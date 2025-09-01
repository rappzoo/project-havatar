#!/usr/bin/env python3
"""
Avatar Tank System - Modular Version Launcher
Enhanced with proper error handling and system verification.
"""

import sys
import os
import time
import subprocess
from pathlib import Path


def print_header():
    """Print startup header"""
    print("\n" + "="*70)
    print("    AVATAR TANK CONTROL SYSTEM - MODULAR VERSION")
    print("="*70)
    print(f"Python version: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Script location: {os.path.abspath(__file__)}")
    print("="*70)


def check_system_requirements():
    """Check system requirements and dependencies"""
    print("[System Check] Verifying requirements...")
    
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 7):
        issues.append(f"Python 3.7+ required, found {sys.version}")
    
    # Check required directories
    required_dirs = ['modules', 'snapshots', 'recordings', 'sounds']
    for directory in required_dirs:
        path = Path(directory)
        if not path.exists():
            print(f"[System Check] Creating missing directory: {directory}")
            try:
                path.mkdir(exist_ok=True)
            except Exception as e:
                issues.append(f"Cannot create directory {directory}: {e}")
    
    # Check for required system commands
    required_commands = ['ffmpeg', 'aplay', 'arecord', 'v4l2-ctl']
    for cmd in required_commands:
        try:
            result = subprocess.run(['which', cmd], capture_output=True)
            if result.returncode == 0:
                print(f"[System Check] ✓ {cmd} found")
            else:
                print(f"[System Check] ⚠ {cmd} not found (some features may not work)")
        except:
            print(f"[System Check] ⚠ Could not check for {cmd}")
    
    # Check for Python modules (basic check)
    required_modules = ['flask', 'flask_socketio', 'cv2', 'serial', 'numpy']
    for module in required_modules:
        try:
            __import__(module)
            print(f"[System Check] ✓ {module} module available")
        except ImportError:
            issues.append(f"Missing Python module: {module}")
    
    if issues:
        print("\n[System Check] ✗ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        print("\nPlease resolve these issues before running the system.")
        return False
    
    print("[System Check] ✓ All requirements satisfied")
    return True


def setup_python_path():
    """Set up Python path for module imports"""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Add current directory to Python path
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)
        print(f"[Setup] Added to Python path: {current_dir}")
    
    # Check if modules directory exists and is accessible
    modules_dir = os.path.join(current_dir, 'modules')
    if not os.path.exists(modules_dir):
        print(f"[Setup] ✗ Modules directory not found: {modules_dir}")
        return False
    
    print(f"[Setup] ✓ Modules directory found: {modules_dir}")
    return True


def test_module_imports():
    """Test if all modules can be imported"""
    print("[Module Test] Testing module imports...")
    
    modules_to_test = [
        'modules.device_detector',
        'modules.camera',
        'modules.motor_controller', 
        'modules.tts',
        'modules.recorder',
        'modules.audio_utils',
        'modules.predictor',
        'modules.audio_streamer'
    ]
    
    failed_modules = []
    
    for module_name in modules_to_test:
        try:
            __import__(module_name)
            print(f"[Module Test] ✓ {module_name}")
        except ImportError as e:
            print(f"[Module Test] ✗ {module_name}: {e}")
            failed_modules.append(module_name)
        except Exception as e:
            print(f"[Module Test] ⚠ {module_name}: {e}")
            # Don't add to failed_modules - might still work
    
    if failed_modules:
        print(f"\n[Module Test] Some modules failed to import: {failed_modules}")
        print("The system will run with reduced functionality.")
    else:
        print("[Module Test] ✓ All modules imported successfully")
    
    return len(failed_modules) == 0


