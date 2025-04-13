from fastapi import FastAPI, HTTPException, Request
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather
from openai import OpenAI
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime
import pytz

# Load environment variables
load_dotenv()

app = FastAPI(title="Wake-up Coach")

# Initialize clients
twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

# Initialize OpenAI client with the latest API version
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    default_headers={
        "OpenAI-Beta": "assistants=v2"
    }
)

# Configuration
WAKE_UP_TIME = os.getenv("WAKE_UP_TIME", "07:00")  # Default to 7 AM
PHONE_NUMBER = os.getenv("PHONE_NUMBER")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

@app.get("/")
async def root():
    return {"status": "Wake-up Coach is running"}

@app.get("/test-call")
async def test_call():
    """Test endpoint to initiate a call immediately"""
    try:
        call = twilio_client.calls.create(
            to=PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{os.getenv('BASE_URL')}/voice"
        )
        return {"status": "Test call initiated", "call_sid": call.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/call")
async def initiate_call():
    """Initiate a wake-up call"""
    try:
        call = twilio_client.calls.create(
            to=PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{os.getenv('BASE_URL')}/voice"
        )
        return {"status": "Call initiated", "call_sid": call.sid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/voice")
async def handle_call():
    """Handle the voice call and generate response"""
    response = VoiceResponse()
    
    # Initial greeting
    response.say("Good morning! Time to wake up. How are you feeling?")
    
    # Gather user's response
    gather = Gather(
        input='speech',
        action='/handle-response',
        method='POST',
        language='en-US',
        speechTimeout='auto'
    )
    response.append(gather)
    
    return str(response)

@app.post("/handle-response")
async def handle_response(request: Request):
    """Process user's response and generate AI response"""
    form_data = await request.form()
    user_speech = form_data.get('SpeechResult', '')
    
    # Generate AI response using OpenAI
    try:
        # Create a chat completion with the latest API
        completion = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a supportive wake-up coach. Your goal is to help the user wake up gently and start their day positively. Keep responses brief and encouraging."
                },
                {
                    "role": "user",
                    "content": user_speech
                }
            ],
            max_tokens=150  # Limit response length for voice
        )
        
        ai_response = completion.choices[0].message.content
        
        response = VoiceResponse()
        response.say(ai_response)
        
        # Add another gather for continued conversation
        gather = Gather(
            input='speech',
            action='/handle-response',
            method='POST',
            language='en-US',
            speechTimeout='auto'
        )
        response.append(gather)
        
        return str(response)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 