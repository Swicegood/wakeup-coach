#!/usr/bin/env python3
"""
WebSocket connectivity test script
Run this to test if WebSocket connections work to your server
"""

import asyncio
import websockets
import json
import sys

async def test_websocket_connection(url):
    """Test WebSocket connection"""
    print(f"Testing WebSocket connection to: {url}")
    print("-" * 60)
    
    try:
        print("Attempting to connect...")
        async with websockets.connect(url, timeout=10) as websocket:
            print("✓ Connected successfully!")
            
            # Wait for initial message
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"✓ Received initial message: {response}")
            except asyncio.TimeoutError:
                print("⚠ No initial message received (timeout)")
            
            # Send a test message
            test_message = "Hello from test script!"
            print(f"\nSending test message: {test_message}")
            await websocket.send(test_message)
            
            # Wait for echo response
            try:
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                print(f"✓ Received echo response: {response}")
            except asyncio.TimeoutError:
                print("⚠ No echo response received (timeout)")
            
            print("\n" + "=" * 60)
            print("SUCCESS: WebSocket connection is working!")
            print("=" * 60)
            return True
            
    except websockets.exceptions.InvalidStatusCode as e:
        print(f"✗ Invalid status code: {e}")
        print(f"  Server returned: {e.status_code}")
        print("\n  This might mean:")
        print("  - WebSocket endpoint doesn't exist")
        print("  - Server doesn't support WebSocket protocol")
        return False
        
    except websockets.exceptions.WebSocketException as e:
        print(f"✗ WebSocket error: {e}")
        return False
        
    except ConnectionRefusedError:
        print("✗ Connection refused")
        print("  Server is not accepting connections on this port")
        return False
        
    except asyncio.TimeoutError:
        print("✗ Connection timeout")
        print("  Could not connect within 10 seconds")
        print("  Check firewall or network connectivity")
        return False
        
    except Exception as e:
        print(f"✗ Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Main test function"""
    # Test local connection first
    local_url = "ws://localhost:8000/test-websocket"
    print("\n" + "=" * 60)
    print("Test 1: Local connection (within Docker container)")
    print("=" * 60)
    local_result = await test_websocket_connection(local_url)
    
    # Test external connection
    external_url = "ws://YOUR_DOMAIN:8765/test-websocket"
    print("\n" + "=" * 60)
    print("Test 2: External connection (as Twilio would see it)")
    print("=" * 60)
    external_result = await test_websocket_connection(external_url)
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Local connection:    {'✓ PASS' if local_result else '✗ FAIL'}")
    print(f"External connection: {'✓ PASS' if external_result else '✗ FAIL'}")
    print()
    
    if local_result and not external_result:
        print("DIAGNOSIS:")
        print("  Server works locally but not externally.")
        print("  Likely causes:")
        print("  - Port forwarding not configured for WebSocket")
        print("  - Reverse proxy blocking WebSocket connections")
        print("  - Firewall blocking WebSocket protocol")
        print()
        print("SOLUTIONS:")
        print("  1. Check your router/firewall allows port 8765")
        print("  2. If using reverse proxy (nginx/Apache), add WebSocket headers")
        print("  3. Test from external network: wscat -c ws://YOUR_DOMAIN:8765/test-websocket")
    elif not local_result:
        print("DIAGNOSIS:")
        print("  Server not responding to WebSocket connections at all.")
        print("  This shouldn't happen - check if server is running.")
    elif local_result and external_result:
        print("SUCCESS!")
        print("  WebSocket connections work both locally and externally.")
        print("  The issue with Twilio Media Streams might be different.")
        print()
        print("Next steps:")
        print("  1. Check Twilio debugger: https://console.twilio.com/monitor/logs/debugger")
        print("  2. Look for errors about Media Streams connection")
        print("  3. Verify BASE_URL in .env is correct")
    
    return external_result

if __name__ == "__main__":
    print("""
╔════════════════════════════════════════════════════════════════╗
║           Wake-up Coach WebSocket Connectivity Test           ║
╚════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)

