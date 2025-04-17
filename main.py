import os
import json
import asyncio
import logging
import time
import uuid
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional

from aiohttp import web, ClientSession, ClientTimeout
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from browser_use import Agent, BrowserConfig, Browser, BrowserContextConfig

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_dir = os.getenv("LOG_DIR", "logs")
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s [%(levelname)s] [%(name)s] [%(process)d] %(message)s",
    handlers=[
        logging.StreamHandler(),
        RotatingFileHandler(
            f"{log_dir}/server.log",
            maxBytes=10485760,  # 10MB
            backupCount=10
        )
    ]
)

logger = logging.getLogger(__name__)

# Custom exceptions
class ValidationError(Exception):
    pass

class ResourceError(Exception):
    pass

# Simple in-memory cache
class Cache:
    def __init__(self):
        self.data = {}
    
    def get(self, key):
        if key in self.data:
            value, expiry = self.data[key]
            if expiry > time.time():
                return value
            else:
                del self.data[key]
        return None
    
    def set(self, key, value, ttl=3600):
        self.data[key] = (value, time.time() + ttl)
    
    def delete(self, key):
        if key in self.data:
            del self.data[key]

# Resource management
class ResourceManager:
    def __init__(self):
        self.llm_instances = {}
        self.browser_pool = []
        self.max_browsers = int(os.getenv("MAX_BROWSER_INSTANCES", "10"))
        self.browsers_in_use = set()
        self.browser_lock = asyncio.Lock()
        self.cache = Cache()
        
    async def initialize(self):
        # Initialize LLM instances with default model
        default_model = os.getenv("OPENAI_MODEL", "gpt-4o")
        self.llm_instances[default_model] = ChatOpenAI(
            model=default_model,
            temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.7")),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
            request_timeout=float(os.getenv("OPENAI_TIMEOUT", "60"))
        )
        
        logger.info(f"Resource manager initialized with model: {default_model}")
    
    async def get_llm(self, model_name=None):
        model_name = model_name or os.getenv("OPENAI_MODEL", "gpt-4o")
        return self.llm_instances.get(model_name)
    
    async def get_browser(self):
        async with self.browser_lock:
            # Try to reuse an existing browser
            for browser in self.browser_pool:
                if browser not in self.browsers_in_use:
                    self.browsers_in_use.add(browser)
                    return browser
            
            # Create new browser if under limit
            if len(self.browser_pool) < self.max_browsers:
                config = BrowserConfig(
                    headless=False,
                    disable_security=False,
                    new_context_config=BrowserContextConfig(
                        highlight_elements=False,
                    ),
                )
                
                browser = Browser(config=config)
                self.browser_pool.append(browser)
                self.browsers_in_use.add(browser)
                return browser
            
            # No browsers available
            raise ResourceError("No browser instances available")
    
    async def release_browser(self, browser):
        async with self.browser_lock:
            if browser in self.browsers_in_use:
                self.browsers_in_use.remove(browser)
    
    async def cleanup(self):
        # Close all browsers
        for browser in self.browser_pool:
            try:
                await browser.close()
            except Exception as e:
                logger.error(f"Error closing browser: {str(e)}")

# Middleware
@web.middleware
async def error_middleware(request, handler):
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as e:
        logger.exception("Unhandled exception")
        return web.json_response(
            {"error": "Internal server error", "request_id": str(uuid.uuid4())},
            status=500
        )

# Request handlers
async def health_check(request):
    health_data = {
        "status": "ok",
        "timestamp": time.time(),
        "version": os.getenv("SERVICE_VERSION", "1.0.0"),
    }
    
    status_code = 200
    return web.json_response(health_data, status=status_code)

