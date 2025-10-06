# Troubleshooting Realtime API Issues

## Problem: Realtime API Call Failed

Based on your logs, the Realtime API call failed because the WebSocket connection to `/media-stream` was never established. The call ended after only 3-4 seconds.

### What Should Have Happened

1. Twilio calls `/voice-realtime` ✓ (This worked)
2. Server returns TwiML with `<Connect><Stream>` ✓ (This worked)
3. Twilio connects to WebSocket at `/media-stream` ✗ (This FAILED)
4. Server bridges audio between Twilio and OpenAI ✗ (Never got here)

### Diagnostic Steps

#### Step 1: Test WebSocket Connectivity

Open `websocket-test.html` in your browser and test the WebSocket connection:

```bash
# If running locally, open:
file:///mnt/y/My%20Drive/Computer/python/wakeup-coach/websocket-test.html

# Or serve it via Python:
cd "/mnt/y/My Drive/Computer/python/wakeup-coach"
python3 -m http.server 8080
# Then open: http://localhost:8080/websocket-test.html
```

**Expected result:** Should see "Connected" and receive echo messages

**If it fails:** WebSocket support is not working properly

#### Step 2: Check Logs for TwiML

When you run a test call, look for this log line:
```
TwiML: <Response>...
```

The TwiML should look like:
```xml
<Response>
  <Say>Good morning! Connecting you to your wake-up coach.</Say>
  <Connect>
    <Stream url="ws://YOUR_DOMAIN:8765/media-stream"/>
  </Connect>
</Response>
```

#### Step 3: Test Endpoints Separately

```bash
# Test traditional mode (should work)
curl http://YOUR_DOMAIN:8765/test-call-traditional

# Test realtime mode (currently failing)
curl http://YOUR_DOMAIN:8765/test-call-realtime
```

#### Step 4: Check Docker/Uvicorn Configuration

WebSockets may need special configuration. Check your `docker-compose.yml`:

```yaml
# Make sure you're exposing the port correctly
ports:
  - "8765:8000"  # This should work for WebSockets

# OR if using nginx/reverse proxy, ensure WebSocket upgrade headers
```

### Common Issues & Solutions

#### Issue 1: WebSocket URL Uses Wrong Protocol

**Problem:** Twilio can't connect because the URL uses `ws://` but should use `wss://`

**Solution:** If you have HTTPS/SSL, update in `main.py`:
```python
# Change this line in /voice-realtime endpoint
ws_url = BASE_URL.replace("http://", "wss://").replace("https://", "wss://")
```

#### Issue 2: Firewall Blocking WebSocket Connections

**Problem:** Twilio's servers can't reach your WebSocket endpoint

**Solution:** 
1. Check firewall rules allow WebSocket connections
2. Test from external network:
   ```bash
   # From a different machine/network
   wscat -c ws://YOUR_DOMAIN:8765/test-websocket
   ```

#### Issue 3: Reverse Proxy Not Configured for WebSockets

**Problem:** If using nginx/Apache, WebSockets need special headers

**Nginx Solution:**
```nginx
location /media-stream {
    proxy_pass http://localhost:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

**Apache Solution:**
```apache
ProxyPass /media-stream ws://localhost:8000/media-stream
```

#### Issue 4: Twilio Request Validation Failing

**Problem:** WebSocket connection is rejected due to signature validation

**Solution:** WebSocket connections don't have Twilio signatures, so validation should be skipped for `/media-stream`

The code already handles this (no validation on WebSocket endpoints).

### Testing the Fix

After making changes:

1. **Restart the service:**
   ```bash
   docker-compose restart
   # or
   docker-compose down && docker-compose up -d
   ```

2. **Run a Realtime API test call:**
   ```bash
   curl http://YOUR_DOMAIN:8765/test-call-realtime
   ```

3. **Watch the logs:**
   ```bash
   docker-compose logs -f
   ```

4. **Look for these log messages:**
   ```
   INFO - Creating Media Stream with URL: ws://YOUR_DOMAIN:8765/media-stream
   INFO - TwiML: <Response>...
   INFO - Media Stream WebSocket connection accepted from Twilio
   INFO - Attempting to connect to OpenAI Realtime API...
   INFO - Connected to OpenAI Realtime API
   INFO - Stream started: MZxxx, Call: CAxxx
   ```

### Fallback Behavior

If Realtime API continues to fail, you can:

1. **Disable it completely:**
   ```bash
   curl -X POST "http://YOUR_DOMAIN:8765/realtime-api-config?probability=0.0"
   ```

2. **Use traditional mode only:**
   ```bash
   curl http://YOUR_DOMAIN:8765/test-call-traditional
   ```

The system will automatically fall back to traditional mode if Realtime API fails.

### Getting More Debug Info

Edit `main.py` and add this to the `/voice-realtime` endpoint:

```python
logger.setLevel(logging.DEBUG)  # Add at top of function
```

This will show more detailed logs about what's happening.

### Need Help?

If still not working after these steps:

1. **Capture full logs** from a test call:
   ```bash
   curl http://YOUR_DOMAIN:8765/test-call-realtime
   # Copy ALL log output
   ```

2. **Test WebSocket from external network:**
   ```bash
   # Install wscat: npm install -g wscat
   wscat -c ws://YOUR_DOMAIN:8765/test-websocket
   ```

3. **Check Twilio debugger:**
   - Go to https://console.twilio.com/monitor/logs/debugger
   - Look for your call SID
   - Check for WebSocket connection errors

### Quick Fix: Use Traditional Mode

While troubleshooting, you can force all calls to use the working traditional mode:

```bash
# Temporarily disable Realtime API
curl -X POST "http://YOUR_DOMAIN:8765/realtime-api-config?probability=0.0"

# Make test calls (will use traditional mode)
curl http://YOUR_DOMAIN:8765/test-call
```

Once WebSocket issues are resolved, re-enable:
```bash
curl -X POST "http://YOUR_DOMAIN:8765/realtime-api-config?probability=0.5"
```

