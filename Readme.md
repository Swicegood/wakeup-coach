# Wake-up Coach

An AI-powered wake-up coach that calls you in the morning and engages in a natural conversation to help you wake up gently and start your day positively.

## Features

- Automated wake-up calls at your specified time
- **Dual AI Modes:**
  - **Traditional Mode**: Uses OpenAI GPT-4 with speech-to-text for cost-effective conversations
  - **Realtime API Mode**: Uses OpenAI's Realtime API for ultra-natural, low-latency voice interactions
- Configurable probability-based selection between AI modes
- Voice interaction using Twilio's voice services
- Doorbell integration to verify you're out of bed
- Docker containerization for easy deployment
- Configurable wake-up time and phone numbers
- Dynamic configuration via REST API

## Prerequisites

- Docker and Docker Compose installed on your Unraid server
- Twilio account with a phone number
- OpenAI API key
- A phone number to receive wake-up calls

## Setup

1. Clone this repository to your Unraid server:
   ```bash
   git clone https://github.com/yourusername/wakeup-coach.git
   cd wakeup-coach
   ```

2. Create a `.env` file with your credentials:
   ```bash
   cat > .env << 'EOF'
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Twilio Configuration
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# User Configuration
PHONE_NUMBER=+1234567890
WAKE_UP_TIME=06:00

# Server Configuration
SERVER_IP=your_server_ip_here
EXTERNAL_PORT=8765
PORT=8000
BASE_URL=http://your_server_ip_or_domain:8765

# Timezone Configuration
TZ=America/New_York

# Doorbell Configuration (optional)
DOORBELL_ACTIVATION_TIMEOUT=300

# OpenAI Realtime API Configuration
# Probability of using Realtime API (0.0 = never, 0.5 = 50%, 1.0 = always)
REALTIME_API_PROBABILITY=0.5
EOF
   ```

3. Edit the `.env` file with your:
   - OpenAI API key
   - Twilio credentials (Account SID, Auth Token, and phone number)
   - Your phone number
   - Desired wake-up time
   - Your server's IP address or domain name
   - Your timezone

4. Build and start the container:
   ```bash
   docker-compose up -d
   ```

## Configuration

The following environment variables can be configured in the `.env` file:

- `OPENAI_API_KEY`: Your OpenAI API key
- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
- `TWILIO_PHONE_NUMBER`: Your Twilio phone number
- `PHONE_NUMBER`: Your phone number to receive wake-up calls
- `WAKE_UP_TIME`: Desired wake-up time (24-hour format, e.g., "07:00")
- `BASE_URL`: Your server's public URL
- `TZ`: Your timezone (e.g., "America/New_York")
- `DOORBELL_ACTIVATION_TIMEOUT`: Seconds before doorbell activation expires (default: 300)
- `REALTIME_API_PROBABILITY`: Probability of using Realtime API (0.0-1.0, default: 0.5)
  - `0.0` = Always use Traditional Mode (cheaper)
  - `0.5` = 50% chance of either mode
  - `1.0` = Always use Realtime API (more expensive, more natural)

### AI Mode Selection

The app randomly selects between two AI conversation modes:

1. **Traditional Mode** (`/voice` endpoint):
   - Uses GPT-4 with Gather/Response cycle
   - More cost-effective
   - Slight delays between responses
   - Good for basic wake-up conversations

2. **Realtime API Mode** (`/voice-realtime` endpoint):
   - Uses OpenAI's Realtime API with Media Streams
   - More expensive (charged by audio duration)
   - Ultra-low latency, natural interruptions
   - Best for engaging, natural conversations

You can adjust the probability dynamically at runtime:

```bash
# Check current configuration
curl http://your-server:8765/realtime-api-config

# Update probability to 75%
curl -X POST "http://your-server:8765/realtime-api-config?probability=0.75"

# Disable Realtime API completely (0% chance)
curl -X POST "http://your-server:8765/realtime-api-config?probability=0.0"

# Always use Realtime API (100% chance)
curl -X POST "http://your-server:8765/realtime-api-config?probability=1.0"
```

## Usage

The application will automatically make wake-up calls at your specified time. The conversation will:

1. Start with a gentle greeting
2. Ask how you're feeling
3. Engage in a natural conversation to help you wake up
4. Provide encouraging responses to help you start your day positively

## Development

To run the application in development mode:

```bash
docker-compose up
```

## Troubleshooting

- Ensure your Unraid server's firewall allows incoming connections on port 8000
- Verify that your Twilio phone number is properly configured for voice calls
- Check the Docker logs for any errors:
  ```bash
  docker-compose logs -f
  ```

## License

MIT License