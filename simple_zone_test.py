#!/usr/bin/env python3
"""
Simple zone filtering test without Home Assistant dependencies.
"""

class MockZone:
    def __init__(self, zone_id, name):
        self.zone_id = zone_id
        self.name = name
    
    def __repr__(self):
        return f"Zone(id={self.zone_id}, name='{self.name}')"

def test_zone_filtering():
    """Test zone filtering logic."""
    print("=== Zone Filtering Test ===")
    
    # Test case 1: Single zone device
    print("\n--- Test Case 1: Single zone device ---")
    zones_single = [MockZone(1, "Living Area")]
    print(f"Original zones: {zones_single}")
    
    # Apply filtering (zone 1 only)
    filtered_single = [zone for zone in zones_single if getattr(zone, 'zone_id', None) == 1]
    print(f"Filtered zones (zone 1 only): {filtered_single}")
    
    # Test case 2: Multi-zone device
    print("\n--- Test Case 2: Multi-zone device ---")
    zones_multi = [MockZone(1, "Living Area"), MockZone(2, "Bedroom")]
    print(f"Original zones: {zones_multi}")
    
    # Apply filtering (zone 1 only)
    filtered_multi = [zone for zone in zones_multi if getattr(zone, 'zone_id', None) == 1]
    print(f"Filtered zones (zone 1 only): {filtered_multi}")
    
    # Test case 3: Check entity creation logic
    print("\n--- Test Case 3: Entity creation logic ---")
    for zones, case_name in [(zones_single, "Single zone"), (zones_multi, "Multi-zone")]:
        print(f"\n{case_name} case:")
        filtered = [zone for zone in zones if getattr(zone, 'zone_id', None) == 1]
        
        entities_created = []
        for zone in filtered:
            zone_id = getattr(zone, 'zone_id', None)
            zone_name = getattr(zone, 'name', None)
            
            print(f"  Processing zone: ID={zone_id}, Name={zone_name}")
            
            # Only create entities for zone ID 1 (our new filter)
            if zone_id == 1 and zone_name:
                entities_created.append(f"Climate entity for zone {zone_id} ({zone_name})")
                print(f"    ✓ Created: Climate entity for zone {zone_id}")
            elif zone_id != 1:
                print(f"    ✗ Skipped: Zone {zone_id} (only zone 1 supported)")
            else:
                print(f"    ✗ Skipped: Missing zone name")
        
        print(f"  Total entities created: {len(entities_created)}")
        for entity in entities_created:
            print(f"    - {entity}")
    
    print("\n=== Test Complete ===")
    print("Expected result: Only 1 climate entity should be created in both cases")

if __name__ == "__main__":
    test_zone_filtering()