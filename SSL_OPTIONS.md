# SSL Options When Port 443 Is Taken

You have **two great options** since port 443 is already used by your router:

## Option 1: Cloudflare Tunnel (RECOMMENDED ⭐)

**Best for your situation!**

### Pros:
- ✅ **NO port forwarding needed at all**
- ✅ No port conflicts - doesn't use any ports
- ✅ Free SSL from Cloudflare
- ✅ WebSocket support built-in
- ✅ DDoS protection included
- ✅ Works anywhere, even behind strict firewalls
- ✅ Easiest to set up

### Cons:
- Requires domain nameservers pointed to Cloudflare
- DNS propagation wait (usually < 1 hour)
- Your traffic goes through Cloudflare (they can see it)

### Setup:
See **SETUP_CLOUDFLARE_TUNNEL.md** for complete instructions.

Quick steps:
1. Sign up for Cloudflare (free)
2. Add your domain
3. Update nameservers
4. Create tunnel, get token
5. Add token to `.env`
6. Deploy: `docker-compose -f docker-compose-cloudflare.yml up -d`

**URL:** `https://YOUR_DOMAIN` (no port!)

---

## Option 2: Caddy with Custom Port (8443)

**Use if you don't want Cloudflare.**

### Pros:
- ✅ Free SSL from Let's Encrypt
- ✅ Runs entirely on your server
- ✅ No third-party involved
- ✅ Auto certificate renewal

### Cons:
- ❌ Requires port forwarding (80 and 8443)
- ❌ Must include port in URL: `https://YOUR_DOMAIN:8443`
- ❌ Twilio webhooks need `:8443` suffix
- ⚠️ Let's Encrypt verification might fail on some routers

### Port Forwarding Needed:
- **Port 80** → **80** (for Let's Encrypt verification)
- **Port 8443** → **8443** (for HTTPS traffic)

### Files:

**docker-compose-caddy-8443.yml:**
```yaml
version: '3.8'

services:
  wakeup-coach:
    build: .
    container_name: wakeup-coach
    restart: unless-stopped
    networks:
      - wakeup_network
    volumes:
      - ./config:/app/config
    env_file:
      - .env
    environment:
      - TZ=America/New_York
      - PORT=8000
      - EXTERNAL_PORT=8443

  caddy:
    image: caddy:latest
    container_name: wakeup-coach-caddy
    restart: unless-stopped
    ports:
      - "80:80"    # HTTP (for Let's Encrypt)
      - "8443:443" # HTTPS on custom port
    volumes:
      - ./Caddyfile-8443:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - wakeup_network
    depends_on:
      - wakeup-coach

networks:
  wakeup_network:
    driver: bridge

volumes:
  caddy_data:
  caddy_config:
```

**Caddyfile-8443:**
```
YOUR_DOMAIN:8443 {
    reverse_proxy wakeup-coach:8000 {
        header_up Upgrade {http.request.header.Upgrade}
        header_up Connection {http.request.header.Connection}
        header_up Host {http.request.host}
        header_up X-Real-IP {http.request.remote.host}
        header_up X-Forwarded-For {http.request.remote.host}
        header_up X-Forwarded-Proto {http.request.scheme}
    }
}
```

**Update .env:**
```bash
BASE_URL=https://YOUR_DOMAIN:8443
EXTERNAL_PORT=8443
```

**Deploy:**
```bash
docker-compose -f docker-compose-caddy-8443.yml up -d
```

**Test:**
```bash
curl https://YOUR_DOMAIN:8443/
wscat -c wss://YOUR_DOMAIN:8443/test-websocket
```

**Important:** All Twilio webhooks must include `:8443`:
- `https://YOUR_DOMAIN:8443/voice`
- `https://YOUR_DOMAIN:8443/voice-realtime`
- `https://YOUR_DOMAIN:8443/call-status`

---

## Comparison

| Feature | Cloudflare Tunnel | Caddy (Port 8443) |
|---------|------------------|-------------------|
| **Port forwarding** | None needed ✅ | 80 + 8443 needed |
| **Port conflicts** | No conflicts ✅ | Uses 80 + 8443 |
| **SSL certificates** | Free (Cloudflare) | Free (Let's Encrypt) |
| **WebSocket support** | Built-in ✅ | Built-in ✅ |
| **URL format** | `https://domain` | `https://domain:8443` |
| **Setup complexity** | Medium | Easy |
| **Third-party service** | Yes (Cloudflare) | No |
| **DDoS protection** | Included ✅ | Not included |
| **Works behind NAT** | Yes ✅ | Depends |
| **Cost** | Free | Free |

---

## My Recommendation

**Use Cloudflare Tunnel** because:
1. No port forwarding = no router conflicts
2. Clean URLs without port numbers
3. DDoS protection included
4. Easier for Twilio webhooks
5. Free forever

The only "downside" is your traffic goes through Cloudflare, but:
- They're a trusted CDN used by millions
- They don't log request contents
- Still encrypted end-to-end
- Industry standard for web hosting

---

## Quick Decision Tree

**Q: Do you want the cleanest, easiest solution?**
→ **Cloudflare Tunnel** (see SETUP_CLOUDFLARE_TUNNEL.md)

**Q: Do you want everything on your server with no third parties?**
→ **Caddy with Port 8443** (see above)

**Q: Do you need to test quickly right now?**
→ **Ngrok** (see USE_NGROK.md) - temporary but instant

---

## Files Provided

1. **docker-compose-cloudflare.yml** - Cloudflare Tunnel setup
2. **SETUP_CLOUDFLARE_TUNNEL.md** - Complete Cloudflare guide
3. **docker-compose-ssl.yml** - Original Caddy on port 443
4. **This file** - Options comparison

Choose your path and follow the guide! 🚀

