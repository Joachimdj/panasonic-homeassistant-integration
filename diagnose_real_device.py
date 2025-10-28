#!/usr/bin/env python3
"""
Diagnostic Script - Check Real aioaquarea Device Methods
This script connects to the real API and shows exactly what methods are available
on the device objects so we can implement working controls.
"""

import asyncio
import logging
import sys
import json
from typing import Any

# Enable comprehensive logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

async def diagnose_real_device():
    """Connect to real API and diagnose available device methods."""
    
    try:
        # Import aioaquarea - replace with your actual credentials
        from aioaquarea import Client, AquareaEnvironment
        
        print("🔗 Connecting to Panasonic Aquarea API...")
        
        # Use your actual credentials
        username = "joachim@dittman.dk"
        password = "Test0001"
        
        client = Client(username, password, AquareaEnvironment.PRODUCTION)
        
        # Get devices
        print("📱 Getting device list...")
        devices_info = await client.get_devices()
        print(f"✓ Found {len(devices_info)} devices")
        
        if not devices_info:
            print("❌ No devices found")
            return
        
        # Get first device
        device_info = devices_info[0]
        print(f"\n📊 Device Info: {device_info.device_id} - {getattr(device_info, 'name', 'Unknown')}")
        
        # Get device object
        print("🔧 Getting device object...")
        device = await client.get_device(device_info)
        print(f"✓ Device object type: {type(device)}")
        
        # === COMPREHENSIVE DEVICE INSPECTION ===
        print("\n" + "="*60)
        print("🔍 DEVICE OBJECT ANALYSIS")
        print("="*60)
        
        # Get all attributes and methods
        all_attrs = dir(device)
        
        # Categorize attributes
        properties = []
        methods = []
        private_attrs = []
        
        for attr in all_attrs:
            if attr.startswith('__'):
                continue
            elif attr.startswith('_'):
                private_attrs.append(attr)
            else:
                try:
                    attr_value = getattr(device, attr)
                    if callable(attr_value):
                        methods.append(attr)
                    else:
                        properties.append(attr)
                except:
                    properties.append(attr)  # If we can't get it, assume it's a property
        
        print(f"\n📋 PUBLIC PROPERTIES ({len(properties)}):")
        for prop in sorted(properties):
            try:
                value = getattr(device, prop)
                print(f"  {prop}: {type(value).__name__} = {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
            except Exception as e:
                print(f"  {prop}: <error accessing: {e}>")
        
        print(f"\n🔧 PUBLIC METHODS ({len(methods)}):")
        for method in sorted(methods):
            try:
                method_obj = getattr(device, method)
                # Try to get method signature
                import inspect
                try:
                    sig = inspect.signature(method_obj)
                    print(f"  {method}{sig}")
                except:
                    print(f"  {method}()")
            except Exception as e:
                print(f"  {method}: <error: {e}>")
        
        print(f"\n🔒 PRIVATE ATTRIBUTES ({len(private_attrs)}):")
        for attr in sorted(private_attrs):
            try:
                value = getattr(device, attr)
                print(f"  {attr}: {type(value).__name__}")
            except Exception as e:
                print(f"  {attr}: <error: {e}>")
        
        # === CHECK FOR DEVICE.STATUS ===
        print(f"\n" + "="*60)
        print("📊 DEVICE STATUS ANALYSIS")
        print("="*60)
        
        if hasattr(device, 'status'):
            status = device.status
            print(f"✓ Device has status: {type(status)}")
            
            # Analyze status object
            status_attrs = [attr for attr in dir(status) if not attr.startswith('__')]
            print(f"Status attributes: {status_attrs}")
            
            for attr in status_attrs:
                if not attr.startswith('_'):
                    try:
                        value = getattr(status, attr)
                        print(f"  status.{attr}: {type(value).__name__} = {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
                    except Exception as e:
                        print(f"  status.{attr}: <error: {e}>")
            
            # Check for zones
            if hasattr(status, 'zones'):
                print(f"\n🏠 ZONES ({len(status.zones) if status.zones else 0}):")
                if status.zones:
                    for i, zone in enumerate(status.zones):
                        print(f"  Zone {i+1}: {type(zone)}")
                        zone_attrs = [attr for attr in dir(zone) if not attr.startswith('_')]
                        for attr in zone_attrs:
                            try:
                                value = getattr(zone, attr)
                                if not callable(value):
                                    print(f"    zone.{attr}: {value}")
                            except Exception as e:
                                print(f"    zone.{attr}: <error: {e}>")
            
            # Check for tank
            if hasattr(status, 'tank'):
                print(f"\n🚰 TANK:")
                tank = status.tank
                print(f"  Tank: {type(tank)}")
                tank_attrs = [attr for attr in dir(tank) if not attr.startswith('_')]
                for attr in tank_attrs:
                    try:
                        value = getattr(tank, attr)
                        if not callable(value):
                            print(f"    tank.{attr}: {value}")
                    except Exception as e:
                        print(f"    tank.{attr}: <error: {e}>")
        else:
            print("❌ Device has no status attribute")
        
        # === TEST POTENTIAL CONTROL METHODS ===
        print(f"\n" + "="*60)
        print("🎮 CONTROL METHODS TEST")
        print("="*60)
        
        # Common method patterns to test
        test_methods = [
            # Temperature control
            'set_temperature', 'set_target_temperature', 'set_zone_temperature',
            'set_tank_temperature', 'set_dhw_temperature', 'set_dhw_target_temperature',
            
            # Mode control  
            'set_mode', 'set_operation_mode', 'set_hvac_mode',
            'set_eco_mode', 'set_comfort_mode', 'set_quiet_mode', 'set_powerful_mode',
            
            # Tank control
            'set_tank_operation', 'enable_tank', 'disable_tank',
            'force_dhw', 'set_force_dhw', 'set_dhw_operation',
            
            # Update methods
            'update', 'refresh', 'fetch_status', 'get_status'
        ]
        
        available_control_methods = []
        
        for method_name in test_methods:
            if hasattr(device, method_name):
                method = getattr(device, method_name)
                if callable(method):
                    available_control_methods.append(method_name)
                    print(f"  ✓ {method_name} - AVAILABLE")
                    
                    # Try to get method signature
                    try:
                        import inspect
                        sig = inspect.signature(method)
                        print(f"    Signature: {method_name}{sig}")
                    except:
                        pass
        
        print(f"\n📝 SUMMARY:")
        print(f"  Available control methods: {len(available_control_methods)}")
        if available_control_methods:
            print("  Methods found:", ", ".join(available_control_methods))
        else:
            print("  ❌ No standard control methods found")
        
        # === CHECK CLIENT OBJECT ===
        print(f"\n" + "="*60)
        print("🌐 CLIENT OBJECT ANALYSIS")  
        print("="*60)
        
        if hasattr(device, '_client'):
            client_obj = device._client
            print(f"✓ Device has _client: {type(client_obj)}")
            
            client_methods = [attr for attr in dir(client_obj) if not attr.startswith('_') and callable(getattr(client_obj, attr))]
            print(f"Client methods: {client_methods}")
            
        # === RAW API ANALYSIS ===
        print(f"\n" + "="*60)
        print("🔗 RAW API ANALYSIS")
        print("="*60)
        
        # Check if we can access the raw API client
        if hasattr(client, 'api') or hasattr(client, '_api'):
            api_client = getattr(client, 'api', None) or getattr(client, '_api', None)
            if api_client:
                print(f"✓ Found API client: {type(api_client)}")
                api_methods = [attr for attr in dir(api_client) if not attr.startswith('_') and callable(getattr(api_client, attr))]
                print(f"API methods: {api_methods}")
        
        print(f"\n" + "="*60)
        print("✅ DIAGNOSIS COMPLETE")
        print("="*60)
        
        return {
            'device_type': str(type(device)),
            'properties': properties,
            'methods': methods,
            'available_control_methods': available_control_methods,
            'has_status': hasattr(device, 'status'),
            'has_zones': hasattr(device, 'status') and hasattr(device.status, 'zones') if hasattr(device, 'status') else False,
            'has_tank': hasattr(device, 'status') and hasattr(device.status, 'tank') if hasattr(device, 'status') else False,
        }
        
    except ImportError as e:
        print(f"❌ Failed to import aioaquarea: {e}")
        print("Make sure aioaquarea is installed: pip install aioaquarea")
        return None
    except Exception as e:
        print(f"❌ Error during diagnosis: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🔍 Panasonic Aquarea Device Diagnostic Tool")
    print("=" * 60)
    
    result = asyncio.run(diagnose_real_device())
    
    if result:
        print("\n💾 Saving diagnosis results...")
        with open('/Users/joachimdittman/Documents/HASS home/HACS/panasonic-homeassistant-integration/device_diagnosis.json', 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print("✓ Results saved to device_diagnosis.json")