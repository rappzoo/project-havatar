#!/usr/bin/env python3
"""
Test script for Mumble integration in avatar_tank_enhanced.py
This script tests the basic functionality of the MumbleController class
"""

import sys
import os
import time

# Add the current directory to the path so we can import the avatar_tank_enhanced module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_mumble_import():
    """Test that we can import the MumbleController class"""
    try:
        from avatar_tank_enhanced import MumbleController
        print("✓ Successfully imported MumbleController")
        return True
    except ImportError as e:
        print(f"✗ Failed to import MumbleController: {e}")
        return False

def test_mumble_instance():
    """Test that we can create an instance of MumbleController"""
    try:
        from avatar_tank_enhanced import MumbleController
        mumble = MumbleController()
        print("✓ Successfully created MumbleController instance")
        return True
    except Exception as e:
        print(f"✗ Failed to create MumbleController instance: {e}")
        return False

def test_mumble_methods():
    """Test that all required methods exist"""
    try:
        from avatar_tank_enhanced import MumbleController
        mumble = MumbleController()
        
        # Check that all required methods exist
        required_methods = ['connect', 'disconnect', 'toggle_mute', 'get_status']
        for method in required_methods:
            if hasattr(mumble, method):
                print(f"✓ Method '{method}' exists")
            else:
                print(f"✗ Method '{method}' is missing")
                return False
        
        return True
    except Exception as e:
        print(f"✗ Error testing MumbleController methods: {e}")
        return False

def test_mumble_status():
    """Test the get_status method"""
    try:
        from avatar_tank_enhanced import MumbleController
        mumble = MumbleController()
        status = mumble.get_status()
        
        # Check that status has the required fields
        required_fields = ['ok', 'connected', 'server', 'port', 'username', 'muted', 'process_running']
        for field in required_fields:
            if field in status:
                print(f"✓ Status field '{field}' present")
            else:
                print(f"✗ Status field '{field}' missing")
                return False
        
        print(f"✓ Mumble status: {status}")
        return True
    except Exception as e:
        print(f"✗ Error testing MumbleController status: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Mumble integration in avatar_tank_enhanced.py...")
    print("=" * 60)
    
    tests = [
        test_mumble_import,
        test_mumble_instance,
        test_mumble_methods,
        test_mumble_status
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All tests passed! Mumble integration is working correctly.")
        return 0
    else:
        print("❌ Some tests failed. Please check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())