from fastapi import FastAPI, HTTPException, Request, Response, Depends, WebSocket, WebSocketDisconnect
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Connect, Stream
from twilio.request_validator import RequestValidator
from openai import OpenAI
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime, timedelta
import pytz
from pydantic import BaseModel
import logging
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing import Optional
import json
import websockets
import base64
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("wakeup-coach")

# Load environment variables
load_dotenv()

app = FastAPI(title="Wake-up Coach")

# Initialize clients
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

# Initialize request validator
validator = RequestValidator(os.getenv("TWILIO_AUTH_TOKEN"))

# Initialize OpenAI client with the latest API version
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={
        "OpenAI-Beta": "assistants=v2"
    }
)

# Configuration
WAKE_UP_TIME = os.getenv("WAKE_UP_TIME", "06:00")  # Default to 6 AM
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
INTERNAL_PORT = os.getenv("PORT", "8000")
EXTERNAL_PORT = os.getenv("EXTERNAL_PORT", "8765")
SERVER_IP = os.getenv("SERVER_IP", "192.168.0.199")  # Your server's IP address
BASE_URL = os.getenv("BASE_URL", f"http://{SERVER_IP}:{EXTERNAL_PORT}")
DOORBELL_ACTIVATION_TIMEOUT = int(os.getenv("DOORBELL_ACTIVATION_TIMEOUT", "300"))  # 5 minutes default
REALTIME_API_PROBABILITY = float(os.getenv("REALTIME_API_PROBABILITY", "0.5"))  # 50% chance by default

# Log configuration
logger.info(f"Configuration loaded: WAKE_UP_TIME={WAKE_UP_TIME}, PHONE_NUMBER={PHONE_NUMBER}, TWILIO_PHONE_NUMBER={TWILIO_PHONE_NUMBER}")
logger.info(f"BASE_URL={BASE_URL}")
logger.info(f"DOORBELL_ACTIVATION_TIMEOUT={DOORBELL_ACTIVATION_TIMEOUT} seconds")
logger.info(f"REALTIME_API_PROBABILITY={REALTIME_API_PROBABILITY} ({REALTIME_API_PROBABILITY*100}% chance)")

# Store scheduled tasks
scheduled_tasks = {}
last_call_time = None  # Track when the last call was made
active_calls = {}  # Track active calls and their status

# Doorbell activation state
doorbell_activated = False
doorbell_activation_time = None
doorbell_timeout_task = None

class ScheduleRequest(BaseModel):
    minutes_from_now: int = 1

class CallStatus(BaseModel):
    CallSid: str
    CallStatus: str
    CallDuration: Optional[str] = None
    SpeechResult: Optional[str] = None

class DoorbellWebhook(BaseModel):
    """Model for UniFi Protect doorbell webhook data"""
    event_type: Optional[str] = None
    device_id: Optional[str] = None
    timestamp: Optional[str] = None
    # Add other fields as needed based on UniFi Protect webhook format

def should_use_realtime_api() -> bool:
    """Randomly decide whether to use Realtime API based on configured probability"""
    use_realtime = random.random() < REALTIME_API_PROBABILITY
    logger.info(f"Call routing decision: {'Realtime API' if use_realtime else 'Traditional API'}")
    return use_realtime

def get_voice_endpoint() -> str:
    """Get the appropriate voice endpoint based on random selection"""
    return "/voice-realtime" if should_use_realtime_api() else "/voice"

async def validate_twilio_request(request: Request) -> bool:
    """Validate that the request is coming from Twilio"""
    try:
        # When behind a reverse proxy (Caddy), we need to reconstruct the original URL
        # Get the X-Forwarded-Proto and X-Forwarded-Host headers set by Caddy
        forwarded_proto = request.headers.get('X-Forwarded-Proto', 'https')
        forwarded_host = request.headers.get('X-Forwarded-Host', request.headers.get('Host', ''))
        
        # Reconstruct the URL that Twilio originally called
        if forwarded_host:
            # Ensure the forwarded host includes the port if it's missing
            if ':' not in forwarded_host and forwarded_proto == 'https':
                # Add the default HTTPS port 8443 if missing
                forwarded_host = f"{forwarded_host}:8443"
            elif ':' not in forwarded_host and forwarded_proto == 'http':
                # Add the default HTTP port 80 if missing
                forwarded_host = f"{forwarded_host}:80"
            
            url = f"{forwarded_proto}://{forwarded_host}{request.url.path}"
            if request.url.query:
                url += f"?{request.url.query}"
        else:
            # Fallback to request URL
            url = str(request.url)
        
        logger.debug(f"Validating Twilio request for URL: {url}")
        
        # Get the X-Twilio-Signature header
        twilio_signature = request.headers.get('X-Twilio-Signature')
        if not twilio_signature:
            logger.warning("No X-Twilio-Signature header found")
            return False
            
        # Get the request body
        form_data = await request.form()
        params = dict(form_data)
        
        # Validate the request
        is_valid = validator.validate(url, params, twilio_signature)
        if not is_valid:
            logger.warning(f"Invalid Twilio signature for URL: {url}")
        return is_valid
    except Exception as e:
        logger.error(f"Error validating Twilio request: {str(e)}")
        return False

