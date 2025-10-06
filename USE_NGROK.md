# Fix Realtime API with Ngrok

## The Problem

Twilio Media Streams **requires** `wss://` (secure WebSocket), not `ws://`.

From Twilio's documentation:
> "The url attribute must use the wss scheme (WebSockets Secure)"

Your current setup uses `ws://YOUR_DOMAIN:8765/media-stream` which Twilio rejects.

## The Solution: Ngrok

Ngrok provides automatic SSL/HTTPS, which converts to `wss://` for WebSockets.

### Step 1: Install Ngrok

Download from: https://ngrok.com/download

Or install via package manager:
```bash
# Mac
brew install ngrok

# Linux (via snap)
sudo snap install ngrok

# Or download directly
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xvf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/
```

### Step 2: Sign up for Ngrok Account

1. Go to https://dashboard.ngrok.com/signup
2. Get your auth token from: https://dashboard.ngrok.com/get-started/your-authtoken
3. Configure it:
   ```bash
   ngrok config add-authtoken YOUR_AUTH_TOKEN
   ```

### Step 3: Start Ngrok Tunnel

```bash
# Tunnel to your Docker container port
ngrok http 8765
```

You'll see output like:
```
Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Forwarding                    https://xxxx-xx-xx-xxx-xxx.ngrok-free.app -> http://localhost:8765

Connections                   0
```

**Copy the HTTPS URL** (like `https://xxxx-xx-xx-xxx-xxx.ngrok-free.app`)

### Step 4: Update Your .env File

Edit `.env`:
```bash
# OLD (doesn't work for Media Streams)
# BASE_URL=http://YOUR_DOMAIN:8765

# NEW (works with Media Streams)
BASE_URL=https://xxxx-xx-xx-xxx-xxx.ngrok-free.app
```

**Replace with your actual ngrok URL!**

### Step 5: Restart Docker

```bash
docker-compose restart
```

### Step 6: Test Realtime API

```bash
curl https://xxxx-xx-xx-xxx-xxx.ngrok-free.app/test-call-realtime
```

Now watch the logs - you should see:
```
INFO - Creating Media Stream with URL: wss://xxxx-xx-xx-xxx-xxx.ngrok-free.app/media-stream
INFO - MEDIA STREAM WEBSOCKET ENDPOINT HIT!
INFO - ✓✓✓ Media Stream WebSocket connection ACCEPTED from Twilio ✓✓✓
INFO - Connected to OpenAI Realtime API
```

**SUCCESS!** 🎉

## Why This Works

1. Ngrok provides HTTPS automatically
2. FastAPI/Uvicorn sees `https://` in BASE_URL
3. Code converts it to `wss://` (secure WebSocket)
4. Twilio accepts the `wss://` connection
5. Media streams work!

## Ngrok Free Tier Limitations

- URL changes every time you restart ngrok
- Session timeout after 2 hours (must restart)
- Limited connections per minute

## Permanent Solution (Later)

Once you confirm it works with ngrok, you can set up a permanent solution:

### Option 1: Ngrok Paid Plan ($8/month)
- Fixed subdomain (no URL changes)
- No session timeouts
- Higher limits

### Option 2: Let's Encrypt SSL Certificate
1. Get a certificate for `YOUR_DOMAIN`
2. Configure nginx with SSL
3. Use your own domain with `wss://`

### Option 3: Cloudflare Tunnel (Free)
Similar to ngrok but free permanent tunnels

## Testing Checklist

After setting up ngrok:

- [ ] Ngrok is running: `ngrok http 8765`
- [ ] Copied HTTPS URL from ngrok output
- [ ] Updated BASE_URL in `.env` file
- [ ] Restarted Docker: `docker-compose restart`
- [ ] Test call: `curl https://YOUR_NGROK_URL/test-call-realtime`
- [ ] See "MEDIA STREAM WEBSOCKET ENDPOINT HIT!" in logs
- [ ] See "Connected to OpenAI Realtime API" in logs
- [ ] Realtime API call works!

## Quick Commands

```bash
# Start ngrok
ngrok http 8765

# In another terminal, update .env (replace URL)
echo 'BASE_URL=https://YOUR-NGROK-URL.ngrok-free.app' >> .env

# Restart Docker
docker-compose restart

# Test
curl https://YOUR-NGROK-URL.ngrok-free.app/test-call-realtime

# Watch logs
docker-compose logs -f
```

## What You'll See Working

**Before (with ws://):**
```
Creating Media Stream with URL: ws://YOUR_DOMAIN:8765/media-stream
Call completed (no WebSocket connection)
```

**After (with wss:// via ngrok):**
```
Creating Media Stream with URL: wss://xxxx.ngrok-free.app/media-stream
MEDIA STREAM WEBSOCKET ENDPOINT HIT!
✓✓✓ Media Stream WebSocket connection ACCEPTED from Twilio ✓✓✓
Attempting to connect to OpenAI Realtime API...
Connected to OpenAI Realtime API
Stream started: MZxxx, Call: CAxxx
(Real-time conversation happens!)
```

That's it! The mystery is solved - you just needed SSL! 🎯

