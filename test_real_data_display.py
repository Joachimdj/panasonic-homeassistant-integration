#!/usr/bin/env python3
"""Test script to show how real data will be displayed."""

# Simulate the real data from your log
real_device_data = {
    'operation': 'FFFFFFFF', 
    'ownerFlg': True, 
    'a2wName': 'Langagervej',
    'step2ApplicationStatusFlg': False, 
    'status': {
        'serviceType': 'STD_ADP-TAW1', 
        'uncontrollableTaw1Flg': False, 
        'operationMode': 1, 
        'coolMode': 1, 
        'direction': 2, 
        'quietMode': 0, 
        'powerful': 0, 
        'forceDHW': 0, 
        'forceHeater': 0, 
        'tank': 1, 
        'multiOdConnection': 0, 
        'pumpDuty': 1, 
        'bivalent': 0, 
        'bivalentActual': 0, 
        'waterPressure': 2.08, 
        'electricAnode': 0, 
        'deiceStatus': 0, 
        'specialStatus': 2, 
        'outdoorNow': 9, 
        'holidayTimer': 0, 
        'modelSeriesSelection': 5, 
        'standAlone': 1, 
        'controlBox': 0, 
        'externalHeater': 0, 
        'zoneStatus': [{
            'zoneId': 1, 
            'zoneName': 'House', 
            'zoneType': 0, 
            'zoneSensor': 0, 
            'operationStatus': 1, 
            'temperatureNow': 56, 
            'heatMin': -5, 
            'heatMax': 5, 
            'coolMin': -5, 
            'coolMax': 5, 
            'heatSet': 5, 
            'coolSet': 0, 
            'ecoHeat': -5, 
            'ecoCool': 5, 
            'comfortHeat': 5, 
            'comfortCool': -5
        }], 
        'tankStatus': {
            'operationStatus': 1, 
            'temperatureNow': 59, 
            'heatMin': 40, 
            'heatMax': 75, 
            'heatSet': 60
        }
    }
}

def display_real_temperature_values():
    """Show how the integration will display real temperature values."""
    
    print("🎯 Real Data Temperature Display")
    print("=" * 50)
    
    # Zone temperature
    zone_status = real_device_data['status']['zoneStatus'][0]
    zone_temp_raw = zone_status['temperatureNow']  # 56
    zone_temp_celsius = float(zone_temp_raw) / 10.0  # 5.6°C
    
    print(f"\n🌡️ Zone Temperature:")
    print(f"   Raw value: {zone_temp_raw}")
    print(f"   Displayed: {zone_temp_celsius}°C")
    
    # Tank temperature  
    tank_status = real_device_data['status']['tankStatus']
    tank_temp_raw = tank_status['temperatureNow']  # 59
    tank_temp_celsius = float(tank_temp_raw)  # 59°C (already in degrees)
    
    print(f"\n💧 Tank Temperature:")
    print(f"   Raw value: {tank_temp_raw}")
    print(f"   Displayed: {tank_temp_celsius}°C")
    
    # Target temperature calculation
    target_temp_raw = zone_temp_raw + zone_status['heatSet']  # 56 + 5 = 61
    target_temp_celsius = float(target_temp_raw) / 10.0  # 6.1°C
    
    print(f"\n🎯 Zone Target Temperature:")
    print(f"   Current: {zone_temp_celsius}°C")
    print(f"   Heat offset: +{zone_status['heatSet']/10.0}°C")
    print(f"   Target: {target_temp_celsius}°C")
    
    # Other sensors
    print(f"\n📊 Other Sensor Values:")
    print(f"   Outdoor Temperature: {real_device_data['status']['outdoorNow']}°C")
    print(f"   Water Pressure: {real_device_data['status']['waterPressure']} bar")
    print(f"   Pump Duty: {real_device_data['status']['pumpDuty']}%")
    print(f"   Operation Mode: {real_device_data['status']['operationMode']} (HEAT)")
    
    print(f"\n✅ Integration will now display:")
    print(f"   • House Temperature: {zone_temp_celsius}°C")
    print(f"   • Tank Temperature: {tank_temp_celsius}°C")  
    print(f"   • Target Temperature: {target_temp_celsius}°C")
    print(f"   • Only 1 zone (House) - no 'zone 2' errors")

if __name__ == "__main__":
    display_real_temperature_values()
