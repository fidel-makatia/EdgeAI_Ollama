#!/usr/bin/env python3
"""
Enhanced Smart Home Assistant for Jetson Xavier AGX
Optimized for efficiency and expanded home automation capabilities
"""

import json
import time
import re
import argparse
import threading
import queue
import asyncio
from datetime import datetime, timedelta
from collections import deque, defaultdict
import statistics
import requests
import schedule
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

# For Ollama integration
import ollama

# For GPIO control on Jetson
try:
    import Jetson.GPIO as GPIO
    GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    print("⚠️  Jetson.GPIO not found or not running on a Jetson. Running in simulation mode.")
    GPIO_AVAILABLE = False


# For web API
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

# For environmental monitoring (optional)
try:
    import board
    import busio
    import adafruit_dht
    SENSORS_AVAILABLE = True
except ImportError:
    SENSORS_AVAILABLE = False
    print("⚠️  Environmental sensors not available. Install adafruit-circuitpython-dht for sensor support.")

class DeviceType(Enum):
    """Enumeration of device types for better categorization"""
    LIGHT = "light"
    FAN = "fan"
    HEATER = "heater"
    AC = "ac"
    DOOR_LOCK = "door_lock"
    CURTAIN = "curtain"
    OUTLET = "outlet"
    ALARM = "alarm"
    SENSOR = "sensor"

@dataclass
class Device:
    """Enhanced device representation with more metadata"""
    name: str
    pin: int
    device_type: DeviceType
    state: bool = False
    aliases: List[str] = None
    room: str = "general"
    power_consumption: float = 0.0  # Watts
    schedule: Dict[str, str] = None  # For scheduled operations
    last_changed: datetime = None
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []
        if self.schedule is None:
            self.schedule = {}
        if self.last_changed is None:
            self.last_changed = datetime.now()