async def reset_doorbell_activation():
    """Reset doorbell activation after timeout"""
    global doorbell_activated, doorbell_activation_time, doorbell_timeout_task
    await asyncio.sleep(DOORBELL_ACTIVATION_TIMEOUT)
    doorbell_activated = False
    doorbell_activation_time = None
    doorbell_timeout_task = None
    logger.info("Doorbell activation timed out - magic words are now disabled")

def activate_doorbell():
    """Activate doorbell and start timeout timer"""
    global doorbell_activated, doorbell_activation_time, doorbell_timeout_task
    
    # Cancel existing timeout task if any
    if doorbell_timeout_task and not doorbell_timeout_task.done():
        doorbell_timeout_task.cancel()
    
    doorbell_activated = True
    doorbell_activation_time = datetime.now()
    doorbell_timeout_task = asyncio.create_task(reset_doorbell_activation())
    logger.info(f"Doorbell activated at {doorbell_activation_time.strftime('%Y-%m-%d %H:%M:%S')} - magic words are now enabled for {DOORBELL_ACTIVATION_TIMEOUT} seconds")

@app.post("/doorbell-webhook")
async def doorbell_webhook(request: Request):
    """Handle webhook from UniFi Protect doorbell"""
    try:
        # Get the request body
        body = await request.body()
        data = json.loads(body) if body else {}
        
        logger.info(f"Received doorbell webhook: {data}")
        
        # Check if this is a fingerprint authentication event
        # You'll need to adjust this based on the actual UniFi Protect webhook format
        event_type = data.get('event_type', '').lower()
        device_id = data.get('device_id', '')
        
        # Common UniFi Protect event types for doorbell authentication
        fingerprint_events = [
            'doorbell.fingerprint.authenticated',
            'doorbell.fingerprint.success',
            'doorbell.auth.success',
            'fingerprint.authenticated',
            'auth.success'
        ]
        
        if any(event in event_type for event in fingerprint_events):
            logger.info(f"Fingerprint authentication detected on device {device_id}")
            activate_doorbell()
            return {"status": "success", "message": "Doorbell activated"}
        else:
            logger.info(f"Non-fingerprint event received: {event_type}")
            return {"status": "ignored", "message": "Not a fingerprint event"}
            
    except Exception as e:
        logger.error(f"Error processing doorbell webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/realtime-api-config")
async def get_realtime_api_config():
    """Get current Realtime API configuration"""
    return {
        "probability": REALTIME_API_PROBABILITY,
        "percentage": f"{REALTIME_API_PROBABILITY * 100}%",
        "description": "Probability of using OpenAI Realtime API vs Traditional API"
    }

@app.post("/realtime-api-config")
async def update_realtime_api_config(probability: float):
    """Update Realtime API probability (0.0 to 1.0)"""
    global REALTIME_API_PROBABILITY
    
    if not 0.0 <= probability <= 1.0:
        raise HTTPException(status_code=400, detail="Probability must be between 0.0 and 1.0")
    
    REALTIME_API_PROBABILITY = probability
    logger.info(f"Realtime API probability updated to {REALTIME_API_PROBABILITY} ({REALTIME_API_PROBABILITY*100}%)")
    
    return {
        "status": "updated",
        "probability": REALTIME_API_PROBABILITY,
        "percentage": f"{REALTIME_API_PROBABILITY * 100}%"
    }

