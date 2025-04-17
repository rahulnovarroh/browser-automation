FROM python:3.11-slim

# --- System setup ---
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install browser dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip git curl sudo wget unzip gnupg \
    procps \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libwayland-client0 \
    libxfixes3 \
    libxkbcommon0 \
    xdg-utils \
    xvfb fluxbox x11vnc supervisor \
    ca-certificates fonts-liberation libappindicator3-1 \
    libasound2 libatk-bridge2.0-0 libnspr4 libnss3 libxss1 libxtst6 libx11-xcb1 \
    libxcomposite1 libxcursor1 libxdamage1 libxi6 libxrandr2 libgbm1 \
    --no-install-recommends && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Chrome installation ---
RUN curl -sSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-unstable && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Install noVNC ---
RUN mkdir -p /opt/novnc && \
    git clone https://github.com/novnc/noVNC.git /opt/novnc && \
    git clone https://github.com/novnc/websockify /opt/websockify && \
    ln -s /opt/novnc/vnc.html /opt/novnc/index.html

# --- App setup (agent) ---
WORKDIR /app

# Install Python dependencies first
RUN pip install --upgrade pip
COPY ./dist/browser_use-*.whl /app/
RUN pip install --upgrade pip
RUN pip install /app/browser_use-*.whl
RUN pip install asyncio langchain-openai python-dotenv prometheus-client pydantic aiohttp numpy

# Install Playwright
RUN pip install playwright
# Install Playwright system dependencies as root
RUN playwright install-deps
# Install browsers in global location
RUN mkdir -p /ms-playwright && \
    playwright install chromium

# Copy agent code
COPY . /app

RUN if [ -f "/app/dist/browser_use-*.whl" ]; then \
        pip install /app/dist/browser_use-*.whl; \
    fi

# Create necessary directories
RUN mkdir -p /app/logs /app/duplo_logs /app/duplo_logs/duplo_conversation

# Copy startup script
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Create non-root user for security
RUN useradd -m appuser
RUN chown -R appuser:appuser /app /ms-playwright /opt/novnc /opt/websockify

ENV HEADLESS=true \
    LOG_LEVEL=INFO \
    LOG_DIR=logs \
    PORT=5001 \
    HOST=0.0.0.0

# Switch to appuser
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:5001/health || exit 1

# Expose ports
EXPOSE 5001 6080 9222 5900

CMD ["/start.sh"]