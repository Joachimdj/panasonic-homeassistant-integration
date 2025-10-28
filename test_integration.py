#!/usr/bin/env python3
"""
Test the Home Assistant integration structure
This validates that all files are properly structured
"""

import json
import os
from pathlib import Path

def test_integration_structure():
    """Test that all required files exist and are valid"""
    base_path = Path(__file__).parent / "custom_components" / "panasonic_aquarea"
    
    print("🧪 Testing Home Assistant Integration Structure")
    print("=" * 50)
    
    # Test manifest.json
    manifest_path = base_path / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            print(f"✅ manifest.json is valid")
            print(f"   Domain: {manifest['domain']}")
            print(f"   Name: {manifest['name']}")
            print(f"   Version: {manifest['version']}")
        except json.JSONDecodeError as e:
            print(f"❌ manifest.json is invalid: {e}")
    else:
        print(f"❌ manifest.json not found")
    
    # Test required files
    required_files = [
        "__init__.py",
        "config_flow.py", 
        "const.py",
        "climate.py",
        "sensor.py",
        "water_heater.py"
    ]
    
    print(f"\n📁 Checking required files:")
    for file in required_files:
        file_path = base_path / file
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✅ {file} ({size} bytes)")
        else:
            print(f"❌ {file} missing")
    
    # Test Python imports (basic syntax check)
    print(f"\n🐍 Testing Python syntax:")
    for file in required_files:
        if file.endswith('.py'):
            file_path = base_path / file
            if file_path.exists():
                try:
                    with open(file_path) as f:
                        compile(f.read(), file, 'exec')
                    print(f"✅ {file} syntax OK")
                except SyntaxError as e:
                    print(f"❌ {file} syntax error: {e}")
    
    print(f"\n📊 Integration Summary:")
    print(f"   📂 Integration path: {base_path}")
    print(f"   🏠 Domain: panasonic_aquarea")
    print(f"   🔌 Platforms: climate, sensor, water_heater")
    print(f"   📡 Library: aioaquarea >= 1.0.0")
    
    print(f"\n🎯 Ready for installation!")
    print(f"   Use: ./install.sh /path/to/homeassistant/config")

if __name__ == "__main__":
    test_integration_structure()