@app.get("/doorbell-status")
async def doorbell_status():
    """Get current doorbell activation status"""
    global doorbell_activated, doorbell_activation_time
    
    if doorbell_activated and doorbell_activation_time:
        time_remaining = DOORBELL_ACTIVATION_TIMEOUT - (datetime.now() - doorbell_activation_time).total_seconds()
        time_remaining = max(0, time_remaining)
        return {
            "activated": doorbell_activated,
            "activation_time": doorbell_activation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "time_remaining_seconds": int(time_remaining),
            "timeout_seconds": DOORBELL_ACTIVATION_TIMEOUT
        }
    else:
        return {
            "activated": False,
            "activation_time": None,
            "time_remaining_seconds": 0,
            "timeout_seconds": DOORBELL_ACTIVATION_TIMEOUT
        }

@app.get("/")
async def root():
    global doorbell_activated, doorbell_activation_time
    
    status_info = {
        "status": "Wake-up Coach is running",
        "doorbell_activated": doorbell_activated,
        "doorbell_timeout_seconds": DOORBELL_ACTIVATION_TIMEOUT,
        "realtime_api_probability": REALTIME_API_PROBABILITY,
        "realtime_api_percentage": f"{REALTIME_API_PROBABILITY * 100}%"
    }
    
    if doorbell_activated and doorbell_activation_time:
        time_remaining = DOORBELL_ACTIVATION_TIMEOUT - (datetime.now() - doorbell_activation_time).total_seconds()
        time_remaining = max(0, time_remaining)
        status_info.update({
            "activation_time": doorbell_activation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "time_remaining_seconds": int(time_remaining)
        })
    
    return status_info

@app.post("/activate-doorbell")
async def manual_activate_doorbell():
    """Manually activate doorbell for testing purposes"""
    activate_doorbell()
    return {"status": "success", "message": "Doorbell manually activated"}

@app.get("/websocket-status")
async def websocket_status():
    """Check if WebSocket endpoints are registered"""
    routes = []
    for route in app.routes:
        routes.append({
            "path": route.path if hasattr(route, 'path') else str(route),
            "type": type(route).__name__
        })
    return {
        "status": "Server is running",
        "websocket_support": "enabled",
        "routes": routes,
        "test_instructions": "Use a WebSocket client to connect to ws://goloka.no-ip.biz:8765/test-websocket"
    }

@app.websocket("/test-websocket")
async def test_websocket(websocket: WebSocket):
    """Test WebSocket connectivity"""
    try:
        await websocket.accept()
        logger.info("Test WebSocket connection accepted")
        await websocket.send_json({"status": "connected", "message": "WebSocket is working!"})
        
        # Echo back any messages received
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"Received test message: {data}")
                await websocket.send_json({"echo": data, "timestamp": datetime.now().isoformat()})
            except WebSocketDisconnect:
                logger.info("Test WebSocket disconnected")
                break
    except Exception as e:
        logger.error(f"Error in test WebSocket: {str(e)}", exc_info=True)

@app.get("/test-call")
async def test_call():
    """Test endpoint to initiate a call immediately"""
    try:
        voice_endpoint = get_voice_endpoint()
        logger.info(f"Initiating test call to {PHONE_NUMBER} from {TWILIO_PHONE_NUMBER} using {voice_endpoint}")
        call = twilio_client.calls.create(
            to=PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}{voice_endpoint}",
            status_callback=f"{BASE_URL}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        logger.info(f"Test call initiated with SID: {call.sid}")
        active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False, "endpoint": voice_endpoint}
        return {"status": "Test call initiated", "call_sid": call.sid, "using_realtime_api": voice_endpoint == "/voice-realtime"}
    except Exception as e:
        logger.error(f"Error initiating test call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-call-realtime")
async def test_call_realtime():
    """Test endpoint to force a Realtime API call"""
    try:
        voice_endpoint = "/voice-realtime"
        logger.info(f"Initiating FORCED Realtime API test call to {PHONE_NUMBER} from {TWILIO_PHONE_NUMBER}")
        call = twilio_client.calls.create(
            to=PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}{voice_endpoint}",
            status_callback=f"{BASE_URL}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        logger.info(f"Realtime API test call initiated with SID: {call.sid}")
        active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False, "endpoint": voice_endpoint}
        return {"status": "Realtime API test call initiated", "call_sid": call.sid, "using_realtime_api": True}
    except Exception as e:
        logger.error(f"Error initiating Realtime API test call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-call-traditional")
