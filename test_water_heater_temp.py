#!/usr/bin/env python3
"""
Test script for water heater temperature setting functionality.
This tests the fallback logic when no API methods are available.
"""

class MockCoordinator:
    def __init__(self, device_data):
        self.data = {"test_device": device_data}
    
    async def async_request_refresh(self):
        """Mock refresh method."""
        print("  → Coordinator refresh triggered")
        return True

class MockWaterHeater:
    """Mock water heater to test temperature setting logic."""
    
    def __init__(self, coordinator, device_id):
        self.coordinator = coordinator
        self._device_id = device_id
        self._attr_target_temperature = None
    
    def async_write_ha_state(self):
        """Mock state write."""
        print(f"  → Entity state written: target_temperature = {self._attr_target_temperature}°C")
    
    @property
    def target_temperature(self):
        """Return target temperature from raw data."""
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            return None
            
        raw_data = device_data.get("raw_data")
        if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
            tank_status = raw_data['status']['tankStatus']
            heat_set = tank_status.get('heatSet')
            if heat_set is not None:
                return float(heat_set)
        return None
    
    async def simulate_set_temperature(self, temperature):
        """Simulate the temperature setting logic."""
        print(f"\n🌡️ Setting water heater temperature to {temperature}°C")
        
        device_data = self.coordinator.data.get(self._device_id)
        if not device_data:
            print("  ❌ No device data found")
            return False
        
        # Get current temperature for comparison
        old_temperature = self.target_temperature
        print(f"  Current target: {old_temperature}°C")
        
        device = device_data.get("device")
        
        # Simulate: No API methods available (typical case)
        success = False
        if device:
            print("  🔍 Checking for API methods... (none found - using fallback)")
        
        if not success:
            # Fallback: Update local data structure for immediate feedback
            print("  📝 No API method available, updating local data for immediate feedback")
            raw_data = device_data.get("raw_data")
            if raw_data and 'status' in raw_data and 'tankStatus' in raw_data['status']:
                # Update the tank target temperature 
                old_heatset = raw_data['status']['tankStatus'].get('heatSet', 'unknown')
                raw_data['status']['tankStatus']['heatSet'] = float(temperature)
                print(f"  ✅ Updated tank heatSet from {old_heatset} to {temperature}°C in raw data")
                
                # Force immediate entity update for better responsiveness
                self._attr_target_temperature = float(temperature)
                self.async_write_ha_state()
                
                # Trigger coordinator refresh
                await self.coordinator.async_request_refresh()
                
                # Verify the change
                new_temperature = self.target_temperature
                print(f"  🎯 New target temperature: {new_temperature}°C")
                return True
            else:
                print("  ❌ No raw data available to update tank temperature")
                return False

async def test_water_heater_temperature_setting():
    """Test water heater temperature setting."""
    print("=== Water Heater Temperature Setting Test ===")
    
    # Create test data with tank
    test_data = {
        "device": {},  # Mock device object (no API methods)
        "raw_data": {
            "a2wName": "Test Device",
            "status": {
                "tankStatus": {
                    "operationStatus": 1,
                    "temperatureNow": 45,  # Current temperature
                    "heatSet": 50,         # Current target temperature
                    "heatMin": 40,
                    "heatMax": 75
                }
            }
        }
    }
    
    coordinator = MockCoordinator(test_data)
    water_heater = MockWaterHeater(coordinator, "test_device")
    
    # Test initial state
    print(f"\n📊 Initial state:")
    print(f"  Target temperature: {water_heater.target_temperature}°C")
    
    # Test setting new temperature
    await water_heater.simulate_set_temperature(55)
    
    # Test another temperature change
    await water_heater.simulate_set_temperature(60)
    
    # Test edge case - invalid temperature
    print(f"\n🧪 Testing edge case with None temperature...")
    try:
        await water_heater.simulate_set_temperature(None)
    except Exception as e:
        print(f"  ⚠️ Handled error: {e}")
    
    print("\n✅ Water heater temperature setting test completed!")
    print("\nExpected behavior:")
    print("1. Current target temperature should be read correctly")
    print("2. New temperature should be set in raw data")
    print("3. Entity should update immediately")
    print("4. Coordinator refresh should be triggered")
    print("5. Target temperature property should reflect new value")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_water_heater_temperature_setting())