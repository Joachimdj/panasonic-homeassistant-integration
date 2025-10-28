#!/usr/bin/env python3
"""Test script to verify real JSON data extraction from aioaquarea."""

import asyncio
import logging
import sys
import os

# Add the custom component path to sys.path
sys.path.insert(0, '/Users/joachimdittman/Documents/HASS home/HACS/panasonic-homeassistant-integration')

# Enable debug logging to see all messages
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def test_real_data_extraction():
    """Test the real data extraction functionality."""
    
    # Import after setting up logging
    try:
        from aioaquarea import Client, AquareaEnvironment
        print("✓ Successfully imported aioaquarea")
    except ImportError as e:
        print(f"✗ Failed to import aioaquarea: {e}")
        return
    
    # Test credentials (you may need to update these)
    username = "joachim@dittman.dk"
    password = "Test0001"
    
    try:
        # Create client and connect
        client = Client(username, password, AquareaEnvironment.PRODUCTION)
        print("✓ Created aioaquarea client")
        
        # Get devices
        devices_info = await client.get_devices()
        print(f"✓ Found {len(devices_info)} devices")
        
        if not devices_info:
            print("✗ No devices found")
            return
            
        # Get first device
        device_info = devices_info[0]
        device_id = device_info.device_id
        print(f"✓ Testing device: {device_id}")
        
        # Get device object
        device = await client.get_device(device_info)
        print(f"✓ Got device object: {type(device)}")
        
        # Log all device attributes
        device_attrs = [attr for attr in dir(device) if not attr.startswith('__')]
        print(f"Device attributes: {device_attrs}")
        
        # Try to get status/refresh data
        if hasattr(device, 'refresh'):
            print("Calling device.refresh()...")
            await device.refresh()
            print("✓ Called device.refresh()")
        
        # Check for any data attributes
        data_attrs = ['_data', 'data', '_raw_data', 'raw_data', '_response', 'response',
                     '_last_response', 'last_response', '_json', 'json']
        
        for attr in data_attrs:
            if hasattr(device, attr):
                value = getattr(device, attr)
                print(f"device.{attr} = {value} (type: {type(value)})")
        
        # Check client attributes too
        if hasattr(device, '_client'):
            client_obj = device._client
            client_attrs = [attr for attr in dir(client_obj) if not attr.startswith('__')]
            print(f"Client attributes: {client_attrs}")
            
            for attr in data_attrs:
                if hasattr(client_obj, attr):
                    value = getattr(client_obj, attr)
                    print(f"client.{attr} = {value} (type: {type(value)})")
        
        print("✓ Test completed")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_real_data_extraction())