async def test_call_traditional():
    """Test endpoint to force a Traditional API call"""
    try:
        voice_endpoint = "/voice"
        logger.info(f"Initiating FORCED Traditional API test call to {PHONE_NUMBER} from {TWILIO_PHONE_NUMBER}")
        call = twilio_client.calls.create(
            to=PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}{voice_endpoint}",
            status_callback=f"{BASE_URL}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        logger.info(f"Traditional API test call initiated with SID: {call.sid}")
        active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False, "endpoint": voice_endpoint}
        return {"status": "Traditional API test call initiated", "call_sid": call.sid, "using_realtime_api": False}
    except Exception as e:
        logger.error(f"Error initiating Traditional API test call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/schedule-test")
async def schedule_test(request: ScheduleRequest):
    """Schedule a test call for a specific time in the future"""
    try:
        minutes = request.minutes_from_now
        if minutes < 1:
            minutes = 1  # Ensure at least 1 minute
        
        # Calculate when the call should be made
        now = datetime.now(pytz.timezone(os.getenv("TZ", "America/New_York")))
        scheduled_time = now + timedelta(minutes=minutes)
        
        # Create a task to make the call after the specified delay
        task_id = f"test_call_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        async def delayed_call():
            await asyncio.sleep(minutes * 60)  # Convert minutes to seconds
            try:
                voice_endpoint = get_voice_endpoint()
                logger.info(f"Making scheduled call to {PHONE_NUMBER} from {TWILIO_PHONE_NUMBER} using {voice_endpoint}")
                call = twilio_client.calls.create(
                    to=PHONE_NUMBER,
                    from_=TWILIO_PHONE_NUMBER,
                    url=f"{BASE_URL}{voice_endpoint}",
                    status_callback=f"{BASE_URL}/call-status",
                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                    status_callback_method='POST'
                )
                logger.info(f"Scheduled test call made at {datetime.now()} with SID: {call.sid}")
                active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False, "endpoint": voice_endpoint}
                if task_id in scheduled_tasks:
                    del scheduled_tasks[task_id]
            except Exception as e:
                logger.error(f"Error making scheduled call: {str(e)}")
        
        # Store the task
        scheduled_tasks[task_id] = asyncio.create_task(delayed_call())
        logger.info(f"Test call scheduled for {scheduled_time.strftime('%Y-%m-%d %H:%M:%S')} with task_id: {task_id}")
        
        return {
            "status": "Test call scheduled",
            "scheduled_time": scheduled_time.strftime("%Y-%m-%d %H:%M:%S"),
            "task_id": task_id
        }
    except Exception as e:
        logger.error(f"Error scheduling test call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cancel-scheduled/{task_id}")
async def cancel_scheduled(task_id: str):
    """Cancel a scheduled test call"""
    if task_id in scheduled_tasks:
        scheduled_tasks[task_id].cancel()
        del scheduled_tasks[task_id]
        logger.info(f"Scheduled call cancelled: {task_id}")
        return {"status": "Scheduled call cancelled", "task_id": task_id}
    else:
        logger.warning(f"Attempted to cancel non-existent task: {task_id}")
        raise HTTPException(status_code=404, detail="Task not found")

@app.get("/list-scheduled")
async def list_scheduled():
    """List all scheduled test calls"""
    logger.info(f"Listing scheduled tasks: {list(scheduled_tasks.keys())}")
    return {
        "scheduled_tasks": list(scheduled_tasks.keys())
    }

@app.post("/call")
async def initiate_call():
    """Initiate a wake-up call"""
    try:
        voice_endpoint = get_voice_endpoint()
        logger.info(f"Initiating wake-up call to {PHONE_NUMBER} from {TWILIO_PHONE_NUMBER} using {voice_endpoint}")
        call = twilio_client.calls.create(
            to=PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}{voice_endpoint}",
            status_callback=f"{BASE_URL}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        logger.info(f"Wake-up call initiated with SID: {call.sid}")
        active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False, "endpoint": voice_endpoint}
        return {"status": "Call initiated", "call_sid": call.sid, "using_realtime_api": voice_endpoint == "/voice-realtime"}
    except Exception as e:
        logger.error(f"Error initiating wake-up call: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/call-status")
