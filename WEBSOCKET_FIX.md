# WebSocket Connection Fix

## Problem Identified

Your Realtime API calls are failing because **Twilio cannot connect to your WebSocket endpoint**. The TwiML is correct, but no WebSocket connection is being established.

You're using **macvlan networking** in Docker, which can interfere with WebSocket connections.

## Diagnostic Steps

### Step 1: Check if WebSocket endpoints are registered

```bash
curl http://YOUR_DOMAIN:8765/websocket-status
```

This should show all registered routes including WebSocket ones.

### Step 2: Test WebSocket from inside Docker

```bash
# Enter the Docker container
docker exec -it wakeup-coach /bin/bash

# Install websockets (if not already)
pip install websockets

# Run the test script
python test_websocket.py
```

### Step 3: Test WebSocket from outside

```bash
# Install wscat globally
npm install -g wscat

# Test connection
wscat -c ws://YOUR_DOMAIN:8765/test-websocket
```

Expected output:
```json
{"status":"connected","message":"WebSocket is working!"}
```

## Likely Issues & Solutions

### Issue 1: Macvlan Network Blocking WebSockets

**Problem:** Macvlan networking in Docker can block WebSocket upgrade headers

**Solution A - Switch to Bridge Networking (Recommended):**

Edit `docker-compose.yml`:

```yaml
version: '3.3'

services:
  wakeup-coach:
    build: .
    container_name: wakeup-coach
    restart: unless-stopped
    ports:
      - "8765:8000"  # Port mapping
    # Remove macvlan network, use default bridge
    env_file:
      - .env
    environment:
      - TZ=America/New_York
      - PORT=8000
      - EXTERNAL_PORT=8765
```

Then restart:
```bash
docker-compose down
docker-compose up -d
```

**Solution B - Keep Macvlan but Fix WebSocket Headers:**

Add WebSocket headers explicitly in Uvicorn. Edit the last line of `main.py`:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(INTERNAL_PORT),
        ws_ping_interval=None,  # Disable WebSocket ping
        ws_ping_timeout=None,   # Disable WebSocket timeout
        timeout_keep_alive=300  # Keep connections alive
    )
```

### Issue 2: Uvicorn WebSocket Configuration

Add these settings to help with WebSocket connections:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(INTERNAL_PORT),
        # WebSocket-specific settings
        ws="auto",  # Auto-detect WebSocket library
        ws_max_size=16777216,  # 16MB max message size
        timeout_keep_alive=300,  # 5 minutes keep-alive
        access_log=True  # Enable access logs to see WebSocket connections
    )
```

### Issue 3: Firewall/Router Configuration

If WebSocket test works locally but not externally:

1. **Check firewall allows WebSocket protocol:**
   ```bash
   # On your server
   sudo iptables -L | grep 8765
   ```

2. **Verify port forwarding:**
   - Router must forward port 8765 with TCP protocol
   - Some routers need explicit WebSocket support enabled

3. **Test from external network:**
   ```bash
   # From your phone or another network
   wscat -c ws://YOUR_DOMAIN:8765/test-websocket
   ```

### Issue 4: Reverse Proxy (if using Nginx/Apache)

If you have a reverse proxy in front of Docker:

**Nginx Configuration:**
```nginx
server {
    listen 8765;
    
    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

**Apache Configuration:**
```apache
<VirtualHost *:8765>
    ProxyPreserveHost On
    ProxyPass / ws://localhost:8000/
    ProxyPassReverse / ws://localhost:8000/
    
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule /(.*)           ws://localhost:8000/$1 [P,L]
</VirtualHost>
```

## Quick Fix: Temporary Workaround

While debugging WebSocket issues, **disable Realtime API** to keep your wake-up coach working:

```bash
curl -X POST "http://YOUR_DOMAIN:8765/realtime-api-config?probability=0.0"
```

This will use only the Traditional API (which works perfectly).

## Testing After Fix

1. **Restart Docker:**
   ```bash
   docker-compose down
   docker-compose up -d
   docker-compose logs -f
   ```

2. **Test WebSocket:**
   ```bash
   wscat -c ws://YOUR_DOMAIN:8765/test-websocket
   # Should connect and show: {"status":"connected",...}
   ```

3. **Test Realtime API call:**
   ```bash
   curl http://YOUR_DOMAIN:8765/test-call-realtime
   ```

4. **Watch logs for:**
   ```
   Media Stream WebSocket connection accepted from Twilio
   Attempting to connect to OpenAI Realtime API...
   Connected to OpenAI Realtime API
   ```

## Expected Log Flow for Successful Realtime Call

```
INFO - Handling incoming voice call with Realtime API
INFO - Creating Media Stream with URL: ws://YOUR_DOMAIN:8765/media-stream
INFO - TwiML: <Response><Say>...
INFO - Media Stream WebSocket connection accepted from Twilio  ← THIS IS MISSING
INFO - Attempting to connect to OpenAI Realtime API...
INFO - Connected to OpenAI Realtime API
INFO - OpenAI Realtime API session configured
INFO - Stream started: MZ..., Call: CA...
```

The missing line indicates Twilio never connected to the WebSocket.

## If Nothing Works

As a last resort, consider using **ngrok** to expose your local server:

```bash
# Install ngrok
brew install ngrok  # or download from ngrok.com

# Expose port 8000
ngrok http 8000

# Update BASE_URL in .env to ngrok URL
BASE_URL=https://xxxx-xx-xx-xxx-xxx.ngrok-free.app

# Restart
docker-compose restart
```

This bypasses all networking issues and uses ngrok's tunnel (which fully supports WebSockets).

