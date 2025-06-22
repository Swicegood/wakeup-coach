#!/usr/bin/env python3
"""
Test script for doorbell webhook integration
"""

import requests
import json
import time

# Configuration
BASE_URL = "http://YOUR_SERVER_IP:8765"  # Update with your server URL

def test_doorbell_status():
    """Test the doorbell status endpoint"""
    print("Testing doorbell status...")
    try:
        response = requests.get(f"{BASE_URL}/doorbell-status")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def test_manual_activation():
    """Test manual doorbell activation"""
    print("\nTesting manual doorbell activation...")
    try:
        response = requests.post(f"{BASE_URL}/activate-doorbell")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def test_doorbell_webhook():
    """Test the doorbell webhook endpoint"""
    print("\nTesting doorbell webhook...")
    
    # Sample webhook data (adjust based on actual UniFi Protect format)
    webhook_data = {
        "event_type": "doorbell.fingerprint.authenticated",
        "device_id": "test_device_123",
        "timestamp": "2024-01-01T12:00:00Z"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/doorbell-webhook",
            json=webhook_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def test_root_endpoint():
    """Test the root endpoint to see overall status"""
    print("\nTesting root endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"Status: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

def main():
    print("Doorbell Integration Test Script")
    print("=" * 40)
    
    # Test initial status
    test_root_endpoint()
    test_doorbell_status()
    
    # Test manual activation
    test_manual_activation()
    time.sleep(1)
    
    # Check status after activation
    test_doorbell_status()
    
    # Test webhook
    test_doorbell_webhook()
    time.sleep(1)
    
    # Check status after webhook
    test_doorbell_status()
    
    print("\nTest completed!")

if __name__ == "__main__":
    main() 