async def call_status(request: Request):
    """Handle call status updates from Twilio"""
    try:
        # Validate the request is from Twilio
        if not await validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid request signature")
        
        form_data = await request.form()
        call_sid = form_data.get('CallSid')
        call_status = form_data.get('CallStatus')
        
        logger.info(f"Call status update: {call_sid} - {call_status}")
        
        # Update call status in our tracking
        if call_sid in active_calls:
            active_calls[call_sid]["status"] = call_status
        else:
            active_calls[call_sid] = {"status": call_status, "magic_words_spoken": False}
        
        # If call is completed and magic words weren't spoken, call back
        if call_status == "completed" and call_sid in active_calls and not active_calls[call_sid].get("magic_words_spoken", False):
            logger.info(f"Call {call_sid} ended without magic words. Calling back...")
            # Wait a short time before calling back
            await asyncio.sleep(5)
            try:
                voice_endpoint = get_voice_endpoint()
                logger.info(f"Calling back using {voice_endpoint}")
                new_call = twilio_client.calls.create(
                    to=PHONE_NUMBER,
                    from_=TWILIO_PHONE_NUMBER,
                    url=f"{BASE_URL}{voice_endpoint}",
                    status_callback=f"{BASE_URL}/call-status",
                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                    status_callback_method='POST'
                )
                logger.info(f"Call back initiated with SID: {new_call.sid}")
                active_calls[new_call.sid] = {"status": "initiated", "magic_words_spoken": False, "endpoint": voice_endpoint}
            except Exception as e:
                logger.error(f"Error calling back: {str(e)}")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error handling call status: {str(e)}")
        return {"status": "error", "message": str(e)}

@app.post("/voice")
async def handle_call(request: Request):
    """Handle the voice call and generate response"""
    logger.info("Handling incoming voice call")
    try:
        # Validate the request is from Twilio
        if not await validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid request signature")
            
        response = VoiceResponse()
        
        # Initial greeting
        response.say("Good morning! Time to wake up. How are you feeling?")
        
        # Gather user's response
        gather = Gather(
            input='speech',
            action='/handle-response',
            method='POST',
            language='en-US',
            speechTimeout='auto',
            timeout=5  # 5 seconds before timeout
        )
        response.append(gather)
        
        # Add a redirect for timeout
        response.redirect('/check-sleeping')
        
        # Return the response with the correct content type
        logger.info("Returning TwiML response for voice call")
        return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error handling voice call: {str(e)}")
        # Return a simple response in case of error
        response = VoiceResponse()
        response.say("I'm sorry, I encountered an error. Let's try again.")
        return Response(content=str(response), media_type="application/xml")

@app.post("/voice-realtime")
async def handle_call_realtime(request: Request):
    """Handle voice call using OpenAI Realtime API with Media Streams"""
    logger.info("Handling incoming voice call with Realtime API")
    try:
        # Validate the request is from Twilio
        if not await validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid request signature")
            
        response = VoiceResponse()
        
        # Initial greeting for Realtime API
        response.say("Good morning! Connecting you to your wake-up coach.")
        
        # Connect to Media Stream
        # Twilio Media Streams may require the actual domain name, not IP
        # Use wss:// for WebSocket Secure if your server supports it, otherwise ws://
        ws_url = BASE_URL.replace("http://", "ws://").replace("https://", "wss://")
        stream_url = f"{ws_url}/media-stream"
        
        logger.info(f"Creating Media Stream with URL: {stream_url}")
        logger.info(f"BASE_URL is: {BASE_URL}")
        
        connect = Connect()
        stream = Stream(url=stream_url)
        connect.append(stream)
        response.append(connect)
        
        # Return the response with the correct content type
        logger.info("Returning TwiML response for Realtime API voice call")
        twiml_str = str(response)
        logger.info(f"TwiML: {twiml_str}")
        return Response(content=twiml_str, media_type="application/xml")
    except Exception as e:
        logger.error(f"Error handling Realtime API voice call: {str(e)}")
        # Fallback to regular voice endpoint
        response = VoiceResponse()
        response.say("I'm sorry, I encountered an error. Let me connect you differently.")
        response.redirect('/voice')
        return Response(content=str(response), media_type="application/xml")

