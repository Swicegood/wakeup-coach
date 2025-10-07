# Setup Cloudflare Tunnel (No Port Forwarding Required!)

## Why Cloudflare Tunnel?

- ✅ **No port forwarding needed** - bypasses your router
- ✅ **Port 443 conflict solved** - doesn't need any ports
- ✅ **Free SSL** from Cloudflare
- ✅ **WebSocket support** - perfect for Realtime API
- ✅ **DDoS protection** included
- ✅ **Works anywhere** - even behind strict firewalls
- ✅ **Perfect for Unraid**

## Step 1: Sign Up for Cloudflare (Free)

1. Go to https://dash.cloudflare.com/sign-up
2. Create a free account
3. Verify your email

## Step 2: Add Your Domain to Cloudflare

1. In Cloudflare dashboard, click **"Add a Site"**
2. Enter your domain: `YOUR_DOMAIN`
3. Select the **Free** plan
4. Cloudflare will scan your DNS records
5. Click **Continue**
6. **Update your domain nameservers** at your domain registrar (no-ip.com):
   - Log into no-ip.com
   - Change nameservers to Cloudflare's (shown in dashboard)
   - Example: `noah.ns.cloudflare.com` and `tara.ns.cloudflare.com`
7. Wait for DNS propagation (can take up to 24 hours, usually < 1 hour)

## Step 3: Create a Cloudflare Tunnel

