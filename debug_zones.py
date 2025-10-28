#!/usr/bin/env python3
"""
Test script to debug zone 2 creation issue.
This will help us understand what zones are being detected and processed.
"""

import asyncio
import logging
import sys
import os

# Add the custom component path to Python path
sys.path.insert(0, '/Users/joachimdittman/Documents/HASS home/HACS/panasonic-homeassistant-integration')

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_LOGGER = logging.getLogger(__name__)

async def test_zone_detection():
    """Test zone detection logic."""
    print("=== Zone Detection Debug Test ===")
    
    # Test the zone creation logic directly
    from custom_components.panasonic_aquarea.climate import async_setup_entry
    from custom_components.panasonic_aquarea import AquareaDataUpdateCoordinator
    
    print("\n1. Testing climate entity setup...")
    
    # Create mock objects to test zone detection
    class MockEntry:
        def __init__(self):
            self.entry_id = "test_entry"
            self.data = {"username": "test", "password": "test"}
    
    class MockHass:
        def __init__(self):
            self.data = {
                "panasonic_aquarea": {
                    "test_entry": None  # Will be filled by coordinator
                }
            }
    
    class MockZone:
        def __init__(self, zone_id, name):
            self.zone_id = zone_id
            self.name = name
    
    class MockDeviceInfo:
        def __init__(self, zones):
            self.device_id = "test_device"
            self.zones = zones
    
    class MockCoordinator:
        def __init__(self, data):
            self.data = data
    
    # Test case 1: Single zone device
    print("\n--- Test Case 1: Single zone device ---")
    mock_device_info_single = MockDeviceInfo([MockZone(1, "Living Area")])
    mock_coordinator_single = MockCoordinator({
        "test_device": {
            "info": mock_device_info_single,
            "raw_data": None
        }
    })
    
    print(f"Device info zones: {mock_device_info_single.zones}")
    for zone in mock_device_info_single.zones:
        print(f"  Zone ID: {zone.zone_id}, Name: {zone.name}")
    
    # Test case 2: Multi-zone device (to see how filtering works)
    print("\n--- Test Case 2: Multi-zone device ---")
    mock_device_info_multi = MockDeviceInfo([
        MockZone(1, "Living Area"), 
        MockZone(2, "Bedroom")
    ])
    mock_coordinator_multi = MockCoordinator({
        "test_device": {
            "info": mock_device_info_multi,
            "raw_data": None
        }
    })
    
    print(f"Device info zones: {mock_device_info_multi.zones}")
    for zone in mock_device_info_multi.zones:
        print(f"  Zone ID: {zone.zone_id}, Name: {zone.name}")
    
    # Test the filtering logic from climate.py
    print("\n--- Testing Zone Filtering Logic ---")
    zones = mock_device_info_multi.zones
    filtered_zones = [zone for zone in zones if getattr(zone, 'zone_id', None) == 1]
    print(f"Original zones: {len(zones)}")
    print(f"Filtered zones (zone 1 only): {len(filtered_zones)}")
    for zone in filtered_zones:
        print(f"  Filtered Zone ID: {zone.zone_id}, Name: {zone.name}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_zone_detection())