async def agents(request):
    task_id = str(uuid.uuid4())
    start_time = time.time()
    browser = None
    
    try:
        # Validate request
        if not request.can_read_body:
            raise ValidationError("Missing request body")
        
        data = await request.json()
        task = data.get("task")
        
        if not task:
            raise ValidationError("Missing 'task' in request payload")
        
        if len(task) > int(os.getenv("MAX_TASK_LENGTH", "1000")):
            raise ValidationError("Task exceeds maximum length")
        
        # Get resources
        llm = await request.app["resources"].get_llm()
        browser = await request.app["resources"].get_browser()
        
        # Check cache if enabled
        if os.getenv("ENABLE_CACHE", "false").lower() == "true":
            cache_key = f"task_cache:{hash(task)}"
            cached_result = request.app["resources"].cache.get(cache_key)
            
            if cached_result:
                logger.info(f"Cache hit for task: {task_id}")
                response_data = cached_result
                return web.json_response({"data": response_data})
        
        # Ensure conversation path directory exists
        conversation_path = os.getenv("CONVERSATION_LOG_PATH", "duplo_logs/duplo_conversation")
        os.makedirs(os.path.dirname(conversation_path), exist_ok=True)
        
        # Create and run agent with timeout
        agent = Agent(
            task=task,
            llm=llm,
            use_vision=True,
            browser=browser,
            include_attributes=[
                "title", "type", "name", "role", "aria-label",
                "placeholder", "value", "alt", "aria-expanded", "data-date-format"
            ],
            save_conversation_path=conversation_path,
        )
        
        # Run with timeout
        try:
            history = await asyncio.wait_for(
                agent.run(), 
                timeout=float(os.getenv("AGENT_TIMEOUT", "300"))
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent task {task_id} timed out")
            raise TimeoutError("Agent task execution timed out")
        
        # Process results
        history_actions = history.model_actions()
        
        url = ""
        actions = []
        
        for action in history_actions:
            if "go_to_url" in action:
                url = action["go_to_url"]["url"]
            if "click_element" in action and action.get("interacted_element"):
                interacted_element = action["interacted_element"]
                actions.append({
                    "selector": interacted_element.get("css_selector"),
                    "action": "click",
                    "waitBefore": int(os.getenv("WAIT_BEFORE_CLICK", "1000")),
                    "waitAfter": int(os.getenv("WAIT_AFTER_CLICK", "1000")),
                })
        
        response_data = {
            "task_id": task_id,
            "response": task,
            "url": url,
            "type": "browser-use",
            "request": "dom",
            "actions": actions,
            "execution_time": time.time() - start_time
        }
        
        # Cache result if enabled
        if os.getenv("ENABLE_CACHE", "false").lower() == "true":
            cache_key = f"task_cache:{hash(task)}"
            request.app["resources"].cache.set(
                cache_key,
                response_data,
                int(os.getenv("CACHE_TTL", "3600"))
            )
        
        return web.json_response({"data": response_data})
        
    except ValidationError as e:
        logger.warning(f"Validation error: {str(e)}")
        return web.json_response({"error": str(e)}, status=400)
    
    except ResourceError as e:
        logger.error(f"Resource error: {str(e)}")
        return web.json_response({"error": str(e)}, status=503)
    
    except asyncio.TimeoutError:
        logger.error(f"Task {task_id} timed out")
        return web.json_response({"error": "Request timed out"}, status=504)
    
    except Exception as e:
        logger.exception(f"Error handling /agents request: {str(e)}")
        return web.json_response(
            {
                "error": "Internal server error",
                "request_id": task_id,
            },
            status=500
        )
    
    finally:
        if browser:
            await request.app["resources"].release_browser(browser)

async def create_app():
    app = web.Application(middlewares=[
        error_middleware,
    ])
    
    # Add routes
    app.router.add_get("/health", health_check)
    app.router.add_post("/agents", agents)
    
    # Initialize resources
    app["resources"] = ResourceManager()
    await app["resources"].initialize()
    
    # Set up shutdown handler
    async def cleanup_resources(app):
        await app["resources"].cleanup()
    
    app.on_cleanup.append(cleanup_resources)
    
    return app

async def run_server():
    # Create and configure the application
    app = await create_app()
    
    # Start server
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5001"))
    
    # Set up graceful shutdown
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, host, port)
    await site.start()
    
    logger.info(f"Server running on http://{host}:{port}")
    
    # Keep server running
    try:
        while True:
            await asyncio.sleep(3600)  # 1 hour
    except asyncio.CancelledError:
        logger.info("Server shutdown initiated")
    finally:
        logger.info("Cleaning up resources...")
        await runner.cleanup()
        logger.info("Server shutdown complete")

def main():
    try:
        # Run main server
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped manually")
    except Exception as e:
        logger.exception(f"Unexpected server error: {str(e)}")
        exit(1)

if __name__ == "__main__":
    main()