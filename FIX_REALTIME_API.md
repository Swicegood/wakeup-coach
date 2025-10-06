# Fix Realtime API - Action Plan

## THE PROBLEM

Your Realtime API calls fail because **Twilio cannot connect to your WebSocket endpoint**. 

The root cause is likely **macvlan networking** in your `docker-compose.yml`, which can block WebSocket upgrade headers.

## QUICK DIAGNOSIS

Run this to check WebSocket status:
```bash
curl http://YOUR_DOMAIN:8765/websocket-status
```

## SOLUTION: Switch to Bridge Networking

Your current setup uses macvlan networking, which is great for getting a dedicated IP but can interfere with WebSockets. The fix is simple:

### Step 1: Backup Current Config
```bash
cd "/mnt/y/My Drive/Computer/python/wakeup-coach"
cp docker-compose.yml docker-compose-macvlan.yml.backup
```

### Step 2: Use Bridge Network Config
```bash
# Replace current docker-compose.yml with bridge version
cp docker-compose-bridge.yml docker-compose.yml

# Or manually edit docker-compose.yml and remove the macvlan network section
```

### Step 3: Restart Docker Container
```bash
docker-compose down
docker-compose up -d
```

### Step 4: Watch Logs
```bash
docker-compose logs -f
```

### Step 5: Test WebSocket (Manual Test)

Install wscat if you haven't:
```bash
npm install -g wscat
```

Test connection:
```bash
wscat -c ws://YOUR_DOMAIN:8765/test-websocket
```

**Expected output:**
```
Connected (press CTRL+C to quit)
< {"status":"connected","message":"WebSocket is working!"}
```

If this works, WebSockets are functioning!

### Step 6: Test Realtime API Call
```bash
curl http://YOUR_DOMAIN:8765/test-call-realtime
```

**Watch logs for:**
```
INFO - Creating Media Stream with URL: ws://YOUR_DOMAIN:8765/media-stream
INFO - TwiML: <Response>...
INFO - Media Stream WebSocket connection accepted from Twilio  ← THIS SHOULD APPEAR!
INFO - Attempting to connect to OpenAI Realtime API...
INFO - Connected to OpenAI Realtime API
INFO - Stream started: MZ..., Call: CA...
```

## ALTERNATIVE: Test WebSocket Programmatically

Run the included test script:
```bash
docker exec -it wakeup-coach python test_websocket.py
```

This will test both local and external WebSocket connectivity.

## IF BRIDGE NETWORKING DOESN'T WORK

### Option A: Use ngrok (Temporary Testing)

```bash
# Install ngrok
# Download from: https://ngrok.com/download

# Run ngrok
ngrok http 8000

# Update .env file with ngrok URL
# BASE_URL=https://xxxx-xx-xx-xxx-xxx.ngrok-free.app

# Restart container
docker-compose restart
```

### Option B: Debug Macvlan + WebSockets

If you must use macvlan, you'll need to:

1. **Check if your router supports WebSocket forwarding**
2. **Verify firewall allows WebSocket protocol** (not just TCP)
3. **Test from Twilio's IP ranges specifically**

But honestly, **bridge networking is simpler and will work**.

## WHILE DEBUGGING: Disable Realtime API

To keep your wake-up coach working while fixing this:

```bash
# Disable Realtime API (use only Traditional mode)
curl -X POST "http://YOUR_DOMAIN:8765/realtime-api-config?probability=0.0"

# Your wake-up calls will work perfectly with Traditional API
curl http://YOUR_DOMAIN:8765/test-call
```

Later, re-enable:
```bash
curl -X POST "http://YOUR_DOMAIN:8765/realtime-api-config?probability=0.5"
```

## SUCCESS CRITERIA

You'll know it's working when:

1. ✅ `wscat -c ws://YOUR_DOMAIN:8765/test-websocket` connects
2. ✅ Logs show "Media Stream WebSocket connection accepted from Twilio"
3. ✅ Logs show "Connected to OpenAI Realtime API"
4. ✅ You can have a natural conversation with ultra-low latency

## EXPECTED BEHAVIOR

**Working Realtime API call flow:**

1. Call initiated → `Initiating FORCED Realtime API test call...`
2. Call connects → `in-progress`
3. TwiML sent → `Creating Media Stream with URL: ws://...`
4. **WebSocket connects** → `Media Stream WebSocket connection accepted from Twilio`
5. OpenAI connects → `Connected to OpenAI Realtime API`
6. Audio streams → Real-time conversation!

## SUMMARY

**Root cause:** Macvlan networking blocks WebSocket connections

**Fix:** Switch to bridge networking

**Quick test:** `wscat -c ws://YOUR_DOMAIN:8765/test-websocket`

**Temporary workaround:** Disable Realtime API (use Traditional mode)

The changes I've made to `main.py`:
- ✅ Enhanced WebSocket configuration in Uvicorn
- ✅ Added `/websocket-status` endpoint to check WebSocket support
- ✅ Added better error logging
- ✅ Created test scripts and documentation

Now it's just a matter of fixing the Docker networking! 🚀

