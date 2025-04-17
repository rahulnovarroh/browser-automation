#!/bin/bash
set -e

echo "Starting browser agent service..."

# Create log directories if they don't already exist
mkdir -p /app/logs
mkdir -p /app/duplo_logs/duplo_conversation

echo "Starting X server..."
# Start Xvfb, x11vnc and fluxbox in the background
export DISPLAY=:99
Xvfb :99 -screen 0 1280x1024x24 &
sleep 2
echo "Starting VNC server..."
x11vnc -display :99 -forever -shared &
fluxbox &

echo "Starting noVNC..."
# Start noVNC (WebSocket proxy to VNC)
/opt/websockify/run 6080 localhost:5900 --web /opt/novnc &

# Allow a moment for the X server to initialize
sleep 2

echo "Environment setup complete. Starting main application..."
# Start the main application
exec python /app/main.py