# Edge AI Smart Home Assistant
This project is a sophisticated, privacy-focused smart home assistant designed to run locally on ARM-based edge devices like the NVIDIA Jetson or Raspberry Pi. It uses a local Ollama instance for natural language understanding, allowing for complex and conversational command processing without relying on cloud services. The assistant can control GPIO-connected devices, manage energy usage, and be controlled via a command-line interface or a web-based dashboard with a full API.

# 🤖 Edge AI on ARM Architecture
This project serves as a powerful demonstration of Edge AI running efficiently on the ARM architecture. By leveraging ARM-based single-board computers (like the NVIDIA Jetson or Raspberry Pi), we can run a sophisticated language model locally, bringing the power of AI to the edge with significant advantages:

Privacy-Focused: All data and command processing happen on your local network. Nothing is sent to the cloud, ensuring your personal information remains private.

Low Latency: Commands are executed instantly without the round-trip delay of cloud-based services, resulting in a more responsive and natural user experience.

Power Efficiency: The ARM-based architecture provides the computational power needed for AI inference while consuming significantly less power than traditional desktop or server hardware.

Reliability: The system continues to function perfectly even if your internet connection goes down.

This assistant proves that complex, practical AI applications are not limited to data centers and can be deployed effectively in a home environment on accessible, energy-efficient hardware.

# ✨ Features
Local First, Privacy-Focused: All command processing is done locally using Ollama.

Natural Language Understanding: Powered by the Deepseek model, it understands complex, conversational commands.

Direct GPIO Control: Interfaces directly with hardware via GPIO pins to control lights, fans, etc.

Web Dashboard & API: A clean web interface and a full API for control and monitoring.

Intelligent Energy Management: Proactively saves energy by turning off unused devices.

Customizable Scenes & Automations: Easily define custom scenes and automation rules.

Performance Monitoring: Real-time metrics for LLM speed and command latency.

# 🖥️ Web Dashboard & API
The assistant includes a web-based dashboard and a comprehensive API, allowing for easy control and monitoring of your smart home.

Dashboard
The dashboard provides a user-friendly interface for all major functions:

Voice and Text Commands:

Device Control:

Status Reports:

API Endpoints
The project runs a Flask server with the following endpoints:

GET /: Serves the main dashboard.

POST /api/command: Processes text/voice commands.

GET /api/status: Returns the current status of all devices and context.

POST /api/device/toggle: Toggles a specific device.

POST /api/scene/activate: Activates a predefined scene.

📊 Performance Metrics
The assistant is optimized to run efficiently on edge devices. Here are some real-world performance metrics captured during operation on an NVIDIA Jetson:

Metric

Value

Description

Tokens/Second

~12.0

The generation speed of the local Deepseek LLM.

Avg. Latency

~1-8s

Varies based on command complexity and caching.

Power Usage

~60-140W

Varies based on the number of active devices.

Cache Hit Rate

~5-15%

Reduces latency for repeated commands.

These metrics demonstrate the viability of running a powerful, responsive AI assistant directly on an energy-efficient ARM device.

🚀 Getting Started
Follow these instructions to get your smart home assistant up and running.

Prerequisites
An ARM-based single-board computer (e.g., NVIDIA Jetson, Raspberry Pi) with a compatible GPIO library installed (e.g., Jetson.GPIO, RPi.GPIO).

Python 3.8 or higher.

Installation & Setup
Clone the repository:

git clone [https://github.com/fidel-makatia/EdgeAI_Ollama.git](https://github.com/fidel-makatia/EdgeAI_Ollama.git)
cd EdgeAI_Ollama

Create and activate a virtual environment:

python3 -m venv smart_home_env
source smart_home_env/bin/activate

Install Ollama:

curl -fsSL [https://ollama.com/install.sh](https://ollama.com/install.sh) | sh

Pull an Ollama model: The script defaults to deepseek-r1:7b, which is recommended for its balance of performance and understanding.

# Pull recommended model

ollama pull deepseek-r1:7b

# Alternative models you can try:

ollama pull llama2:7b
ollama pull mistral:7b
ollama pull phi:2.7b # Smaller, faster model

Install required Python packages:

pip install ollama flask flask-cors schedule Jetson.GPIO

# Optional: For environmental sensors

pip install adafruit-circuitpython-dht

Running the Assistant
Execute the main script from your terminal.

# With default model (deepseek-r1:7b)

python3 smart_home_assistant.py

# With a different model

python3 smart_home_assistant.py --model llama2:7b

# With custom port for web dashboard

python3 smart_home_assistant.py --port 8080

# CLI only (no web interface)

python3 smart_home_assistant.py --no-api

Once running, you can access the web dashboard at http://<your-device-ip>:5000 (or your custom port).

⚙️ Usage & Output
You can interact with the assistant through the CLI or the web dashboard.

Example Output
Here is an example of the interaction with the assistant in the command-line interface:

You: I'm cold
🤔 Using Deepseek model for command...
🤖 LLM Raw Output: {
"intent": "set_temperature",
"devices": null,
"scene": null,
"value": "increase",
"reasoning": "User is cold, so I will increase the temperature. This will turn on heaters and turn off ACs."
}

🤖 Assistant: Heating mode activated. Current temperature: 72°F
💭 Logic: User is cold, so I will increase the temperature. This will turn on heaters and turn off ACs.
⏱️ [1234ms]

Special Commands
status: Get a full report of all device states and context.

perf: See the latest performance metrics.

help: Display available command types.

quit: Shut down the assistant.

📂 File Structure
The repository is structured as follows:

EdgeAI_Ollama/
├── assets/
│ ├── UI1.png
│ ├── UI2.png
│ ├── UI3.png
│ └── stats.png
├── smart_home_assistant.py # Main application script
├── requirements.txt # Python dependencies
└── README.md # Project documentation

🔧 Configuration
All device, scene, and automation configurations are handled within the smart_home_assistant.py script.

Adding a New Device
Open the script and navigate to the \_init_devices method.

Add a new entry to the self.devices dictionary. You will need to define:

name: A unique identifier (e.g., office_light).

pin: The GPIO pin number (BOARD mode) the device is connected to.

device_type: The type of device (e.g., DeviceType.LIGHT).

aliases: A list of friendly names for the device.

room: The room the device is in.

power_consumption: The device's power usage in watts (for energy monitoring).

Example:

'office_light': Device(
name='office_light',
pin=33,
device_type=DeviceType.LIGHT,
aliases=['office light', 'desk lamp'],
room='office',
power_consumption=15
),

Creating a New Scene
Navigate to the \_init_automation_rules method.

Add a new entry to the self.scenes dictionary.

Define the devices you want to control and their desired state (True for on, False for off).

Example:

'work_mode': {
'devices': {
'office_light': True,
'living_room_light': False,
'living_room_fan': False,
},
'description': 'Sets up the office for work.'
},

🛠️ Technology Stack
Backend: Python 3

Web Framework: Flask

Natural Language Processing: Ollama with Deepseek

Hardware Interface: Jetson.GPIO (or other compatible GPIO library)

Scheduling: schedule

Frontend: HTML, CSS, JavaScript (no external frameworks)

🤝 Contributing
Contributions are welcome! If you have ideas for new features, improvements, or bug fixes, please feel free to:

Fork the repository.

Create a new branch (git checkout -b feature/your-feature-name).

Make your changes.

Commit your changes (`git commit -m 'Add some feature