def check_permissions():
    """Check file and device permissions"""
    print("[Permissions] Checking device access...")
    
    # Check video devices
    video_devices = ['/dev/video0', '/dev/video1', '/dev/video2']
    video_found = False
    for device in video_devices:
        if os.path.exists(device):
            if os.access(device, os.R_OK):
                print(f"[Permissions] ✓ {device} readable")
                video_found = True
            else:
                print(f"[Permissions] ✗ {device} not readable")
    
    if not video_found:
        print("[Permissions] ⚠ No video devices found")
    
    # Check serial devices
    serial_devices = ['/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyACM0', '/dev/ttyACM1']
    serial_found = False
    for device in serial_devices:
        if os.path.exists(device):
            if os.access(device, os.R_OK | os.W_OK):
                print(f"[Permissions] ✓ {device} accessible")
                serial_found = True
            else:
                print(f"[Permissions] ✗ {device} not accessible (may need to add user to dialout group)")
    
    if not serial_found:
        print("[Permissions] ⚠ No serial devices found")
    
    # Check if user is in required groups
    try:
        import grp
        import pwd
        
        username = pwd.getpwuid(os.getuid()).pw_name
        user_groups = [g.gr_name for g in grp.getgrall() if username in g.gr_mem]
        
        required_groups = ['audio', 'video', 'dialout']
        for group in required_groups:
            if group in user_groups:
                print(f"[Permissions] ✓ User in {group} group")
            else:
                print(f"[Permissions] ⚠ User not in {group} group (some features may not work)")
    
    except Exception as e:
        print(f"[Permissions] Could not check group membership: {e}")


def show_environment_info():
    """Show environment variable information"""
    print("[Environment] Checking override variables...")
    
    env_vars = {
        'AV_CAMERA': 'Camera device override',
        'AV_MIC': 'Microphone device override', 
        'AV_SPK': 'Speaker device override',
        'AV_MOTOR': 'Motor controller port override'
    }
    
    overrides_found = False
    for var, description in env_vars.items():
        value = os.environ.get(var)
        if value:
            print(f"[Environment] {var}={value} ({description})")
            overrides_found = True
    
    if not overrides_found:
        print("[Environment] No override variables set")
        print("[Environment] You can set AV_CAMERA, AV_MIC, AV_SPK, AV_MOTOR to override device detection")


def run_application():
    """Run the main application"""
    print("\n[Launch] Starting Avatar Tank application...")
    print("[Launch] Press Ctrl+C to stop")
    print("="*70)
    
    try:
        # Import and run the main application
        from modules.main_app import app, socketio
        
        # Give a moment for all modules to initialize
        time.sleep(1)
        
        # Start the server
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=False,
            allow_unsafe_werkzeug=True,
            use_reloader=False,
            log_output=False
        )
        
    except ImportError as e:
        print(f"[Launch] ✗ Failed to import main application: {e}")
        print("[Launch] Falling back to direct Flask server...")
        
        try:
            # Fallback to basic Flask
            from modules.main_app import app
            app.run(host='0.0.0.0', port=5000, debug=False)
        except Exception as e2:
            print(f"[Launch] ✗ Fallback also failed: {e2}")
            return False
    
    except KeyboardInterrupt:
        print("\n[Launch] Shutdown requested by user")
        return True
    
    except Exception as e:
        print(f"[Launch] ✗ Application error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


def main():
    """Main entry point"""
    print_header()
    
    # System checks
    if not check_system_requirements():
        print("\n[FATAL] System requirements not met")
        sys.exit(1)
    
    if not setup_python_path():
        print("\n[FATAL] Could not set up Python path")
        sys.exit(1)
    
    # Module testing (non-fatal)
    test_module_imports()
    
    # Permissions and environment info
    check_permissions()
    show_environment_info()
    
    print("\n[Info] Web interface will be available at:")
    print("[Info]   Local:    http://localhost:5000")
    print("[Info]   Network:  http://[your-pi-ip]:5000")
    
    # Final confirmation
    try:
        input("\n[Ready] Press Enter to start the Avatar Tank system (Ctrl+C to cancel)...")
    except KeyboardInterrupt:
        print("\n[Cancelled] Startup cancelled by user")
        sys.exit(0)
    
    # Run the application
    success = run_application()
    
    if success:
        print("\n[Shutdown] Avatar Tank system stopped normally")
        sys.exit(0)
    else:
        print("\n[Error] Avatar Tank system stopped with errors")
        sys.exit(1)


if __name__ == '__main__':
    main()