#!/usr/bin/env bash

# mobile-dev.sh — The Listening Tree Mobile Development Script
# High-speed development with Live Reload on iOS/Android

# 1. Configuration
PYTHON_EXE="python3"
CAP_PLATFORM="${1:-ios}" # Default to ios, can be 'android'
IP_ADDR=$(ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print $2}' | head -n 1)
PORT=5000
SERVER_URL="http://$IP_ADDR:$PORT"

echo "----------------------------------------------------"
echo "🚀 The Listening Tree: Mobile Development Mode"
echo "🌐 Server URL: $SERVER_URL"
echo "📱 Platform: $CAP_PLATFORM"
echo "----------------------------------------------------"

# 2. Check if Python server is already running, if not start it in background
if ! lsof -i :$PORT > /dev/null; then
    echo "📦 Starting Python backend server..."
    $PYTHON_EXE run.py &
    SERVER_PID=$!
    # Finish background process on script exit
    trap "kill $SERVER_PID" EXIT
    sleep 2 # Wait for server to initialize
else
    echo "✅ Backend server is already running on port $PORT."
fi

# 3. Synchronize Capacitor (Update plugins etc.)
echo "🔄 Synchronizing Capacitor..."
npx cap sync $CAP_PLATFORM

# 4. Run with Live Reload
# This will open Xcode or Android Studio and link it to your local server
echo "✨ Starting Live Reload..."
echo "Tips: Keep your phone and computer on the same Wi-Fi ($IP_ADDR)"

if [[ "$CAP_PLATFORM" == "ios" ]]; then
    # Force iPhone 17 Pro simulator to avoid loading iPad by default
    npx cap run ios --target DB0D47B0-237E-44C0-A7D5-C9E4EA412D74 --livereload --external --port $PORT --address $IP_ADDR
else
    npx cap run $CAP_PLATFORM --livereload --external --port $PORT --address $IP_ADDR
fi
