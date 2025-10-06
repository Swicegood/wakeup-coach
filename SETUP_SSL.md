# Setup SSL with Caddy (Free & Automatic)

## Why Caddy?

- ✅ **Automatic SSL certificates** from Let's Encrypt
- ✅ **Auto-renewal** - never expires
- ✅ **WebSocket support** built-in
- ✅ **Simple configuration** - just one file
- ✅ **Free forever**
- ✅ **Perfect for Unraid**

## Prerequisites

1. **Domain name pointing to your server**: `YOUR_DOMAIN` must resolve to your public IP
2. **Ports 80 and 443 open**: Forward these ports to your Unraid server
3. **Valid domain ownership**: Let's Encrypt needs to verify you own the domain

## Step 1: Update Port Forwarding

On your router, update port forwarding:

### Remove old forwarding:
- ~~8765 → 8765~~ (remove this)

### Add new forwarding:
- **80** → **80** (HTTP - for Let's Encrypt verification)
- **443** → **443** (HTTPS - for actual traffic)

## Step 2: Verify Domain Resolution

Make sure your domain points to your public IP:

```bash
# Check if domain resolves correctly
nslookup YOUR_DOMAIN

# Or
dig YOUR_DOMAIN

# Should show your public IP address
```

## Step 3: Update Configuration Files

### Edit `Caddyfile`
The file is already created, but verify the domain is correct:

```bash
cd "/mnt/y/My Drive/Computer/python/wakeup-coach"
cat Caddyfile
```

Should show:
```
YOUR_DOMAIN {
    reverse_proxy wakeup-coach:8000 {
        ...
    }
}
```

Edit it with your actual domain:
```bash
nano Caddyfile
# Change YOUR_DOMAIN to your actual domain
```

### Update `.env` file

```bash
nano .env
```

Change:
```bash
# OLD
# BASE_URL=http://YOUR_DOMAIN:8765

# NEW
BASE_URL=https://YOUR_DOMAIN
EXTERNAL_PORT=443
```

No port number needed - HTTPS uses 443 by default!

## Step 4: Deploy with SSL

### Backup current setup:
```bash
cd "/mnt/y/My Drive/Computer/python/wakeup-coach"
cp docker-compose.yml docker-compose-old.yml.backup
```

### Use the SSL-enabled docker-compose:
```bash
cp docker-compose-ssl.yml docker-compose.yml
```

### Restart everything:
```bash
docker-compose down
docker-compose up -d
```

## Step 5: Watch Caddy Get SSL Certificate

```bash
docker-compose logs -f caddy
```

You should see:
```
caddy  | {"level":"info","msg":"certificate obtained successfully"}
caddy  | {"level":"info","msg":"serving initial configuration"}
```

**This means SSL is working!** 🎉

Press Ctrl+C to stop following logs.

## Step 6: Test HTTPS

```bash
# Test HTTPS (should work)
curl https://YOUR_DOMAIN/

# Should return: {"status":"Wake-up Coach is running",...}
```

```bash
# Test WebSocket with SSL (should work)
wscat -c wss://YOUR_DOMAIN/test-websocket

# Should connect and show: {"status":"connected",...}
```

## Step 7: Test Realtime API

```bash
curl https://YOUR_DOMAIN/test-call-realtime
```

Watch logs:
```bash
docker-compose logs -f wakeup-coach
```

You should see:
```
INFO - Creating Media Stream with URL: wss://YOUR_DOMAIN/media-stream
INFO - MEDIA STREAM WEBSOCKET ENDPOINT HIT!
INFO - ✓✓✓ Media Stream WebSocket connection ACCEPTED from Twilio ✓✓✓
INFO - Connected to OpenAI Realtime API
```

**SUCCESS!** 🎉🎉🎉

## Troubleshooting

### Issue: Caddy can't get certificate

**Error:**
```
caddy  | {"level":"error","msg":"could not get certificate"}
```

**Solutions:**

1. **Check domain resolution:**
   ```bash
   nslookup YOUR_DOMAIN
   # Must show your public IP
   ```

2. **Check port 80 is open:**
   ```bash
   # From outside your network (use your phone)
   curl http://YOUR_DOMAIN/.well-known/acme-challenge/test
   ```

3. **Check firewall:**
   ```bash
   # On Unraid/server
   sudo ufw status
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```

4. **Verify router port forwarding:**
   - Port 80 → Unraid IP:80
   - Port 443 → Unraid IP:443

### Issue: WebSocket still not working

1. **Check TwiML URL in logs:**
   ```bash
   docker-compose logs wakeup-coach | grep "Creating Media Stream"
   ```
   Should show: `wss://YOUR_DOMAIN/media-stream`

2. **Check BASE_URL:**
   ```bash
   docker-compose exec wakeup-coach env | grep BASE_URL
   ```
   Should show: `BASE_URL=https://YOUR_DOMAIN`

3. **Restart everything:**
   ```bash
   docker-compose restart
   ```

### Issue: Certificate expired / needs renewal

Caddy auto-renews, but if issues:
```bash
# Force certificate renewal
docker-compose exec caddy caddy reload --config /etc/caddy/Caddyfile
```

## Architecture

```
Internet (Twilio)
    ↓ HTTPS/WSS
Router Port 443
    ↓
Caddy Container (SSL termination)
    ↓ HTTP/WS (internally)
FastAPI App Container
```

## Benefits of This Setup

1. **No ngrok needed** - runs entirely on your server
2. **Free SSL certificates** - Let's Encrypt via Caddy
3. **Auto-renewal** - certificates renew automatically
4. **Production-ready** - stable and reliable
5. **WebSocket support** - works perfectly with Media Streams
6. **Easy maintenance** - minimal configuration

## Files Created

- `docker-compose-ssl.yml` - Docker setup with Caddy
- `Caddyfile` - Caddy reverse proxy configuration
- `SETUP_SSL.md` - This guide

## Update Twilio Webhooks (If Needed)

If you had manually configured any webhooks, update them:

**Old:**
- `http://YOUR_DOMAIN:8765/voice`

**New:**
- `https://YOUR_DOMAIN/voice`

(No port needed - HTTPS is 443 by default)

## Enable Realtime API Again

Once SSL is working:

```bash
# Re-enable Realtime API at 50%
curl -X POST "https://YOUR_DOMAIN/realtime-api-config?probability=0.5"

# Test it
curl https://YOUR_DOMAIN/test-call-realtime
```

## Monitoring SSL Status

```bash
# Check certificate expiry
docker-compose exec caddy caddy list-certificates

# Check Caddy status
docker-compose exec caddy caddy version
```

## Alternative: Cloudflare Tunnel (If Caddy Doesn't Work)

If Let's Encrypt verification fails (some ISPs block port 80), use Cloudflare Tunnel:

1. Sign up for Cloudflare (free)
2. Add your domain to Cloudflare
3. Use Cloudflare Tunnel instead of Caddy

I can provide a docker-compose for this if needed.

## Success Checklist

- [ ] Ports 80 and 443 forwarded to Unraid
- [ ] Domain resolves to public IP
- [ ] `Caddyfile` has correct domain
- [ ] `.env` has `BASE_URL=https://YOUR_DOMAIN`
- [ ] `docker-compose.yml` is the SSL version
- [ ] Containers running: `docker-compose ps`
- [ ] Caddy obtained certificate: `docker-compose logs caddy`
- [ ] HTTPS works: `curl https://YOUR_DOMAIN/`
- [ ] WSS works: `wscat -c wss://YOUR_DOMAIN/test-websocket`
- [ ] Realtime API works: test call shows Media Stream connected

Once all checked, your Realtime API will work! 🚀

