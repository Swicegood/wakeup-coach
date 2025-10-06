# OpenAI Realtime API Integration

This document describes the implementation of OpenAI's Realtime API as an alternative conversation mode for the Wake-up Coach application.

## Overview

The application now supports **two AI conversation modes** that are randomly selected for each wake-up call:

1. **Traditional Mode** - Original implementation using GPT-4 with speech-to-text
2. **Realtime API Mode** - New implementation using OpenAI's Realtime API with Media Streams

## How It Works

### Probability-Based Selection

Every time a wake-up call is initiated (scheduled, test, or callback), the system:
1. Generates a random number between 0 and 1
2. Compares it to `REALTIME_API_PROBABILITY` environment variable
3. Routes the call to either `/voice` (traditional) or `/voice-realtime` (realtime)

Example:
- `REALTIME_API_PROBABILITY=0.5` → 50% chance of each mode
- `REALTIME_API_PROBABILITY=0.0` → Always traditional (0% realtime)
- `REALTIME_API_PROBABILITY=1.0` → Always realtime (100% realtime)
- `REALTIME_API_PROBABILITY=0.25` → 25% realtime, 75% traditional

### Traditional Mode (`/voice` endpoint)

**How it works:**
1. Twilio calls the endpoint
2. TwiML `<Say>` speaks greeting
3. `<Gather>` listens for user speech
4. Speech is transcribed by Twilio
5. Server sends transcription to GPT-4
6. GPT-4 response is converted to speech via `<Say>`
7. Loop continues

**Pros:**
- Cost-effective (standard GPT-4 pricing)
- Reliable and well-tested
- Simple architecture

**Cons:**
- Slight delays between turns
- Cannot interrupt AI mid-sentence
- Less natural conversation flow

### Realtime API Mode (`/voice-realtime` endpoint)

**How it works:**
1. Twilio calls the endpoint
2. TwiML `<Connect>` establishes Media Stream WebSocket
3. Server opens WebSocket to OpenAI Realtime API
4. Audio flows bidirectionally:
   - Twilio → Server → OpenAI (user speech)
   - OpenAI → Server → Twilio (AI speech)
5. Real-time voice activity detection (VAD)
6. Streaming audio in/out with μ-law encoding

**Pros:**
- Ultra-low latency (conversational)
- Natural interruptions (can cut off AI)
- More engaging conversations
- Better wake-up experience

**Cons:**
- More expensive (charged per audio minute)
- More complex implementation
- Requires WebSocket support
- Newer, less battle-tested

## Architecture Details

### WebSocket Bridge (`/media-stream`)

The Media Streams WebSocket endpoint acts as a bridge:

```
Twilio Phone Call
      ↕ (audio packets)
Media Streams WebSocket (/media-stream)
      ↕ (JSON messages)
OpenAI Realtime API (wss://api.openai.com/v1/realtime)
```

**Key Implementation Details:**

1. **Audio Format**: μ-law (g711_ulaw) 8kHz mono
2. **Encoding**: Base64-encoded audio chunks
3. **Bidirectional**: Two async tasks running concurrently
4. **VAD**: Server-side voice activity detection by OpenAI
5. **Interruption Handling**: When user speaks, clear Twilio buffer

### Configuration

```python
session_update = {
    "type": "session.update",
    "session": {
        "turn_detection": {"type": "server_vad"},  # Voice activity detection
        "input_audio_format": "g711_ulaw",         # Twilio format
        "output_audio_format": "g711_ulaw",        # Twilio format
        "voice": "alloy",                          # OpenAI voice
        "instructions": "...",                     # System prompt
        "modalities": ["text", "audio"],           # Enable audio
        "temperature": 0.8,                        # Creativity level
    }
}
```

## API Endpoints

### GET `/realtime-api-config`
Get current Realtime API probability configuration.

**Response:**
```json
{
  "probability": 0.5,
  "percentage": "50.0%",
  "description": "Probability of using OpenAI Realtime API vs Traditional API"
}
```

