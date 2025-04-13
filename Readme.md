# Wake-up Coach

An AI-powered wake-up coach that calls you in the morning and engages in a natural conversation to help you wake up gently and start your day positively.

## Features

- Automated wake-up calls at your specified time
- Natural conversation using OpenAI's GPT-4
- Voice interaction using Twilio's voice services
- Docker containerization for easy deployment
- Configurable wake-up time and phone numbers

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

2. Copy the environment template and fill in your credentials:
   ```bash
   cp .env.example .env
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