@app.websocket("/media-stream")
async def media_stream(websocket: WebSocket):
    """Handle Twilio Media Streams WebSocket connection and bridge to OpenAI Realtime API"""
    logger.info("=" * 80)
    logger.info("MEDIA STREAM WEBSOCKET ENDPOINT HIT!")
    logger.info(f"Client: {websocket.client}")
    logger.info(f"Headers: {websocket.headers}")
    logger.info("=" * 80)
    
    try:
        logger.info("Attempting to accept WebSocket connection...")
        await websocket.accept()
        logger.info("✓✓✓ Media Stream WebSocket connection ACCEPTED from Twilio ✓✓✓")
    except Exception as e:
        logger.error(f"✗✗✗ Failed to accept WebSocket connection: {str(e)}")
        logger.error(f"Error type: {type(e).__name__}", exc_info=True)
        return
    
    openai_ws = None
    stream_sid = None
    call_sid = None
    goodbye_timeout_task = None
    goodbye_detected = False
    
    async def end_call_after_timeout():
        """End the call after a timeout period"""
        nonlocal goodbye_detected
        await asyncio.sleep(12)  # Wait 12 seconds for goodbye to be heard
        if goodbye_detected and doorbell_activated:
            logger.info("⏰ Timeout reached - ending call")
            try:
                await websocket.send_json({
                    "event": "stop",
                    "streamSid": stream_sid
                })
                logger.info("📞 Sent stop event to Twilio to end call")
            except Exception as e:
                logger.error(f"Error sending stop event: {str(e)}")
    
    try:
        logger.info("Attempting to connect to OpenAI Realtime API...")
        # Connect to OpenAI Realtime API
        # Use additional_headers for newer websockets library
        openai_ws = await websockets.connect(
            'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01',
            additional_headers={
                "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                "OpenAI-Beta": "realtime=v1"
            }
        )
        logger.info("Connected to OpenAI Realtime API")
        
        # Configure the Realtime API session
        session_update = {
            "type": "session.update",
            "session": {
                "turn_detection": {"type": "server_vad"},
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "voice": "alloy",
                "instructions": (
                    "You are a supportive wake-up coach calling to help someone wake up. "
                    "Your goal is to help them wake up gently and start their day positively. "
                    "Keep responses brief and encouraging. If they seem sleepy, engage them actively. "
                    "Be conversational and warm. "
                    "IMPORTANT: The user must physically get out of bed and touch their "
                    "doorbell fingerprint reader before they can end the call. "
                    "When the user says they want to end the call or says goodbye, you should: "
                    "1. If the doorbell has NOT been activated, tell them they need to get out of bed and touch the doorbell first. "
                    "2. If the doorbell HAS been activated, say a brief goodbye like 'Great job getting up! Have a wonderful day!' and then END THE CONVERSATION IMMEDIATELY. "
                    "You will know the doorbell has been activated when the user mentions they've touched it or gotten out of bed."
                ),
                "modalities": ["audio"],
                "temperature": 0.8,
            }
        }
        await openai_ws.send(json.dumps(session_update))
        logger.info("OpenAI Realtime API session configured")
        
        # Send initial conversation item to have AI speak first
        initial_item = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Greet the user warmly and ask how they're feeling this morning."
                    }
                ]
            }
        }
        await openai_ws.send(json.dumps(initial_item))
        await openai_ws.send(json.dumps({"type": "response.create"}))
        logger.info("Initial greeting sent to OpenAI")
        
        async def receive_from_twilio():
            """Receive audio from Twilio and send to OpenAI"""
            nonlocal stream_sid, call_sid
            try:
                async for message in websocket.iter_text():
                    data = json.loads(message)
                    
                    if data['event'] == 'start':
                        stream_sid = data['start']['streamSid']
                        call_sid = data['start']['callSid']
                        logger.info(f"Stream started: {stream_sid}, Call: {call_sid}")
                        
                    elif data['event'] == 'media':
                        # Forward audio to OpenAI
                        audio_append = {
                            "type": "input_audio_buffer.append",
                            "audio": data['media']['payload']
                        }
                        await openai_ws.send(json.dumps(audio_append))
                        
                    elif data['event'] == 'stop':
                        logger.info(f"Stream stopped: {stream_sid}")
                        break
                        
            except WebSocketDisconnect:
                logger.info("Twilio WebSocket disconnected")
            except Exception as e:
                logger.error(f"Error receiving from Twilio: {str(e)}")
        
        async def receive_from_openai():
            """Receive audio from OpenAI and send to Twilio"""
            try:
                async for message in openai_ws:
                    data = json.loads(message)
                    
                    # Log ALL OpenAI events to debug audio processing
                    event_type = data.get('type', 'unknown')
                    logger.info(f"🤖 OpenAI Event: {event_type}")
                    if event_type in ['response.audio.delta', 'response.done', 'error', 'session.updated']:
                        logger.info(f"🤖 OpenAI Event Details: {data}")
                    
                    if data.get('type') == 'response.audio.delta':
                        # Send audio chunk to Twilio
                        media_message = {
                            "event": "media",
                            "streamSid": stream_sid,
                            "media": {
                                "payload": data['delta']
                            }
                        }
                        await websocket.send_json(media_message)
                        
                    elif data.get('type') == 'input_audio_buffer.speech_started':
                        # User started speaking, clear buffer
                        logger.info("User speech detected, clearing buffer")
                        
                        # Check if doorbell is activated and start timeout if user might be saying goodbye
                        if doorbell_activated and not goodbye_detected:
                            logger.info("🚨 User speaking with doorbell activated - starting goodbye timeout")
                            goodbye_detected = True
                            goodbye_timeout_task = asyncio.create_task(end_call_after_timeout())
                        
                        await websocket.send_json({
                            "event": "clear",
                            "streamSid": stream_sid
                        })
                        
                    elif data.get('type') == 'response.done':
                        # AI response completed
                        logger.info("🤖 AI Response completed")
                                
                    elif data.get('type') == 'error':
                        logger.error(f"OpenAI error: {data}")
                        
            except websockets.exceptions.ConnectionClosed:
                logger.info("OpenAI WebSocket connection closed")
            except Exception as e:
                logger.error(f"Error receiving from OpenAI: {str(e)}")
        
        # Run both directions concurrently
        await asyncio.gather(
            receive_from_twilio(),
            receive_from_openai()
        )
        
    except Exception as e:
        logger.error(f"Error in media stream: {str(e)}", exc_info=True)
        # Try to send error to Twilio
        try:
            await websocket.send_json({
                "event": "stop",
                "streamSid": stream_sid
            })
        except:
            pass
    finally:
        if openai_ws:
            try:
                await openai_ws.close()
                logger.info("OpenAI WebSocket closed")
            except:
                pass
        try:
            await websocket.close()
            logger.info("Twilio WebSocket closed")
        except:
            pass
        logger.info("Media Stream WebSocket connection fully closed")

