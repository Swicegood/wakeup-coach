# Doorbell Webhook Integration Setup

This guide explains how to set up the UniFi Protect doorbell webhook integration to require physical verification before magic words can end the wake-up call.

## How It Works

1. When you receive a wake-up call, magic words like "goodbye" or "end call" will be ignored
2. You must physically get out of bed and touch your G4 doorbell's fingerprint reader
3. UniFi Protect sends a webhook to the wake-up coach when fingerprint authentication occurs
4. Once the webhook is received, magic words are enabled for 5 minutes (configurable)
5. After 5 minutes, the doorbell activation expires and magic words are disabled again

## UniFi Protect Webhook Setup

### 1. Access UniFi Protect Webhook Settings

1. Open your UniFi Protect web interface
2. Go to **Settings** → **System** → **Webhooks**
3. Click **Add Webhook**

### 2. Configure the Webhook

- **Name**: `Wake-up Coach Doorbell`
- **URL**: `http://YOUR_SERVER_IP:8765/doorbell-webhook` (update with your server IP)
- **Method**: `POST`
- **Content Type**: `application/json`

### 3. Select Events

Enable the following events for your G4 doorbell:
- `Doorbell Fingerprint Authenticated`
- `Doorbell Fingerprint Success`
- `Doorbell Auth Success`

*Note: The exact event names may vary depending on your UniFi Protect version. You may need to test different event names.*

### 4. Test the Webhook

1. Start your wake-up coach application
2. Run the test script: `python test_doorbell.py`
3. Touch your doorbell's fingerprint reader
4. Check the logs to see if the webhook was received

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Doorbell activation timeout in seconds (default: 300 = 5 minutes)
DOORBELL_ACTIVATION_TIMEOUT=300
```

### API Endpoints

- `GET /doorbell-status` - Check current doorbell activation status
- `POST /activate-doorbell` - Manually activate doorbell (for testing)
- `POST /doorbell-webhook` - Receive webhooks from UniFi Protect

## Testing

### Manual Testing

1. Start a test call: `curl -X GET http://YOUR_SERVER_IP:8765/test-call`
2. Try saying "goodbye" - it should be ignored
3. Manually activate doorbell: `curl -X POST http://YOUR_SERVER_IP:8765/activate-doorbell`
4. Try saying "goodbye" again - it should now work

### Using the Test Script

```bash
python test_doorbell.py
```

## Troubleshooting

### Webhook Not Received

1. Check UniFi Protect webhook settings
2. Verify the webhook URL is accessible from your UniFi Protect server
3. Check the wake-up coach logs for webhook attempts
4. Test with the manual activation endpoint

### Wrong Event Types

The webhook handler looks for these event types:
- `doorbell.fingerprint.authenticated`
- `doorbell.fingerprint.success`
- `doorbell.auth.success`
- `fingerprint.authenticated`
- `auth.success`

If your UniFi Protect sends different event names, update the `fingerprint_events` list in `main.py`.

### Debugging

Check the application logs for:
- Webhook reception: `"Received doorbell webhook: {data}"`
- Fingerprint detection: `"Fingerprint authentication detected on device {device_id}"`
- Doorbell activation: `"Doorbell activated at {time} - magic words are now enabled"`

## Security Considerations

- The webhook endpoint is currently unauthenticated
- Consider adding authentication if your server is exposed to the internet
- The webhook URL should only be accessible from your local network

## Customization

### Different Timeout

Change the `DOORBELL_ACTIVATION_TIMEOUT` environment variable to adjust how long magic words remain enabled after doorbell activation.

### Different Magic Words

Modify the magic word detection in the `handle_response` function:

```python
if "goodbye" in user_speech or "end call" in user_speech or "your_custom_word" in user_speech:
```

### Different Doorbell Events

Update the `fingerprint_events` list in the `doorbell_webhook` function to match your UniFi Protect event names. 