### POST `/realtime-api-config?probability=0.75`
Update the Realtime API probability at runtime.

**Parameters:**
- `probability` (float): Value between 0.0 and 1.0

**Response:**
```json
{
  "status": "updated",
  "probability": 0.75,
  "percentage": "75.0%"
}
```

### GET `/`
Root endpoint now includes Realtime API configuration in status.

**Response includes:**
```json
{
  "status": "Wake-up Coach is running",
  "realtime_api_probability": 0.5,
  "realtime_api_percentage": "50.0%",
  ...
}
```

## Cost Considerations

### Traditional Mode Costs
- GPT-4 text completion: ~$0.03 per 1K input tokens, ~$0.06 per 1K output tokens
- Typical 5-minute wake-up call: ~$0.10 - $0.30
- Twilio costs: ~$0.02/min
- **Total: ~$0.20 - $0.40 per call**

### Realtime API Mode Costs
- OpenAI Realtime API: ~$0.06 per minute (input) + ~$0.24 per minute (output)
- Typical 5-minute wake-up call: ~$1.50 (audio time)
- Twilio costs: ~$0.02/min
- **Total: ~$1.60 per call**

### Cost Optimization Strategies

1. **Start Conservative**: `REALTIME_API_PROBABILITY=0.1` (10%)
2. **Monitor Quality**: Check which mode wakes you better
3. **Adjust Gradually**: Increase if Realtime works better
4. **Peak Hours**: Use higher probability on hardest wake-up days
5. **Dynamic Adjustment**: Use API to change probability based on day of week

Example: Higher probability on Mondays
```bash
# Monday morning - need extra help
curl -X POST "http://your-server:8765/realtime-api-config?probability=0.8"

# Friday morning - easier to wake
curl -X POST "http://your-server:8765/realtime-api-config?probability=0.2"
```

## Testing

### Test Realtime API Directly
Make a test call and it will randomly select:
```bash
curl http://your-server:8765/test-call
```

Response includes which mode was used:
```json
{
  "status": "Test call initiated",
  "call_sid": "CA1234...",
  "using_realtime_api": true
}
```

### Force Traditional Mode
```bash
curl -X POST "http://your-server:8765/realtime-api-config?probability=0.0"
curl http://your-server:8765/test-call
```

### Force Realtime Mode
```bash
curl -X POST "http://your-server:8765/realtime-api-config?probability=1.0"
curl http://your-server:8765/test-call
```

## Troubleshooting

### Realtime API Connection Issues

**Problem**: WebSocket fails to connect to OpenAI

**Solutions:**
1. Verify OpenAI API key has Realtime API access
2. Check internet connectivity from server
3. Ensure no firewall blocking WebSocket connections
4. Check logs: `docker-compose logs -f`

### Audio Quality Issues

**Problem**: Choppy or garbled audio in Realtime mode

**Solutions:**
1. Check server CPU/memory resources
2. Verify network bandwidth (need consistent connection)
3. Test with Traditional mode to isolate issue
4. Check Twilio Media Streams status

### Fallback Behavior

If Realtime API fails:
- The `/voice-realtime` endpoint catches exceptions
- Automatically redirects to `/voice` (traditional mode)
- Call continues without interruption
- Error logged for debugging

## Future Enhancements

Potential improvements:
1. **Cost Tracking**: Log which mode was used per call for cost analysis
2. **Performance Metrics**: Track which mode results in better wake-up success
3. **Smart Selection**: ML-based selection based on historical success rates
4. **Time-Based Rules**: Different probabilities for different times/days
5. **Voice Cloning**: Use custom voices with Realtime API
6. **Conversation History**: Maintain context across multiple wake-up attempts

## References

- [OpenAI Realtime API Docs](https://platform.openai.com/docs/guides/realtime)
- [Twilio Media Streams Docs](https://www.twilio.com/docs/voice/media-streams)
- [Twilio + OpenAI Sample](https://github.com/twilio-samples/speech-assistant-openai-realtime-api-node)

