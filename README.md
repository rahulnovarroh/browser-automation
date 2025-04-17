# Browser Automation Agent

A containerized browser automation service that uses Playwright and AI to perform tasks in a web browser.

## Overview

This service provides an API endpoint that accepts natural language task descriptions and uses an AI agent to perform those tasks in a headless browser. The service is containerized for easy deployment and includes monitoring capabilities via Loki and Grafana.

## Features

- **AI-Powered Browser Automation**: Uses LangChain and OpenAI to interpret and execute browser tasks
- **Headless Browser**: Runs Google Chrome in a headless environment
- **VNC Access**: Allows real-time viewing of browser automation through noVNC
- **API Endpoint**: Simple REST API for task submission
- **Monitoring**: Log monitoring with Loki and Grafana
- **Caching**: In-memory caching for repeated tasks

## Prerequisites

- Docker and Docker Compose
- OpenAI API key

## Quick Start

1. Clone this repository:
   ```bash
   git clone https://github.com/rahulnovarroh/browser-automation.git
   cd browser-automation
   ```

2. Create an `.env` file with your OpenAI API key:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

3. Start the services:
   ```bash
   docker-compose up -d --build
   ```

4. The following services will be available:
   - Browser Agent API: `http://localhost:5001`
   - noVNC Browser View: `http://localhost:6080`
   - Grafana Dashboard: `http://localhost:3000`

## Configuration

### Environment Variables

Configure the service using these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | (Required) |
| `OPENAI_MODEL` | OpenAI model to use | `gpt-4o` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `HEADLESS` | Run browser in headless mode | `true` |
| `AGENT_TIMEOUT` | Timeout for agent tasks (seconds) | `300` |
| `AGENT_MAX_STEPS` | Maximum steps for an agent task | `30` |
| `MAX_BROWSER_INSTANCES` | Maximum concurrent browser instances | `5` |
| `ENABLE_CACHE` | Enable in-memory caching | `false` |
| `CACHE_TTL` | Cache time-to-live (seconds) | `3600` |

### Docker Compose Configuration

The `docker-compose.yml` file includes:

- `browser-agent`: The main service (API and browser automation)
- `loki`: Log aggregation service
- `promtail`: Log collection agent
- `grafana`: Dashboard for viewing logs

## Usage

### API Endpoints

#### Health Check

```
GET /health
```

Returns service health status.

#### Execute Browser Task

```
POST /agents
```

Request Body:
```json
{
  "task": "Go to example.com and click on the About link"
}
```

Response:
```json
{
  "data": {
    "task_id": "uuid-string",
    "response": "Go to example.com and click on the About link",
    "url": "https://example.com",
    "type": "browser-use",
    "request": "dom",
    "actions": [
      {
        "selector": "a[href='/about']",
        "action": "click",
        "waitBefore": 1000,
        "waitAfter": 1000
      }
    ],
    "execution_time": 5.2
  }
}
```

### Viewing Browser Activity

You can view the browser automation in real-time using the noVNC interface:

1. Navigate to `http://localhost:6080` in your web browser
2. You'll see the headless browser performing the tasks

## Monitoring

### Log Monitoring with Grafana

1. Access Grafana at `http://localhost:3000`
2. Login with username `admin` and password `admin` (or the password set in your environment)
3. Navigate to the Explore page
4. Select "Loki" as the data source
5. Use query: `{container="browser-agent"}`

### Common Queries

- All logs: `{container="browser-agent"}`
- Error logs: `{container="browser-agent"} |= "ERROR"`
- Agent task logs: `{container="browser-agent"} |= "task"`

## Troubleshooting

### Common Issues

#### Playwright Browser Not Found

If you see an error about Playwright browser not found:

```
ERROR Failed to initialize Playwright browser: BrowserType.launch: Executable doesn't exist
```

Solution: This occurs because Playwright browsers aren't properly installed for the user running the container. Fix it by:

```bash
# Update your Dockerfile to install browsers as root and set proper permissions
# Use the global PLAYWRIGHT_BROWSERS_PATH environment variable
docker-compose build --no-cache browser-agent
```

#### No Logs in Grafana

If you don't see logs in Grafana:

1. Check if Loki is running:
   ```bash
   docker-compose ps loki
   ```

2. Verify the Loki data source is configured correctly in Grafana:
   - Go to Grafana → Configuration → Data Sources
   - Check the Loki URL is set to `http://loki:3100` (not localhost)

3. Make sure Promtail can access the Docker socket:
   ```bash
   docker-compose logs promtail
   ```

4. Update your promtail-config.yml to use Docker service discovery:
   ```yaml
   scrape_configs:
     - job_name: docker
       docker_sd_configs:
         - host: unix:///var/run/docker.sock
           refresh_interval: 5s
   ```

#### Container Fails to Start

Check the logs:
```bash
docker-compose logs browser-agent
```

## Building from Source

If you need to rebuild the container:

```bash
docker-compose build
```

## Project Structure

```
.
├── Dockerfile              # Container configuration
├── docker-compose.yml      # Multi-container setup
├── main.py                 # Main API server
├── start.sh                # Container startup script
├── promtail-config.yml     # Log collection configuration
├── loki-config.yaml        # Log storage configuration
└── grafana/                # Grafana dashboards & configuration
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