@app.post("/handle-response")
async def handle_response(request: Request):
    """Process user's response and generate AI response"""
    try:
        # Validate the request is from Twilio
        if not await validate_twilio_request(request):
            raise HTTPException(status_code=403, detail="Invalid request signature")
            
        form_data = await request.form()
        user_speech = form_data.get('SpeechResult', '').lower()
        call_sid = form_data.get('CallSid')
        logger.info(f"Received speech input: {user_speech}")
        
        # Check if user wants to end the call with magic words
        if "goodbye" in user_speech or "end call" in user_speech:
            # Check if doorbell has been activated
            if not doorbell_activated:
                logger.info("Magic words spoken but doorbell not activated - ignoring")
                response = VoiceResponse()
                response.say("I heard you say goodbye, but you need to get out of bed and touch your doorbell first. Come on, you can do it!")
                
                # Add another gather for continued conversation
                gather = Gather(
                    input='speech',
                    action='/handle-response',
                    method='POST',
                    language='en-US',
                    speechTimeout='auto',
                    timeout=5  # 5 seconds before timeout
                )
                response.append(gather)
                response.redirect('/check-sleeping')
                return Response(content=str(response), media_type="application/xml")
            else:
                # Doorbell is activated, allow magic words to work
                logger.info("Magic words spoken with doorbell activated - ending call")
                if call_sid in active_calls:
                    active_calls[call_sid]["magic_words_spoken"] = True
                
                response = VoiceResponse()
                response.say("Great job getting out of bed! Goodbye and have a wonderful day!")
                return Response(content=str(response), media_type="application/xml")
        
        # Generate AI response using OpenAI
        try:
            # Create a chat completion with the latest API
            logger.info("Generating AI response using OpenAI")
            
            # Add doorbell context to the AI response
            system_message = "You are a supportive wake-up coach. Your goal is to help the user wake up gently and start their day positively. Keep responses brief and encouraging. If the user seems sleepy, try to engage them more actively."
            
            if not doorbell_activated:
                system_message += " IMPORTANT: The user must physically get out of bed and touch their doorbell fingerprint reader before they can end the call with magic words. Encourage them to do this if they mention wanting to end the call."
            
            completion = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": system_message
                    },
                    {
                        "role": "user",
                        "content": user_speech
                    }
                ],
                max_tokens=150  # Limit response length for voice
            )
            
            ai_response = completion.choices[0].message.content
            logger.info(f"AI response generated: {ai_response}")
            
            response = VoiceResponse()
            response.say(ai_response)
            
            # Add another gather for continued conversation
            gather = Gather(
                input='speech',
                action='/handle-response',
                method='POST',
                language='en-US',
                speechTimeout='auto',
                timeout=5  # 5 seconds before timeout
            )
            response.append(gather)
            
            # Add a redirect for timeout
            response.redirect('/check-sleeping')
            
            # Return the response with the correct content type
            logger.info("Returning TwiML response for user input")
            return Response(content=str(response), media_type="application/xml")
        except Exception as e:
            logger.error(f"Error generating AI response: {str(e)}")
            # If there's an error, return a simple response
            response = VoiceResponse()
            response.say("I'm sorry, I encountered an error. Let's try again.")
            gather = Gather(
                input='speech',
                action='/handle-response',
                method='POST',
                language='en-US',
                speechTimeout='auto',
                timeout=5  # 5 seconds before timeout
            )
            response.append(gather)
            response.redirect('/check-sleeping')
            return Response(content=str(response), media_type="application/xml")
    except Exception as e:
        logger.error(f"Error handling user response: {str(e)}")
        # Return a simple response in case of error
        response = VoiceResponse()
        response.say("I'm sorry, I encountered an error. Let's try again.")
        return Response(content=str(response), media_type="application/xml")

