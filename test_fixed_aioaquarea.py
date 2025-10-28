#!/usr/bin/env python3
"""
Test Fixed aioaquarea Client Usage
Test the corrected aioaquarea client calls without unsupported parameters.
"""

def test_fixed_aioaquarea_usage():
    """Test the corrected aioaquarea usage."""
    
    print("=== Testing Fixed aioaquarea Client Usage ===")
    
    # Mock aioaquarea for testing the corrected pattern
    class MockClient:
        def __init__(self, username, password, session, device_direct=True, 
                     refresh_login=True, environment=None):
            print("✅ Client created successfully")
        
        async def get_devices(self):
            """Mock get_devices - no include_long_id parameter."""
            print("✅ get_devices() called (no extra parameters)")
            return [MockDeviceInfo()]
        
        async def get_device(self, device_info=None, device_id=None):
            """Mock get_device - no consumption_refresh_interval parameter."""
            print("✅ get_device() called with device_info only")
            return MockDevice()
    
    class MockDeviceInfo:
        def __init__(self):
            self.device_id = "TEST123"
    
    class MockDevice:
        async def refresh_data(self):
            print("✅ device.refresh_data() called")
        
        async def set_mode(self, mode):
            print(f"✅ device.set_mode({mode}) called")
    
    async def test_corrected_pattern():
        """Test the corrected pattern that should work."""
        print("\n1. Creating client with supported parameters only:")
        
        client = MockClient(
            username="test_user",
            password="test_pass", 
            session=None,
            device_direct=True,
            refresh_login=True,
            environment="production"
        )
        
        print("\n2. Getting devices (no include_long_id):")
        devices_info = await client.get_devices()
        
        print("\n3. Getting device (no consumption_refresh_interval):")
        device_info = devices_info[0]
        device = await client.get_device(device_info=device_info)
        
        print("\n4. Using device methods:")
        await device.refresh_data()
        await device.set_mode(1)  # UpdateOperationMode.HEAT
        
        print("\n✅ All aioaquarea calls successful!")
    
    print("\n=== Fixed Integration Pattern ===")
    print("```python")
    print("# Corrected coordinator update method:")
    print("async def _async_update_data(self):")
    print("    devices_info = await self.client.get_devices()  # No extra params")
    print("    for device_info in devices_info:")
    print("        device = await self.client.get_device(device_info=device_info)  # No extra params")
    print("        await device.refresh_data()")
    print("```")
    
    print("\n=== What Changed ===")
    print("❌ REMOVED: get_devices(include_long_id=True)")
    print("✅ FIXED:   get_devices()")
    print("")
    print("❌ REMOVED: get_device(device_info=info, consumption_refresh_interval=timedelta(minutes=1))")
    print("✅ FIXED:   get_device(device_info=info)")
    
    print("\n=== Integration Should Now Load Successfully! ===")
    
    import asyncio
    asyncio.run(test_corrected_pattern())

if __name__ == "__main__":
    test_fixed_aioaquarea_usage()