class SmartHomeAssistant:
    """
    Enhanced Smart Home Assistant using Ollama for natural language understanding
    """
    
    def __init__(self, model_name="deepseek-r1:7b"):
        """
        Initialize the assistant with Ollama
        
        Args:
            model_name: Name of the Ollama model to use
        """
        print("🏠 Initializing Enhanced Smart Home Assistant...")
        self._gpio_simulation_mode = not GPIO_AVAILABLE
        
        # Performance tracking
        self._setup_performance_tracking()
        
        # Initialize Ollama model
        self._init_ollama(model_name)
        
        # Initialize devices with enhanced configuration
        self._init_devices()
        
        # Setup GPIO
        self._setup_gpio()
        
        # Initialize context and automation rules
        self._init_context()
        self._init_automation_rules()
        
        # Command queue for async processing
        self.command_queue = queue.Queue()
        self.response_cache = {}  # Cache for frequent commands
        
        # Start background threads
        self._start_background_tasks()
        
        print("✅ Smart Home Assistant initialized successfully!")
    
    def _init_ollama(self, model_name):
        """Initialize Ollama client"""
        try:
            # Check if model exists
            models = ollama.list()
            # FIX: Safely check for model name to prevent KeyError
            if not any(model_name in m.get('name', '') for m in models.get('models', [])):
                print(f"⚠️  Model {model_name} not found. Pulling it now...")
                ollama.pull(model_name)
            
            self.model_name = model_name
            print(f"✅ Ollama initialized with model: {model_name}")
        except Exception as e:
            print(f"❌ Failed to initialize Ollama: {e}")
            raise
    
    def _init_devices(self):
        """Initialize enhanced device configuration"""
        self.devices = {
            # Living Room
            'living_room_light': Device(
                name='living_room_light', pin=7, device_type=DeviceType.LIGHT,
                aliases=['living room light', 'main light', 'lounge light'],
                room='living_room', power_consumption=60
            ),
            'living_room_fan': Device(
                name='living_room_fan', pin=11, device_type=DeviceType.FAN,
                aliases=['living room fan', 'main fan'],
                room='living_room', power_consumption=75
            ),
            
            # Bedroom
            'bedroom_light': Device(
                name='bedroom_light', pin=13, device_type=DeviceType.LIGHT,
                aliases=['bedroom light', 'bed light'],
                room='bedroom', power_consumption=40
            ),
            'bedroom_ac': Device(
                name='bedroom_ac', pin=15, device_type=DeviceType.AC,
                aliases=['bedroom ac', 'bedroom air conditioner'],
                room='bedroom', power_consumption=1200
            ),
            'bedroom_heater': Device(
                name='bedroom_heater', pin=31, device_type=DeviceType.HEATER,
                aliases=['heater', 'bedroom heater'],
                room='bedroom', power_consumption=1500
            ),
            
            # Kitchen
            'kitchen_light': Device(
                name='kitchen_light', pin=16, device_type=DeviceType.LIGHT,
                aliases=['kitchen light'],
                room='kitchen', power_consumption=80
            ),
            'kitchen_exhaust': Device(
                name='kitchen_exhaust', pin=18, device_type=DeviceType.FAN,
                aliases=['exhaust fan', 'kitchen fan'],
                room='kitchen', power_consumption=30
            ),
            
            # Security
            'front_door_lock': Device(
                name='front_door_lock', pin=22, device_type=DeviceType.DOOR_LOCK,
                aliases=['front door', 'main door', 'door lock'],
                room='entrance', power_consumption=5
            ),
            'security_alarm': Device(
                name='security_alarm', pin=24, device_type=DeviceType.ALARM,
                aliases=['alarm', 'security'],
                room='general', power_consumption=10
            ),
            
            # Outdoor
            'garden_light': Device(
                name='garden_light', pin=26, device_type=DeviceType.LIGHT,
                aliases=['garden', 'outdoor light', 'yard light'],
                room='outdoor', power_consumption=100
            ),
            
            # Smart Outlets
            'smart_outlet_1': Device(
                name='smart_outlet_1', pin=29, device_type=DeviceType.OUTLET,
                aliases=['outlet 1', 'plug 1'],
                room='general', power_consumption=0
            ),
        }
        
        # Create room-based device mapping for efficient lookups
        self.devices_by_room = defaultdict(list)
        for name, device in self.devices.items():
            self.devices_by_room[device.room].append(name)
        
        # Create type-based device mapping
        self.devices_by_type = defaultdict(list)
        for name, device in self.devices.items():
            self.devices_by_type[device.device_type].append(name)
    
    def _init_context(self):
        """Initialize enhanced context with more environmental data"""
        self.context = {
            'temperature': 72,
            'humidity': 45,
            'outdoor_temp': 85,
            'time_of_day': self.get_time_context(),
            'day_of_week': datetime.now().strftime('%A'),
            'season': self._get_season(),
            'occupancy': {'living_room': True, 'bedroom': False, 'kitchen': False},
            'power_usage': 0.0,
            'security_armed': False,
            'sleep_mode': False,
            'vacation_mode': False,
            'last_motion': datetime.now(),
        }
        
        # Environmental thresholds
        self.thresholds = {
            'temp_comfort_min': 68,
            'temp_comfort_max': 76,
            'humidity_comfort_min': 30,
            'humidity_comfort_max': 60,
            'power_limit': 3000,  # Watts
        }
    
    def _init_automation_rules(self):
        """Initialize automation rules and scenes"""
        self.scenes = {
            'movie_night': {
                'devices': {
                    'living_room_light': False,
                    'kitchen_light': False,
                    'living_room_fan': True,
                },
                'description': 'Dims lights for movie watching'
            },
            'dinner': {
                'devices': {
                    'kitchen_light': True,
                    'kitchen_exhaust': True,
                    'living_room_light': True,
                },
                'description': 'Bright kitchen for cooking'
            },
            'sleep': {
                'devices': {
                    'bedroom_light': False,
                    'bedroom_ac': True,
                    'living_room_light': False,
                    'kitchen_light': False,
                    'garden_light': False,
                    'security_alarm': True,
                },
                'description': 'Nighttime sleep mode'
            },
            'wake_up': {
                'devices': {
                    'bedroom_light': True,
                    'kitchen_light': True,
                    'security_alarm': False,
                },
                'description': 'Morning wake up routine'
            },
            'away': {
                'devices': {
                    'all_lights': False,
                    'security_alarm': True,
                    'front_door_lock': True,
                },
                'description': 'Security mode when away'
            },
        }
        
        # Automation triggers
        self.automation_rules = [
            {
                'name': 'sunset_lights',
                'trigger': 'time',
                'time': 'sunset',
                'action': lambda: self.activate_scene('evening_lights'),
                'enabled': True
            },
            {
                'name': 'temperature_control',
                'trigger': 'condition',
                'condition': lambda: self.context['temperature'] > self.thresholds['temp_comfort_max'],
                'action': lambda: self._temperature_regulation('cool'),
                'enabled': True
            },
            {
                'name': 'motion_lights',
                'trigger': 'motion',
                'condition': lambda: self.context['time_of_day'] in ['evening', 'night'],
                'action': lambda: self._motion_activated_lights(),
                'enabled': True
            },
        ]
    
    def _setup_gpio(self):
        """Configure GPIO pins with error handling"""
        if self._gpio_simulation_mode:
            print("GPIO running in simulation mode.")
            return

        try:
            GPIO.setmode(GPIO.BOARD)
            GPIO.setwarnings(False)
            
            for device in self.devices.values():
                GPIO.setup(device.pin, GPIO.OUT, initial=GPIO.LOW)
            
            print("✅ GPIO pins initialized for all devices")
        except Exception as e:
            print(f"⚠️  GPIO initialization failed: {e}. Running in simulation mode.")
            self._gpio_simulation_mode = True
    
    def _setup_performance_tracking(self):
        """Initialize performance metrics"""
        self.performance_stats = {
            'command_latencies': deque(maxlen=100),
            'inference_times': deque(maxlen=100),
            'llm_token_counts': deque(maxlen=100),
            'llm_eval_durations': deque(maxlen=100),
            'cache_hits': 0,
            'cache_misses': 0,
            'total_commands': 0,
            'energy_saved': 0.0,
            'automation_triggers': 0,
            'recent_commands': deque(maxlen=5)
        }
    
    def _start_background_tasks(self):
        """Start background threads for automation and monitoring"""
        # Schedule checker thread
        schedule_thread = threading.Thread(target=self._schedule_checker, daemon=True)
        schedule_thread.start()
        
        # Context updater thread
        context_thread = threading.Thread(target=self._context_updater, daemon=True)
        context_thread.start()
        
        # Command processor thread
        processor_thread = threading.Thread(target=self._command_processor, daemon=True)
        processor_thread.start()
    
    def _get_ollama_response(self, prompt: str, max_tokens: int = 256) -> str:
        """Get response from Ollama model"""
        try:
            response = ollama.generate(
                model=self.model_name,
                prompt=prompt,
                options={
                    'temperature': 0.0, # Set to 0 for deterministic JSON output
                    'top_p': 0.9,
                    'num_predict': max_tokens,
                },
                format="json" # Enforce JSON output format
            )
            
            # Track token generation performance from the response object
            if response and response.get('eval_count') and response.get('eval_duration'):
                self.performance_stats['llm_token_counts'].append(response.get('eval_count', 0))
                self.performance_stats['llm_eval_durations'].append(response.get('eval_duration', 0))

            return response['response']
        except Exception as e:
            print(f"❌ Ollama error: {e}")
            return None
    
    def understand_command(self, user_input: str) -> Dict[str, Any]:
        """Enhanced command understanding with caching and context awareness, LLM-first."""
        # Check cache first
        cache_key = user_input.lower().strip()
        if cache_key in self.response_cache:
            self.performance_stats['cache_hits'] += 1
            cached = self.response_cache[cache_key].copy()
            cached['from_cache'] = True
            print("✅ Using cached response.")
            return cached
        
        self.performance_stats['cache_misses'] += 1
        
        # Always use Ollama for understanding
        print("🤔 Using Deepseek model for command...")
        inference_start = time.time()
        
        prompt = self._build_ollama_prompt(user_input)
        response_text = self._get_ollama_response(prompt)
        
        # Print the raw LLM output for debugging
        print(f"🤖 LLM Raw Output: {response_text}")

        inference_time = time.time() - inference_start
        self.performance_stats['inference_times'].append(inference_time)
        
        # Parse response
        action = self._parse_llm_response(response_text)
        if action:
            action['raw_input'] = user_input
            self._cache_response(cache_key, action)
            return action
        
        # Fallback to pattern matching ONLY if LLM fails completely
        print("⚠️ LLM failed to provide a valid action. Falling back to pattern matching.")
        fallback_action = self._fast_pattern_match(user_input, is_fallback=True)
        fallback_action['raw_input'] = user_input
        return fallback_action
    
    def _build_ollama_prompt(self, user_input: str) -> str:
        """Build optimized prompt for Ollama"""
        device_states = {name: ("on" if device.state else "off") for name, device in self.devices.items()}
        occupied_rooms = [room for room, is_occupied in self.context.get('occupancy', {}).items() if is_occupied]
        unused_devices = [
            name for name, device in self.devices.items()
            if device.state and device.room not in occupied_rooms and device.room != 'general'
        ]

        prompt = f"""You are a smart home automation assistant and energy manager. You have full control over all home devices (lights, fans, ACs, heaters, outlets, etc.). Your job is to always act to maximize comfort, safety, and energy efficiency based on the user's request and the context.
If the user asks to save power, reduce electricity bill, or optimize energy usage:

Take the initiative to turn off all lights, fans, ACs, heaters, and outlets in unoccupied rooms or devices not needed for safety or comfort.
If the user does not specify devices, you must decide and recommend/off actions that make sense (for example, turn off devices in empty rooms).
Never return an ambiguous or clarify response for "save power" requests—always take the most reasonable set of actions possible and explain your reasoning.
General command schema:

{{
  "intent": "turn_off/turn_on/set_temperature/toggle/activate_scene/clarify/unknown",
  "devices": ["device1", "device2"],
  "scene": "scene_name or null",
  "value": "number_or_string_or_null",
  "reasoning": "brief explanation"
}}
Context example:

Time: morning, Monday
Season: summer
Temperature (indoor/outdoor): 73°F / 89°F
Occupancy: {{"living_room": true, "bedroom": false, "kitchen": false}}
Devices and their state: {json.dumps(device_states)}
Unused devices: {json.dumps(unused_devices)}
Scenes: {', '.join(self.scenes.keys())}
Examples:
User: "I want to save power"

{{
  "intent": "turn_off",
  "devices": ["kitchen_light", "living_room_fan"],
  "scene": null,
  "value": null,
  "reasoning": "Turning off unused lights and fans in unoccupied rooms to save power."
}}
User: "Reduce my electricity bill"

{{
  "intent": "turn_off",
  "devices": ["bedroom_ac", "garden_light"],
  "scene": null,
  "value": null,
  "reasoning": "Turning off AC and outdoor lights not needed."
}}
User request: "{user_input}"
Respond ONLY with a valid JSON object according to the schema above. Never respond with clarify or unknown for power-saving or optimization requests—always take the smartest, safest actions. Do not output markdown or extra text.
"""
        return prompt
    
    def _fast_pattern_match(self, user_input: str, is_fallback: bool = False) -> Dict[str, Any]:
        """Optimized pattern matching for common commands"""
        text = user_input.lower()
        confidence = 1.0 if not is_fallback else 0.5
        
        # Scene activation
        for scene_name, scene_data in self.scenes.items():
            if scene_name.replace('_', ' ') in text:
                return {
                    'intent': 'activate_scene',
                    'scene': scene_name,
                    'confidence': confidence,
                    'reasoning': f'Activating {scene_name} scene'
                }
        
        # Device control patterns
        patterns = {
            'turn_on': ['turn on', 'switch on', 'enable', 'activate'],
            'turn_off': ['turn off', 'switch off', 'disable', 'deactivate', 'kill'],
            'toggle': ['toggle', 'flip'],
        }
        
        for intent, keywords in patterns.items():
            if any(kw in text for kw in keywords):
                devices = self._extract_devices_from_text(text)
                if devices:
                    return {
                        'intent': intent,
                        'devices': devices,
                        'confidence': confidence,
                        'reasoning': f'Pattern match for {intent}'
                    }
        
        # Room-based commands
        room_keywords = {
            'living room': 'living_room',
            'bedroom': 'bedroom',
            'kitchen': 'kitchen',
            'garden': 'outdoor',
            'outside': 'outdoor',
        }
        
        for keyword, room in room_keywords.items():
            if keyword in text:
                if 'light' in text:
                    devices = [d for d in self.devices_by_room[room] 
                               if self.devices[d].device_type == DeviceType.LIGHT]
                else:
                    devices = self.devices_by_room[room]
                
                if devices:
                    intent = 'turn_on' if any(kw in text for kw in patterns['turn_on']) else 'turn_off'
                    return {
                        'intent': intent,
                        'devices': devices,
                        'confidence': confidence - 0.02, # Slightly less confident than direct match
                        'reasoning': f'Room-based command for {room}'
                    }
        
        # Environmental commands
        if any(word in text for word in ['hot', 'warm', 'sweating']):
            return {
                'intent': 'set_temperature',
                'value': 'decrease',
                'confidence': 0.8,
                'reasoning': 'User feels hot'
            }
        
        if any(word in text for word in ['cold', 'freezing', 'chilly']):
            return {
                'intent': 'set_temperature',
                'value': 'increase',
                'confidence': 0.8,
                'reasoning': 'User feels cold'
            }
        
        # Status check
        if any(word in text for word in ['status', 'what\'s on', 'check', 'show']):
            return {
                'intent': 'check_status',
                'confidence': 0.9,
                'reasoning': 'Status check request'
            }
        
        return {
            'intent': 'unknown',
            'confidence': 0.1,
            'reasoning': 'No pattern matched'
        }
    
    def _extract_devices_from_text(self, text: str) -> List[str]:
        """Extract device names from text"""
        devices = []
        
        # Check for "all" keywords
        if any(word in text for word in ['all', 'everything', 'entire']):
            if 'light' in text:
                return self.devices_by_type[DeviceType.LIGHT]
            return list(self.devices.keys())
        
        # Check specific devices
        for name, device in self.devices.items():
            device_keywords = [name.replace('_', ' ')] + device.aliases
            if any(kw in text for kw in device_keywords):
                devices.append(name)
        
        return devices
    
    def execute_command(self, action: Dict[str, Any]) -> str:
        """Execute the parsed command with enhanced feedback"""
        if not action:
            return "I'm sorry, I had trouble understanding that."

        intent = action.get('intent')
        self.performance_stats['total_commands'] += 1
        if 'raw_input' in action:
            self.performance_stats['recent_commands'].append(action['raw_input'])
        
        if intent == 'clarify':
            return action.get('reasoning', "Could you please clarify?")

        if intent == 'activate_scene':
            return self._activate_scene(action.get('scene'))
        
        elif intent in ['turn_on', 'turn_off']:
            devices = action.get('devices', [])
            state = intent == 'turn_on'
            return self._control_devices(devices, state)
        
        elif intent == 'toggle':
            devices = action.get('devices', [])
            return self._toggle_devices(devices)
        
        elif intent == 'set_temperature':
            value = action.get('value')
            return self._temperature_regulation(value)
        
        elif intent == 'check_status':
            return self._get_status_report()
        
        elif intent == 'schedule':
            return self._schedule_operation(action)
        
        else:
            return action.get('reasoning', f"I understood the intent '{intent}' but don't know how to handle it yet.")
    
    def _control_devices(self, device_names: List[str], state: bool) -> str:
        """Control multiple devices with power monitoring"""
        responses = []
        total_power_change = 0
        
        for device_name in device_names:
            if device_name not in self.devices:
                continue
            
            device = self.devices[device_name]
            if device.state != state:
                # Control the device
                if self._gpio_simulation_mode:
                    print(f"[SIM] {'Turning on' if state else 'Turning off'} {device_name} (Pin {device.pin})")
                else:
                    GPIO.output(device.pin, GPIO.HIGH if state else GPIO.LOW)
                
                # Update state and power usage
                power_change = device.power_consumption if state else -device.power_consumption
                total_power_change += power_change
                
                device.state = state
                device.last_changed = datetime.now()
                
                responses.append(f"{device_name.replace('_', ' ')}")
        
        if responses:
            action_str = "on" if state else "off"
            self.context['power_usage'] += total_power_change
            
            response = f"Turned {action_str}: {', '.join(responses)}"
            if abs(total_power_change) > 100:
                response += f" (Power change: {total_power_change:+.0f}W)"
            
            # Check power limit
            if self.context['power_usage'] > self.thresholds['power_limit']:
                response += f"\n⚠️  Warning: Power usage ({self.context['power_usage']:.0f}W) exceeds limit!"
            
            return response
        
        return "No devices were changed."

    def _toggle_devices(self, device_names: List[str]) -> str:
        """Toggles the state of specified devices."""
        if not device_names:
            return "Which device would you like to toggle?"
        
        responses = []
        for device_name in device_names:
            if device_name in self.devices:
                device = self.devices[device_name]
                new_state = not device.state
                self._control_devices([device_name], new_state)
                responses.append(f"{device_name.replace('_', ' ')} is now {'ON' if new_state else 'OFF'}")
        
        return ". ".join(responses) if responses else "Could not find the specified devices."

    def _activate_scene(self, scene_name: str) -> str:
        """Activate a predefined scene"""
        if scene_name not in self.scenes:
            available = ', '.join(self.scenes.keys())
            return f"Unknown scene. Available: {available}"
        
        scene = self.scenes[scene_name]
        
        for device_name, desired_state in scene['devices'].items():
            if device_name == 'all_lights':
                # Special case for all lights
                light_devices = self.devices_by_type[DeviceType.LIGHT]
                self._control_devices(light_devices, desired_state)
            elif device_name in self.devices:
                self._control_devices([device_name], desired_state)
        
        return f"Scene '{scene_name}' activated: {scene['description']}"
    
    def _temperature_regulation(self, direction: str) -> str:
        """Intelligent temperature regulation"""
        current_temp = self.context['temperature']
        
        if direction == 'increase' or direction == 'heat':
            # Turn on heating devices, turn off cooling
            self._control_devices(self.devices_by_type.get(DeviceType.HEATER, []), True)
            self._control_devices(self.devices_by_type.get(DeviceType.FAN, []), False)
            self._control_devices(self.devices_by_type.get(DeviceType.AC, []), False)
            return f"Heating mode activated. Current temperature: {current_temp}°F"
        
        elif direction == 'decrease' or direction == 'cool':
            # Turn on cooling devices, turn off heating
            self._control_devices(self.devices_by_type.get(DeviceType.AC, []), True)
            self._control_devices(self.devices_by_type.get(DeviceType.FAN, []), True)
            self._control_devices(self.devices_by_type.get(DeviceType.HEATER, []), False)
            return f"Cooling mode activated. Current temperature: {current_temp}°F"
        
        else:
            return "Please specify 'increase' or 'decrease' for temperature control."
    
    def _get_status_report(self) -> str:
        """Generate comprehensive status report"""
        # Devices by room
        report = ["🏠 Smart Home Status Report\n"]
        
        # Power usage
        report.append(f"⚡ Power Usage: {self.context['power_usage']:.0f}W / {self.thresholds['power_limit']:.0f}W")
        
        # Environmental
        report.append(f"🌡️  Temperature: {self.context['temperature']}°F (Outside: {self.context['outdoor_temp']}°F)")
        report.append(f"💧 Humidity: {self.context['humidity']}%\n")
        
        # Devices by room
        for room, device_names in self.devices_by_room.items():
            if not device_names:
                continue
            
            room_display = room.replace('_', ' ').title()
            active_devices = [self.devices[d].name.replace('_', ' ') 
                              for d in device_names if self.devices[d].state]
            
            if active_devices:
                report.append(f"📍 {room_display}: {', '.join(active_devices)} ON")
            else:
                report.append(f"📍 {room_display}: All devices OFF")
        
        # Security status
        if self.context['security_armed']:
            report.append("\n🔒 Security: ARMED")
        
        # Active modes
        active_modes = []
        if self.context['sleep_mode']:
            active_modes.append('Sleep Mode')
        if self.context['vacation_mode']:
            active_modes.append('Vacation Mode')
        if active_modes:
            report.append(f"🔧 Active Modes: {', '.join(active_modes)}")
        
        return '\n'.join(report)
    
    def _cache_response(self, key: str, response: Dict[str, Any]):
        """Cache responses for frequent commands"""
        # Limit cache size
        if len(self.response_cache) > 100:
            # Remove oldest entries
            oldest_keys = list(self.response_cache.keys())[:20]
            for k in oldest_keys:
                del self.response_cache[k]
        
        self.response_cache[key] = response.copy()
    
    def _schedule_checker(self):
        """Background thread for scheduled operations"""
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                print(f"Schedule error: {e}")
    
    def _context_updater(self):
        """Background thread to update context"""
        while True:
            try:
                # Update time context
                self.context['time_of_day'] = self.get_time_context()
                self.context['day_of_week'] = datetime.now().strftime('%A')
                
                # Update power usage
                total_power = sum(d.power_consumption for d in self.devices.values() if d.state)
                self.context['power_usage'] = total_power
                
                # Check automation rules
                for rule in self.automation_rules:
                    if not rule['enabled']:
                        continue
                    
                    if rule['trigger'] == 'condition':
                        if rule['condition']():
                            rule['action']()
                            self.performance_stats['automation_triggers'] += 1
                
                time.sleep(30)  # Update every 30 seconds
            except Exception as e:
                print(f"Context update error: {e}")
    
    def _command_processor(self):
        """Background thread to process queued commands"""
        while True:
            try:
                if not self.command_queue.empty():
                    command = self.command_queue.get()
                    # Process command asynchronously
                    action = self.understand_command(command['text'])
                    response = self.execute_command(action)
                    if 'callback' in command and callable(command['callback']):
                        command['callback'](response)
                time.sleep(0.1)
            except Exception as e:
                print(f"Command processor error: {e}")
    
    def get_time_context(self) -> str:
        """Get current time period"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"
    
    def _get_season(self) -> str:
        """Get current season"""
        month = datetime.now().month
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "fall"
    
    def _parse_llm_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response with better error handling"""
        if not response_text:
            return None
        try:
            # The response should be a direct JSON string
            return json.loads(response_text)
        except json.JSONDecodeError:
             # If direct parsing fails, try to find a JSON block within the text
            try:
                json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    return json.loads(json_str)
            except Exception as e:
                 print(f"JSON parse error after regex: {e} on response: '{response_text}'")
        except Exception as e:
            print(f"General parse error: {e} on response: '{response_text}'")
        return None
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics"""
        if not self.performance_stats['inference_times']:
            avg_latency = 0
        else:
            avg_latency = statistics.mean(self.performance_stats['inference_times']) * 1000

        total_lookups = self.performance_stats['cache_hits'] + self.performance_stats['cache_misses']
        if total_lookups == 0:
            cache_rate = 0
        else:
            cache_rate = (self.performance_stats['cache_hits'] / total_lookups) * 100
        
        # Calculate tokens per second from LLM
        if self.performance_stats['llm_eval_durations']:
            total_tokens = sum(self.performance_stats['llm_token_counts'])
            total_duration_ns = sum(self.performance_stats['llm_eval_durations'])
            if total_duration_ns > 0:
                total_duration_s = total_duration_ns / 1_000_000_000
                tokens_per_sec = total_tokens / total_duration_s
            else:
                tokens_per_sec = 0.0
        else:
            tokens_per_sec = 0.0

        return {
            'avg_inference_ms': f"{avg_latency:.0f}",
            'tokens_per_second': f"{tokens_per_sec:.1f}",
            'cache_hit_rate': f"{cache_rate:.1f}%",
            'total_commands': self.performance_stats['total_commands'],
            'automation_triggers': self.performance_stats['automation_triggers'],
            'current_power_usage': f"{self.context['power_usage']:.0f}W",
            'energy_saved': f"{self.performance_stats['energy_saved']:.1f}kWh"
        }
    
    def cleanup(self):
        """Clean up resources"""
        print("\n🔧 Shutting down Smart Home Assistant...")
        if not self._gpio_simulation_mode:
            try:
                # Turn off all devices for safety
                for device in self.devices.values():
                    if device.state:
                        GPIO.output(device.pin, GPIO.LOW)
                        device.state = False
                
                GPIO.cleanup()
                print("✅ GPIO cleanup complete")
            except Exception as e:
                print(f"⚠️  Cleanup warning: {e}")
        else:
            print("Skipping GPIO cleanup (simulation mode).")


# Flask Web API with Dashboard
app = Flask(__name__)
CORS(app)
assistant = None

# HTML Dashboard Template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Smart Home Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #121212;
            color: #e0e0e0;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1, h2 {
            color: #ffffff;
            border-bottom: 1px solid #333;
            padding-bottom: 10px;
        }
        .card {
            background: #1e1e1e;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .room-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }
        .device {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            margin: 8px 0;
            background: #2a2a2a;
            border-radius: 8px;
        }
        .switch {
            position: relative;
            display: inline-block;
            width: 60px;
            height: 34px;
        }
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #444;
            transition: .4s;
            border-radius: 34px;
        }
        .slider:before {
            position: absolute;
            content: "";
            height: 26px;
            width: 26px;
            left: 4px;
            bottom: 4px;
            background-color: white;
            transition: .4s;
            border-radius: 50%;
        }
        input:checked + .slider {
            background-color: #007aff;
        }
        input:checked + .slider:before {
            transform: translateX(26px);
        }
        .scene-button {
            padding: 10px 20px;
            margin: 5px;
            border: none;
            border-radius: 8px;
            background-color: #007aff;
            color: white;
            cursor: pointer;
            font-size: 16px;
            transition: background-color 0.3s;
        }
        .scene-button:hover {
            background-color: #0056b3;
        }
        .command-input {
            width: calc(100% - 220px);
            padding: 12px;
            font-size: 16px;
            border: 1px solid #444;
            border-radius: 8px;
            background-color: #2a2a2a;
            color: #e0e0e0;
        }
        .command-input:focus {
            outline: none;
            border-color: #007aff;
        }
        .cmd-btn {
            padding: 12px 20px;
            border: none;
            border-radius: 8px;
            background-color: #34c759;
            color: white;
            cursor: pointer;
            font-size: 16px;
            margin-left: 10px;
        }
        .mic-btn {
             background-color: #ff3b30;
        }
        #commandResponse {
            margin-top: 15px;
            padding: 10px;
            background: #2a2a2a;
            border-radius: 8px;
            min-height: 20px;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
        }
        .stat-item {
            text-align: center;
            padding: 15px;
            background: #2a2a2a;
            border-radius: 8px;
        }
        .stat-value {
            font-size: 28px;
            font-weight: bold;
            color: #007aff;
        }
        .stat-label {
            font-size: 14px;
            color: #8e8e93;
            text-transform: uppercase;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🏠 Smart Home Dashboard</h1>
        
        <div class="card">
            <h2>Voice Command</h2>
            <input type="text" id="commandInput" class="command-input" placeholder="Type a command or speak...">
            <button onclick="sendCommand()" class="cmd-btn">Send</button>
            <button onclick="startVoiceRecognition()" class="cmd-btn mic-btn">🎤 Speak</button>
            <div id="commandResponse"></div>
        </div>
        
        <div class="card">
            <h2>Quick Scenes</h2>
            <div id="scenes"></div>
        </div>
        
        <div class="card">
            <h2>Status Overview</h2>
            <div class="stats" id="stats"></div>
        </div>
        
        <div class="card">
            <h2>Rooms & Devices</h2>
            <div class="room-grid" id="rooms"></div>
        </div>
    </div>
    
    <script>
        let recognition;
        
        // Initialize speech recognition if available
        if ('webkitSpeechRecognition' in window) {
            recognition = new webkitSpeechRecognition();
            recognition.continuous = false;
            recognition.interimResults = false;
            recognition.lang = 'en-US';
            
            recognition.onresult = function(event) {
                const command = event.results[0][0].transcript;
                document.getElementById('commandInput').value = command;
                sendCommand();
            };

            recognition.onstart = function() {
                document.getElementById('commandInput').placeholder = "Listening...";
            };

            recognition.onend = function() {
                document.getElementById('commandInput').placeholder = "Type a command or speak...";
            };
        }
        
        function startVoiceRecognition() {
            if (recognition) {
                recognition.start();
            } else {
                alert("Speech recognition not supported in this browser");
            }
        }
        
        async function sendCommand() {
            const input = document.getElementById('commandInput').value;
            if (!input) return;
            
            try {
                const response = await fetch('/api/command', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: input})
                });
                const data = await response.json();
                document.getElementById('commandResponse').innerHTML = 
                    `<p><strong>Response:</strong> ${data.response.replace(/\\n/g, '<br>')}</p>`;
                document.getElementById('commandInput').value = '';
                loadStatus();
            } catch (error) {
                console.error('Error:', error);
                document.getElementById('commandResponse').innerText = 'Error sending command.';
            }
        }
        
        async function toggleDevice(deviceName) {
            try {
                await fetch('/api/device/toggle', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({device: deviceName})
                });
                loadStatus();
            } catch (error) {
                console.error('Error:', error);
            }
        }
        
        async function activateScene(sceneName) {
            try {
                await fetch('/api/scene/activate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({scene: sceneName})
                });
                loadStatus();
            } catch (error) {
                console.error('Error:', error);
            }
        }
        
        async function loadStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // Update stats
                const perf = data.performance;
                const statsHtml = `
                    <div class="stat-item"><div class="stat-value">${data.stats.power_usage}</div><div class="stat-label">Power</div></div>
                    <div class="stat-item"><div class="stat-value">${data.stats.temperature}</div><div class="stat-label">Temp</div></div>
                    <div class="stat-item"><div class="stat-value">${data.stats.active_devices}/${data.stats.total_devices}</div><div class="stat-label">Active Devices</div></div>
                    <div class="stat-item"><div class="stat-value">${perf.avg_inference_ms}ms</div><div class="stat-label">Avg Latency</div></div>
                    <div class="stat-item"><div class="stat-value">${perf.tokens_per_second}</div><div class="stat-label">Tokens/Sec</div></div>
                    <div class="stat-item"><div class="stat-value">${perf.cache_hit_rate}</div><div class="stat-label">Cache Rate</div></div>
                `;
                document.getElementById('stats').innerHTML = statsHtml;
                
                // Update rooms and devices
                const roomsHtml = Object.entries(data.rooms).map(([room, devices]) => `
                    <div class="card">
                        <h3>${room.replace(/_/g, ' ').toUpperCase()}</h3>
                        ${devices.map(device => `
                            <div class="device">
                                <span>${device.name.replace(/_/g, ' ')}</span>
                                <label class="switch">
                                    <input type="checkbox" ${device.state ? 'checked' : ''} 
                                           onchange="toggleDevice('${device.name}')">
                                    <span class="slider"></span>
                                </label>
                            </div>
                        `).join('')}
                    </div>
                `).join('');
                document.getElementById('rooms').innerHTML = roomsHtml;
                
                // Update scenes
                const scenesHtml = data.scenes.map(scene => `
                    <button class="scene-button" onclick="activateScene('${scene}')">${scene.replace(/_/g, ' ')}</button>
                `).join('');
                document.getElementById('scenes').innerHTML = scenesHtml;
                
            } catch (error) {
                console.error('Error loading status:', error);
            }
        }
        
        // Auto-refresh every 5 seconds
        setInterval(loadStatus, 5000);
        window.onload = loadStatus;
        
        // Handle Enter key in command input
        document.getElementById('commandInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') sendCommand();
        });
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    """Serve the web dashboard"""
    return render_template_string(DASHBOARD_HTML)

@app.route('/api/command', methods=['POST'])
def api_command():
    """Process voice/text commands"""
    data = request.json
    if not data or 'text' not in data:
        return jsonify({'error': 'Missing text field'}), 400
    
    start_time = time.time()
    action = assistant.understand_command(data['text'])
    response = assistant.execute_command(action)
    elapsed_ms = (time.time() - start_time) * 1000
    
    return jsonify({
        'response': response,
        'action': action,
        'elapsed_ms': f"{elapsed_ms:.0f}"
    })

@app.route('/api/status', methods=['GET'])
def api_status():
    """Get current system status"""
    # Organize devices by room
    rooms = {}
    for room, device_names in assistant.devices_by_room.items():
        rooms[room] = [
            {
                'name': name,
                'state': assistant.devices[name].state,
                'type': assistant.devices[name].device_type.value,
                'power': assistant.devices[name].power_consumption
            }
            for name in device_names
        ]
    
    return jsonify({
        'rooms': rooms,
        'stats': {
            'power_usage': f"{assistant.context['power_usage']:.0f}W",
            'temperature': f"{assistant.context['temperature']}°F",
            'active_devices': sum(1 for d in assistant.devices.values() if d.state),
            'total_devices': len(assistant.devices)
        },
        'scenes': list(assistant.scenes.keys()),
        'performance': assistant.get_performance_summary()
    })

@app.route('/api/device/toggle', methods=['POST'])
def api_toggle_device():
    """Toggle a specific device"""
    data = request.json
    device_name = data.get('device')
    
    if not device_name or device_name not in assistant.devices:
        return jsonify({'error': 'Device not found'}), 404
    
    assistant._toggle_devices([device_name])
    new_state = assistant.devices[device_name].state
    
    return jsonify({'success': True, 'new_state': new_state})

@app.route('/api/scene/activate', methods=['POST'])
def api_activate_scene():
    """Activate a scene"""
    data = request.json
    scene_name = data.get('scene')
    
    response = assistant._activate_scene(scene_name)
    return jsonify({'response': response})

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Enhanced Smart Home Assistant")
    parser.add_argument("--model", type=str, default="deepseek-r1:7b",
                        help="Ollama model name (e.g., deepseek-r1:7b, llama2:7b)")
    parser.add_argument("--no-api", action="store_true",
                        help="Disable web API")
    parser.add_argument("--port", type=int, default=5000,
                        help="Web API port")
    args = parser.parse_args()
    
    global assistant
    try:
        # Initialize assistant
        assistant = SmartHomeAssistant(model_name=args.model)
        
        # Start web API if not disabled
        if not args.no_api:
            api_thread = threading.Thread(
                target=lambda: app.run(host='0.0.0.0', port=args.port, debug=False),
                daemon=True
            )
            api_thread.start()
            print(f"\n🌐 Web Dashboard available at http://127.0.0.1:{args.port}")
        
        print("\n🎤 Smart Home Assistant Ready!")
        print("💬 Commands: 'status', 'perf', 'help', or 'quit'")
        print("🗣️  Or just tell me what you want!\n")
        
        # Interactive loop
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye']:
                    break
                elif user_input.lower() == 'help':
                    print("\nAvailable commands:")
                    print("- Natural language: 'turn on the lights', 'I'm cold', etc.")
                    print("- Scenes: 'activate movie night', 'bedtime', etc.")
                    print("- Status: 'status' or 'what's on?'")
                    print("- Performance: 'perf'")
                    continue
                elif user_input.lower() == 'perf':
                    perf = assistant.get_performance_summary()
                    for key, value in perf.items():
                        print(f"- {key.replace('_', ' ').title()}: {value}")
                    continue
                
                # Process command
                start_time = time.time()
                action = assistant.understand_command(user_input)
                
                response = assistant.execute_command(action)
                elapsed = (time.time() - start_time) * 1000
                
                print(f"\n🤖 Assistant: {response}")

                if action and action.get('reasoning'):
                    print(f"💭 Logic: {action['reasoning']}")
                print(f"⏱️  [{elapsed:.0f}ms]\n")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error during loop: {e}")
    
    except Exception as e:
        print(f"❌ Fatal error during initialization: {e}")
    finally:
        if assistant:
            assistant.cleanup()
        print("\n👋 Goodbye!")

if __name__ == "__main__":
    main()
