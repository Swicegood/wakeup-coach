from fastapi import FastAPI, HTTPException, Request, Response, Depends
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
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
SERVER_IP = os.getenv("SERVER_IP", "YOUR_SERVER_IP")  # Your server's IP address
BASE_URL = os.getenv("BASE_URL", f"http://{SERVER_IP}:{EXTERNAL_PORT}")

# Log configuration
logger.info(f"Configuration loaded: WAKE_UP_TIME={WAKE_UP_TIME}, PHONE_NUMBER={PHONE_NUMBER}, TWILIO_PHONE_NUMBER={TWILIO_PHONE_NUMBER}")
logger.info(f"BASE_URL={BASE_URL}")

# Store scheduled tasks
scheduled_tasks = {}
last_call_time = None  # Track when the last call was made
active_calls = {}  # Track active calls and their status

class ScheduleRequest(BaseModel):
    minutes_from_now: int = 1

class CallStatus(BaseModel):
    CallSid: str
    CallStatus: str
    CallDuration: Optional[str] = None
    SpeechResult: Optional[str] = None

async def validate_twilio_request(request: Request) -> bool:
    """Validate that the request is coming from Twilio"""
    try:
        # Get the full URL
        url = str(request.url)
        
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
            logger.warning("Invalid Twilio signature")
        return is_valid
    except Exception as e:
        logger.error(f"Error validating Twilio request: {str(e)}")
        return False

@app.get("/")
async def root():
    return {"status": "Wake-up Coach is running"}

@app.get("/test-call")
async def test_call():
    """Test endpoint to initiate a call immediately"""
    try:
        logger.info(f"Initiating test call to {PHONE_NUMBER} from {TWILIO_PHONE_NUMBER}")
        call = twilio_client.calls.create(
            to=PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}/voice",
            status_callback=f"{BASE_URL}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        logger.info(f"Test call initiated with SID: {call.sid}")
        active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False}
        return {"status": "Test call initiated", "call_sid": call.sid}
    except Exception as e:
        logger.error(f"Error initiating test call: {str(e)}")
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
                logger.info(f"Making scheduled call to {PHONE_NUMBER} from {TWILIO_PHONE_NUMBER}")
                call = twilio_client.calls.create(
                    to=PHONE_NUMBER,
                    from_=TWILIO_PHONE_NUMBER,
                    url=f"{BASE_URL}/voice",
                    status_callback=f"{BASE_URL}/call-status",
                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                    status_callback_method='POST'
                )
                logger.info(f"Scheduled test call made at {datetime.now()} with SID: {call.sid}")
                active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False}
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
        logger.info(f"Initiating wake-up call to {PHONE_NUMBER} from {TWILIO_PHONE_NUMBER}")
        call = twilio_client.calls.create(
            to=PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{BASE_URL}/voice",
            status_callback=f"{BASE_URL}/call-status",
            status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
            status_callback_method='POST'
        )
        logger.info(f"Wake-up call initiated with SID: {call.sid}")
        active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False}
        return {"status": "Call initiated", "call_sid": call.sid}
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
                new_call = twilio_client.calls.create(
                    to=PHONE_NUMBER,
                    from_=TWILIO_PHONE_NUMBER,
                    url=f"{BASE_URL}/voice",
                    status_callback=f"{BASE_URL}/call-status",
                    status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                    status_callback_method='POST'
                )
                logger.info(f"Call back initiated with SID: {new_call.sid}")
                active_calls[new_call.sid] = {"status": "initiated", "magic_words_spoken": False}
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
            # Mark that magic words were spoken
            if call_sid in active_calls:
                active_calls[call_sid]["magic_words_spoken"] = True
            
            response = VoiceResponse()
            response.say("Goodbye! Have a great day!")
            return Response(content=str(response), media_type="application/xml")
        
        # Generate AI response using OpenAI
        try:
            # Create a chat completion with the latest API
            logger.info("Generating AI response using OpenAI")
            completion = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a supportive wake-up coach. Your goal is to help the user wake up gently and start their day positively. Keep responses brief and encouraging. If the user seems sleepy, try to engage them more actively."
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
                    call = twilio_client.calls.create(
                        to=PHONE_NUMBER,
                        from_=TWILIO_PHONE_NUMBER,
                        url=f"{BASE_URL}/voice",
                        status_callback=f"{BASE_URL}/call-status",
                        status_callback_event=['initiated', 'ringing', 'answered', 'completed'],
                        status_callback_method='POST'
                    )
                    last_call_time = now
                    logger.info(f"Wake-up call initiated with SID: {call.sid}")
                    active_calls[call.sid] = {"status": "initiated", "magic_words_spoken": False}
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
    uvicorn.run(app, host="0.0.0.0", port=int(INTERNAL_PORT)) 