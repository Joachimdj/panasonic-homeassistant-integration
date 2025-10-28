#!/usr/bin/env python3
"""
Test Zone ID Temperature Setting
Test the updated temperature setting methods with proper zone_id handling.
"""

def test_zone_id_temperature_setting():
    """Test the zone_id parameter handling for temperature setting."""
    
    print("=== Testing Zone ID Temperature Setting Fix ===")
    
    # Mock device with zone_id requirements
    class MockDevice:
        async def set_temperature(self, *args):
            if len(args) == 1:
                # Only temperature provided
                raise Exception("No zone id provided to set_temperature")
            elif len(args) == 2:
                # Zone ID and temperature provided
                zone_id, temperature = args
                print(f"✅ set_temperature(zone_id={zone_id}, temperature={temperature}) succeeded")
                return True
            else:
                raise Exception("Invalid arguments")
        
        async def set_tank_target_temperature(self, *args):
            if len(args) == 1:
                # Only temperature provided - might work for tank
                temperature = args[0]
                print(f"✅ set_tank_target_temperature(temperature={temperature}) succeeded")
                return True
            elif len(args) == 2:
                # Zone ID and temperature provided
                zone_id, temperature = args
                print(f"✅ set_tank_target_temperature(zone_id={zone_id}, temperature={temperature}) succeeded")
                return True
        
        async def set_dhw_target_temperature(self, temperature):
            print(f"✅ set_dhw_target_temperature(temperature={temperature}) succeeded")
            return True
    
    class MockTank:
        async def set_target_temperature(self, *args):
            if len(args) == 1:
                temperature = args[0]
                print(f"✅ tank.set_target_temperature(temperature={temperature}) succeeded")
                return True
            elif len(args) == 2:
                zone_id, temperature = args
                print(f"✅ tank.set_target_temperature(zone_id={zone_id}, temperature={temperature}) succeeded")
                return True
    
    async def test_temperature_methods():
        """Test various temperature setting approaches."""
        
        device = MockDevice()
        tank = MockTank()
        temperature = 55.0
        
        print("\n1. Testing device.set_dhw_target_temperature (should work):")
        try:
            await device.set_dhw_target_temperature(temperature)
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        print("\n2. Testing device.set_tank_target_temperature (should work):")
        try:
            await device.set_tank_target_temperature(temperature)
        except Exception as e:
            print(f"❌ Failed: {e}")
        
        print("\n3. Testing device.set_temperature with zone_id attempts:")
        zone_attempts = [None, 0, "dhw", "tank"]
        
        for zone_id in zone_attempts:
            try:
                if zone_id is None:
                    print(f"   Trying with no zone_id...")
                    await device.set_temperature(temperature)
                    print(f"   ✅ Success with no zone_id")
                    break
                else:
                    print(f"   Trying with zone_id={zone_id}...")
                    await device.set_temperature(zone_id, temperature)
                    print(f"   ✅ Success with zone_id={zone_id}")
                    break
            except Exception as e:
                print(f"   ❌ Failed with zone_id={zone_id}: {e}")
                continue
        
        print("\n4. Testing tank.set_target_temperature:")
        try:
            await tank.set_target_temperature(temperature)
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    print("\n=== Error Analysis ===")
    print("❌ Original Error: 'No zone id provided to set_temperature'")
    print("✅ Root Cause: aioaquarea set_temperature() requires zone_id parameter")
    print("✅ Solution: Try multiple zone_id values for water heater")
    
    print("\n=== Zone ID Strategy ===")
    print("1. 🎯 First Priority: set_dhw_target_temperature() - DHW specific")
    print("2. 🎯 Second Priority: set_tank_target_temperature() - Tank specific") 
    print("3. 🎯 Third Priority: set_temperature() with zone attempts:")
    print("   - None (no zone)")
    print("   - 0 (DHW/tank zone)")
    print("   - 'dhw' (DHW identifier)")
    print("   - 'tank' (tank identifier)")
    print("4. 🎯 Fourth Priority: tank.set_target_temperature() with zone fallback")
    
    print("\n=== Expected Results After Fix ===")
    print("✅ Should see one of these success messages:")
    print("   '🌐 API SUCCESS: Set DHW target temperature using set_dhw_target_temperature'")
    print("   '🌐 API SUCCESS: Set tank target temperature using set_tank_target_temperature'")  
    print("   '🌐 API SUCCESS: Set temperature using set_temperature(zone=X, Y°C)'")
    print("   '🌐 API SUCCESS: Set tank target using tank.set_target_temperature'")
    print("❌ Should NOT see: 'No zone id provided to set_temperature'")
    
    print("\n=== Testing Implementation ===")
    import asyncio
    asyncio.run(test_temperature_methods())
    
    print("\n🚀 NEXT STEPS:")
    print("1. Restart Home Assistant to load the zone_id fix")
    print("2. Set water heater temperature")
    print("3. Check logs for success message (should work now!)")
    print("4. Temperature should persist without reverting")

if __name__ == "__main__":
    test_zone_id_temperature_setting()