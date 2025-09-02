#!/usr/bin/env python3
"""
Motor control module for Avatar Tank system.
Handles motor controller communication and movement commands.
"""

import serial
import time
import json
import threading
import os
import sys
from typing import Dict, Any, Optional


# Try to get device detector - handle import gracefully
try:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    
    from modules.device_detector import device_detector, MOTOR_PORT
    print(f"[Motor] Using detected motor port: {MOTOR_PORT}")
except ImportError as e:
    print(f"[Motor] Warning: Could not import device detector ({e}), using fallback")
    MOTOR_PORT = '/dev/ttyUSB0'


class MotorController:
    """Enhanced motor controller with better error handling and reconnection"""
    
    def __init__(self, port: str = MOTOR_PORT):
        self.ser: Optional[serial.Serial] = None
        self.port = port
        self.lock = threading.Lock()
        self.battery_voltage = 12.0
        self.battery_percentage = 75
        self.connection_attempts = 0
        self.max_connection_attempts = 3
        self.last_command_time = 0
        self.command_timeout = 1.0  # seconds
        self.reconnect_delay = 2.0  # seconds between reconnection attempts
        
        # Connection status
        self.connected = False
        self.last_error = None
        
        # Initialize connection
        self.connect()
    
    def connect(self) -> bool:
        """Connect to motor controller with enhanced error handling"""
        with self.lock:
            return self._connect_internal()
    
    def _connect_internal(self) -> bool:
        """Internal connection method (assumes lock is held)"""
        # Close existing connection
        if self.ser:
            try:
                self.ser.close()
            except:
                pass
            self.ser = None
            self.connected = False
        
        # Get list of ports to try
        ports_to_try = self._get_port_candidates()
        
        for port in ports_to_try:
            if self._try_connect_port(port):
                self.port = port
                self.connected = True
                self.connection_attempts = 0
                self.last_error = None
                print(f"[Motor] ✓ Connected to {port}")
                return True
        
        self.connection_attempts += 1
        error_msg = f"No motor controller found after trying {len(ports_to_try)} ports"
        self.last_error = error_msg
        print(f"[Motor] ✗ {error_msg}")
        return False
    
    def _get_port_candidates(self) -> list:
        """Get list of serial ports to try"""
        candidates = []
        
        # Add the configured port first
        if self.port and os.path.exists(self.port):
            candidates.append(self.port)
        
        # Add common fallback ports
        fallback_ports = [
            '/dev/ttyUSB0', '/dev/ttyUSB1', '/dev/ttyUSB2',
            '/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2',
            '/dev/ttyAMA0', '/dev/ttyAMA1'
        ]
        
        for port in fallback_ports:
            if port not in candidates and os.path.exists(port):
                candidates.append(port)
        
        return candidates
    
    def _try_connect_port(self, port: str) -> bool:
        """Try to connect to a specific port"""
        try:
            print(f"[Motor] Trying {port}...")
            
            # Open serial connection
            self.ser = serial.Serial(
                port=port,
                baudrate=115200,
                timeout=0.5,
                write_timeout=1.0,
                inter_byte_timeout=0.1
            )
            
            # Wait for device to initialize
            time.sleep(1.5)
            
            # Clear any existing data
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            # Test communication
            test_response = self._test_communication()
            if test_response:
                return True
            else:
                self.ser.close()
                self.ser = None
                return False
                
        except Exception as e:
            print(f"[Motor] Failed to connect to {port}: {e}")
            if self.ser:
                try:
                    self.ser.close()
                except:
                    pass
                self.ser = None
            return False
    
    def _test_communication(self) -> bool:
        """Test communication with the motor controller"""
        try:
            print(f"[Motor] Testing communication with motor controller on {self.port}")
            # Send a status command to test communication
            self.ser.write(b'STATUS\n')
            time.sleep(0.3)
            
            response = ""
            start_time = time.time()
            
            while time.time() - start_time < 1.0:
                if self.ser.in_waiting:
                    data = self.ser.read_all().decode('utf-8', 'ignore')
                    response += data
                    break
                time.sleep(0.05)
            
            # Check if we got a valid response
            if response.strip():
                print(f"[Motor] Communication test successful: {response.strip()[:50]}...")
                
                # Try to parse battery info if available
                try:
                    for line in response.split('\n'):
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            data = json.loads(line)
                            print(f"[Motor] Received JSON data: {data}")
                            if 'voltage' in data:
                                self.battery_voltage = float(data['voltage'])
                                self._update_battery_percentage()
                                print(f"[Motor] Battery voltage: {self.battery_voltage}V, {self.battery_percentage}%")
                            break
                except Exception as e:
                    print(f"[Motor] Error parsing battery info: {e}")
                    pass  # Not critical if battery parsing fails
                
                return True
            else:
                print(f"[Motor] No response to STATUS command")
                return False
                
        except Exception as e:
            print(f"[Motor] Communication test failed: {e}")
            return False
    
    def _update_battery_percentage(self):
        """Update battery percentage based on voltage"""
        # Simple linear mapping: 10V = 0%, 12.6V = 100%
        voltage_range = 12.6 - 10.0
        voltage_offset = self.battery_voltage - 10.0
        self.battery_percentage = max(0, min(100, int((voltage_offset / voltage_range) * 100)))
    
    def send_command(self, cmd: str) -> Dict[str, Any]:
        """Send command to motor controller with enhanced error handling"""
        print(f"[Motor] Sending command: {cmd}")
        with self.lock:
            return self._send_command_internal(cmd)
    
    def _send_command_internal(self, cmd: str) -> Dict[str, Any]:
        """Internal command sending method (assumes lock is held)"""
        print(f"[Motor] Internal command processing: {cmd}")
        # Check if we're connected
        if not self.ser or not self.connected:
            print("[Motor] Not connected, attempting to reconnect...")
            if not self._connect_internal():
                return {"ok": False, "msg": "no motor connection", "error": "disconnected"}
        
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_command_time
        if time_since_last < 0.05:  # Minimum 50ms between commands
            print(f"[Motor] Rate limiting, sleeping for {0.05 - time_since_last:.3f}s")
            time.sleep(0.05 - time_since_last)
        
        try:
            # Send command
            command_bytes = (cmd + '\n').encode('utf-8')
            print(f"[Motor] Writing command bytes: {command_bytes}")
            self.ser.write(command_bytes)
            self.ser.flush()  # Ensure command is sent
            
            self.last_command_time = time.time()
            
            # Wait for response
            response = ""
            start_time = time.time()
            
            while time.time() - start_time < self.command_timeout:
                if self.ser.in_waiting:
                    data = self.ser.read_all().decode('utf-8', 'ignore')
                    response += data
                    print(f"[Motor] Received data: {data}")
                    
                    # Look for JSON responses
                    for line in response.split('\n'):
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            try:
                                json_response = json.loads(line)
                                print(f"[Motor] Parsed JSON response: {json_response}")
                                
                                # Update battery info if present
                                if 'voltage' in json_response:
                                    self.battery_voltage = float(json_response['voltage'])
                                    self._update_battery_percentage()
                                
                                return json_response
                            except json.JSONDecodeError as e:
                                print(f"[Motor] JSON decode error: {e}")
                                continue
                
                time.sleep(0.01)
            
            # If we get here, we got a response but no valid JSON
            if response.strip():
                print(f"[Motor] Non-JSON response: {response.strip()}")
                return {"ok": True, "msg": "command sent", "raw": response.strip()}
            else:
                print("[Motor] No response received")
                # Network failure - stop motors
                self._stop_motors_on_failure()
                return {"ok": False, "msg": "no response from motor controller", "error": "network"}
                
        except serial.SerialException as e:
            # Serial communication error - mark as disconnected
            print(f"[Motor] Serial exception: {e}")
            self.connected = False
            self.last_error = str(e)
            try:
                self.ser.close()
            except:
                pass
            self.ser = None
            
            # Network failure - stop motors
            self._stop_motors_on_failure()
            return {"ok": False, "msg": f"serial error: {e}", "error": "serial"}
            
        except Exception as e:
            print(f"[Motor] General exception: {e}")
            self.last_error = str(e)
            # Network failure - stop motors
            self._stop_motors_on_failure()
            return {"ok": False, "msg": f"command error: {e}", "error": "general"}
    
    def _stop_motors_on_failure(self):
        """Stop motors when network failure is detected"""
        print("[Motor] Network failure detected, stopping motors")
        try:
            if self.ser:
                self.ser.write(b'STOP\n')
                self.ser.flush()
        except:
            pass
    
    def move(self, left_speed: int, right_speed: int) -> Dict[str, Any]:
        """Move the robot with specified left and right motor speeds"""
        # Clamp speeds to valid range
        left_speed = max(-255, min(255, int(left_speed)))
        right_speed = max(-255, min(255, int(right_speed)))
        
        command = f"PWM {left_speed} {right_speed}"
        print(f"[Motor] Sending move command: {command}")
        return self.send_command(command)
    
    def stop(self) -> Dict[str, Any]:
        """Stop all motors immediately"""
        print("[Motor] Sending STOP command")
        return self.send_command("STOP")
    
    def test_motors(self) -> Dict[str, Any]:
        """Test motor functionality"""
        try:
            # Test forward movement
            forward_result = self.move(100, 100)
            time.sleep(1)
            
            # Stop motors
            stop_result = self.stop()
            time.sleep(0.5)
            
            # Test backward movement
            backward_result = self.move(-100, -100)
            time.sleep(1)
            
            # Stop motors
            stop_result2 = self.stop()
            
            return {
                "ok": True,
                "msg": "Motor test completed",
                "forward": forward_result,
                "backward": backward_result,
                "stops": [stop_result, stop_result2]
            }
        except Exception as e:
            return {"ok": False, "msg": str(e)}
    
    def get_battery(self) -> Dict[str, Any]:
        """Get battery status"""
        # If not connected, return last known values
        if not self.connected:
            return {
                "voltage": self.battery_voltage,
                "percentage": self.battery_percentage,
                "connected": False,
                "error": self.last_error
            }
        
        # Try to get fresh battery data
        response = self.send_command("STATUS")
        
        return {
            "voltage": self.battery_voltage,
            "percentage": self.battery_percentage,
            "connected": self.connected,
            "last_response": response.get("ok", False)
        }
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive motor controller status"""
        # If not connected, try to reconnect
        if not self.connected:
            # Try to reconnect but don't block
            threading.Thread(target=self._connect_internal, daemon=True).start()
            # Return current status without waiting for reconnect
            pass
        
        return {
            "connected": self.connected,
            "ok": self.connected,  # For backward compatibility
            "port": self.port,
            "battery_voltage": self.battery_voltage,
            "battery_percentage": self.battery_percentage,
            "connection_attempts": self.connection_attempts,
            "last_error": self.last_error,
            "last_command_time": self.last_command_time
        }
    
    def reconnect(self) -> bool:
        """Force a reconnection attempt"""
        print("[Motor] Manual reconnection requested")
        with self.lock:
            self.connected = False
            return self._connect_internal()
    
    def close(self):
        """Clean up motor controller connection"""
        with self.lock:
            if self.ser:
                try:
                    # Send stop command before closing
                    self.ser.write(b'STOP\n')
                    time.sleep(0.1)
                    self.ser.close()
                except:
                    pass
                self.ser = None
            self.connected = False
            print("[Motor] Connection closed")


# Create global motor controller instance
print("[Motor] Initializing motor controller...")
motors = MotorController(MOTOR_PORT)

# Compatibility functions for the old interface
def get_motor_status():
    """Get motor controller status"""
    return motors.get_status()

def reconnect_motors():
    """Reconnect to motor controller"""
    return motors.reconnect()

# Add a specific reconnect function for the API
def reconnect_motor_controller():
    """Reconnect to motor controller - for API use"""
    print("[Motor] API reconnection requested")
    return motors.reconnect()

print(f"[Motor] Initialized - Connected: {motors.connected}, Port: {motors.port}")