1. In Cloudflare dashboard, go to **Zero Trust** (left sidebar)
2. If first time: Set up Zero Trust (it's free, just click through)
3. Go to **Networks** → **Tunnels**
4. Click **Create a tunnel**
5. Select **Cloudflared**
6. Name it: `wakeup-coach`
7. Click **Save tunnel**
8. **Copy the tunnel token** - you'll need this! 
   - It looks like: `eyJhIjoiZjE4M2Q4Y2YtOWFjNC00NTNhLTg1YTktNzQ5MTU3ZTc1NDQ5IiwidCI6IjY3NjY3...`

## Step 4: Configure the Tunnel

Still in the tunnel creation wizard:

1. Under **Public Hostnames**, click **Add a public hostname**
2. Configure:
   - **Subdomain**: Leave empty (or use `wakeup` if you want `wakeup.yourdomain.com`)
   - **Domain**: Select your domain
   - **Path**: Leave empty
   - **Type**: HTTP
   - **URL**: `wakeup-coach:8000`
3. Click **Additional application settings** → **HTTP Settings**:
   - Enable **WebSocket**
   - Enable **No TLS Verify** (since internal connection is HTTP)
4. Click **Save hostname**
5. Click **Save tunnel**

## Step 5: Configure Docker

### Update `.env` file:

```bash
cd "/mnt/y/My Drive/Computer/python/wakeup-coach"
nano .env
```

Add/update these lines:
```bash
# Your Cloudflare Tunnel token (from Step 3)
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiZjE4M2Q4Y2YtOWFjNC00NTNhLTg1YTktNzQ5MTU3ZTc1NDQ5...

# Base URL (your domain with HTTPS)
BASE_URL=https://YOUR_DOMAIN

# External port (Cloudflare uses 443)
EXTERNAL_PORT=443
```

### Deploy:

```bash
# Backup current docker-compose
cp docker-compose.yml docker-compose-old.yml

# Use Cloudflare version
cp docker-compose-cloudflare.yml docker-compose.yml

# Bring everything up
docker-compose down
docker-compose up -d
```

## Step 6: Watch Tunnel Connect

```bash
docker-compose logs -f cloudflared
```

Look for:
```
INF Connection registered connIndex=0
INF Registered tunnel connection
```

**Success!** Your tunnel is connected! 🎉

## Step 7: Test Everything

```bash
# Test HTTPS (from anywhere - even your phone)
curl https://YOUR_DOMAIN/

# Test WebSocket
wscat -c wss://YOUR_DOMAIN/test-websocket

# Test Realtime API
curl https://YOUR_DOMAIN/test-call-realtime
```

Watch logs:
```bash
docker-compose logs -f wakeup-coach
```

Should see:
```
INFO - Creating Media Stream with URL: wss://YOUR_DOMAIN/media-stream
INFO - MEDIA STREAM WEBSOCKET ENDPOINT HIT!
INFO - ✓✓✓ Media Stream WebSocket connection ACCEPTED from Twilio ✓✓✓
INFO - Connected to OpenAI Realtime API
```

**REALTIME API WORKS!** 🎉🎉🎉

## No Port Forwarding Needed!

You can **remove all port forwarding** from your router:
- No need for port 80
- No need for port 443
- No need for port 8765
- Everything goes through Cloudflare's network!

## How It Works

```
Internet (Twilio)
    ↓ HTTPS/WSS
Cloudflare Network (SSL, DDoS protection)
    ↓ Encrypted Tunnel
Cloudflared Container (on your Unraid)
    ↓ Internal network
Wake-up Coach Container
```

## Benefits

1. **No router configuration** - works through your existing internet
2. **No port conflicts** - doesn't need any ports open
3. **Free SSL** - Cloudflare provides certificates
4. **DDoS protection** - Cloudflare filters bad traffic
5. **Fast** - Cloudflare's global CDN
6. **WebSocket support** - perfect for Media Streams
7. **Works anywhere** - VPN, firewall, NAT, doesn't matter

## Troubleshooting

### Issue: Tunnel won't connect

**Check token:**
```bash
docker-compose exec cloudflared env | grep TUNNEL_TOKEN
```

Should show your token. If empty, check `.env` file.

**Check tunnel status in Cloudflare:**
1. Go to Zero Trust → Networks → Tunnels
2. Your tunnel should show **HEALTHY** (green)

### Issue: Domain doesn't resolve

**Wait for DNS propagation:**
```bash
nslookup YOUR_DOMAIN
```

Should show Cloudflare IPs (not your home IP). This is correct!

**Check Cloudflare DNS:**
1. Go to Cloudflare dashboard → DNS → Records
2. Make sure there's a CNAME record pointing to your tunnel

### Issue: WebSocket not working

**Enable WebSocket in tunnel config:**
1. Zero Trust → Networks → Tunnels
2. Click your tunnel → **Configure**
3. Edit the public hostname
4. HTTP Settings → Enable **WebSocket**
5. Save

## Alternative: Use Subdomain

If you want to keep your main domain separate:

In Cloudflare tunnel configuration:
- **Subdomain**: `wakeup`
- **Domain**: `YOUR_DOMAIN`
- Result: `https://wakeup.YOUR_DOMAIN`

Then update `.env`:
```bash
BASE_URL=https://wakeup.YOUR_DOMAIN
```

## Update Twilio Webhooks

Update any manually configured webhooks:

**New URL:**
- `https://YOUR_DOMAIN/voice`
- `https://YOUR_DOMAIN/voice-realtime`
- `https://YOUR_DOMAIN/call-status`

(No port needed!)

## Enable Realtime API

```bash
# Re-enable Realtime API at 50%
curl -X POST "https://YOUR_DOMAIN/realtime-api-config?probability=0.5"

# Test
curl https://YOUR_DOMAIN/test-call-realtime
```

## Success Checklist

- [ ] Cloudflare account created
- [ ] Domain added to Cloudflare
- [ ] Nameservers updated at registrar
- [ ] DNS propagated (check with nslookup)
- [ ] Tunnel created in Cloudflare
- [ ] Tunnel token copied
- [ ] Public hostname configured with WebSocket enabled
- [ ] `.env` has CLOUDFLARE_TUNNEL_TOKEN and BASE_URL
- [ ] Docker containers running: `docker-compose ps`
- [ ] Tunnel shows HEALTHY in Cloudflare
- [ ] HTTPS works: `curl https://YOUR_DOMAIN/`
- [ ] WSS works: `wscat -c wss://YOUR_DOMAIN/test-websocket`
- [ ] Realtime API works!

## Cost

**$0/month** - Completely free!

Cloudflare Free plan includes:
- Unlimited tunnel bandwidth
- SSL certificates
- DDoS protection
- Up to 50 tunnels
- WebSocket support

Perfect for home use! 🚀