@app.post("/check-sleeping")
async def check_sleeping(request: Request):
    """Handle timeout by checking if user is sleeping"""
    # Validate the request is from Twilio
    if not await validate_twilio_request(request):
        raise HTTPException(status_code=403, detail="Invalid request signature")
        
    response = VoiceResponse()
    response.say("Are you sleeping?")
    
    # Gather response after sleep check
    gather = Gather(
        input='speech',
        action='/handle-response',
        method='POST',
        language='en-US',
        speechTimeout='auto',
        timeout=5  # 5 seconds before timeout
    )
    response.append(gather)
    
    return Response(content=str(response), media_type="application/xml")

async def check_wake_up_time():
    """Check if it's time for the wake-up call and make the call if needed"""
    global last_call_time
    while True:
        try:
            # Get current time in the configured timezone
            tz = pytz.timezone(os.getenv("TZ", "America/New_York"))
            now = datetime.now(tz)
            
            # Parse wake-up time
            wake_up_hour, wake_up_minute = map(int, WAKE_UP_TIME.split(":"))
            
            # Check if it's time for the wake-up call and enough time has passed since last call
            if (now.hour == wake_up_hour and now.minute == wake_up_minute and 
                (last_call_time is None or (now - last_call_time).total_seconds() > 3600)):  # 1 hour cooldown
                logger.info(f"It's {WAKE_UP_TIME}! Making wake-up call to {PHONE_NUMBER}")
                try:
                    voice_endpoint = get_voice_endpoint()
                    logger.info(f"Using {voice_endpoint} for wake-up call")
                    call = twilio_client.calls.create(
                        to=PHONE_NUMBER,
                        from_=TWILIO_PHONE_NUMBER,
                        url=f"{BASE_URL}{voice_endpoint}",
                        status_callback=f"{BASE_URL}/call-status",
                        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                        status_callback_method='POST'
                    )
                    last_call_time = now
                    logger.info(f"Wake-up call initiated with SID: {call.sid}")
                    active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False, "endpoint": voice_endpoint}
                except Exception as e:
                    logger.error(f"Error making wake-up call: {str(e)}")
            
            # Sleep for 30 seconds before checking again
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Error in wake-up time checker: {str(e)}")
            await asyncio.sleep(30)

@app.on_event("startup")
async def startup_event():
    """Start the wake-up time checker when the application starts"""
    asyncio.create_task(check_wake_up_time())
    logger.info("Wake-up time checker started")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(INTERNAL_PORT),
        # WebSocket configuration
        ws="auto",  # Auto-detect WebSocket library (websockets or wsproto)
        ws_max_size=16777216,  # 16MB max WebSocket message size
        timeout_keep_alive=300,  # 5 minutes keep-alive for long conversations
        log_level="info"  # Ensure we see WebSocket connection logs
    ) 