# Coffee Voice Agent ROS2 Package

A ROS2 package that integrates the LiveKit Coffee Barista Voice Agent with the Coffee Buddy robot system through a clean bridge architecture with unified messaging.

## Overview

This package provides ROS2 integration for the Coffee Barista Voice Agent while preserving its interactive console mode functionality. The voice agent runs as a standalone application with full console controls, while a separate ROS2 bridge node provides system integration via WebSocket communication using **unified status messages** for robot coordination.

## Implementation Versions

This package now includes **two implementations** of the voice agent:

### **🏗️ Refactored Version (Recommended)**
- **Files**: `main.py` + modular structure (`state/`, `agents/`, `tools/`)
- **Launcher**: `./run_main.sh`
- **Architecture**: Clean file-based modular organization
- **Benefits**: Better maintainability, easier testing, cleaner separation of concerns
- **Status**: ✅ **Production ready** - Same functionality with better organization

### **📚 Original Version (Reference)**
- **Files**: `livekit_voice_agent.py` (monolithic, 1109 lines)
- **Launcher**: `./run_voice_agent_original.sh` 
- **Architecture**: Single-file implementation
- **Benefits**: Proven, stable, all logic in one place
- **Status**: 📖 **Preserved for reference** - Fully functional but less maintainable

**Both implementations provide identical functionality** - choose based on your preference for code organization.

## Unified Messaging Architecture

### **Key Design Principle: Single Source of Truth**

The voice agent now uses a **unified messaging approach** that provides all robot coordination information through two primary message types:

1. **`AgentStatus`** - Comprehensive agent state for robot coordination
2. **`ToolEvent`** - Function tool call tracking for UI and analytics

This replaces the previous fragmented approach of separate state, emotion, and TTS event messages, ensuring **atomic updates** and **consistent state** for the orchestrator.

## Refactoring Details

The refactored version was created through careful **file-based modular extraction** while preserving all original functionality:

### **What Was Extracted**

| **Component** | **Original Location** | **New Location** | **Lines** | **Purpose** |
|---------------|----------------------|------------------|-----------|-------------|
| **StateManager** | Lines 40-566 in monolith | `state/state_manager.py` | 540 | State transitions, timeouts, virtual queue |
| **CoffeeBaristaAgent** | Lines 568-1039 in monolith | `agents/coffee_barista_agent.py` | 358 | I/O services, TTS, wake word, WebSocket |
| **Function Tools** | Agent methods | `tools/coffee_tools.py` | 82 | Coffee-related functions (menu, time, etc.) |
| **Configuration** | Scattered constants | `config/settings.py` | 25 | Environment variables, timeouts |
| **Instructions** | Large string | `config/instructions.py` | 50 | LLM system prompt |
| **Utilities** | Helper methods | `utils/*.py` | 150 | Greetings, animations, announcements |

### **Key Improvements**

- **🧩 Modular Design**: 1109-line monolith → 7 focused files
- **🔧 Clean Tool Registration**: Programmatic `function_tool()` registration vs duplicate methods
- **🧪 Testable Components**: Each class can be unit tested independently  
- **📝 Maintainable**: Add features by editing specific files, not searching through monolith
- **⚙️ Configuration Management**: Environment variables and settings centralized
- **🛠️ Reusable Utilities**: Greeting selection, animation descriptions, announcement formatting
- **📡 Unified Messaging**: Single `AgentStatus` message for robot coordination

### **What Was Preserved**

✅ **All complex logic**: State management, timeout handling, virtual request batching  
✅ **Threading model**: Same 3-thread architecture (main, wake word, WebSocket)  
✅ **Session events**: Conversation flow, goodbye detection, timer management  
✅ **TTS processing**: Emotion extraction from `emotion:text` format  
✅ **Resource management**: Proper cleanup, state transitions, error handling  
✅ **Behavior**: Identical user experience and functionality

### **Refactoring Principles**

- **No Logic Changes**: Pure organizational refactoring, zero behavior modification
- **Composition over Services**: Avoided over-engineering with service abstractions  
- **Single Responsibility**: Each file has a clear, focused purpose
- **Dependency Injection**: Components accept dependencies for better testing
- **Proven Patterns**: Used established LiveKit patterns (programmatic tool registration)

## Features

- **🎙️ Wake Word Detection**: "Hey barista" activation with Porcupine
- **🗣️ Voice Conversation**: STT, LLM, and TTS using LiveKit/OpenAI  
- **😊 Emotion Processing**: Emotion-aware responses with animated expressions
- **☕ Coffee Functions**: Menu, recommendations, and ordering guidance with tool tracking
- **🖥️ Console Mode**: Full interactive controls (Ctrl+B, Q) in terminal
- **🌐 ROS2 Bridge**: WebSocket-based integration with Coffee Buddy system
- **📡 Virtual Requests**: External coffee requests via ROS2 topics
- **🔧 Tool Events**: Real-time function tool call tracking for UI feedback

## Architecture

### **File Structure**
```
coffee_voice_agent/
├── scripts/
│   ├── main.py                        # 🏗️ Refactored voice agent entry point
│   ├── run_main.sh                    # 🏗️ Refactored version launcher  
│   ├── livekit_voice_agent.py         # 📚 Original monolithic voice agent
│   ├── run_voice_agent_original.sh   # 📚 Original version launcher
│   ├── state/
│   │   └── state_manager.py           # 🏗️ Extracted StateManager (540 lines)
│   ├── agents/
│   │   └── coffee_barista_agent.py   # 🏗️ CoffeeBaristaAgent with programmatic tools
│   ├── tools/
│   │   └── coffee_tools.py            # 🏗️ Function tool implementations with event tracking
│   ├── config/
│   │   ├── settings.py                # 🏗️ Configuration and environment variables
│   │   └── instructions.py            # 🏗️ LLM system instructions
│   └── utils/
│       ├── greeting_data.py           # 🏗️ Greeting utilities
│       ├── animation_data.py          # 🏗️ Eye animation descriptions
│       └── announcement_data.py       # 🏗️ Order announcement templates
├── coffee_voice_agent/
│   └── voice_agent_bridge.py          # ROS2 bridge node with unified messaging
└── launch/
    ├── voice_agent_bridge.launch.py   # Bridge only
    └── voice_agent_system.launch.py   # Voice agent + bridge together
```

### **Refactored Architecture Benefits**
- **🧩 Modular**: StateManager (540 lines) separate from Agent (358 lines)
- **🔧 Clean Tools**: Programmatic function registration, no code duplication
- **⚙️ Configuration**: Environment variables and instructions extracted
- **🛠️ Utilities**: Reusable components for greetings, animations, announcements
- **🧪 Testable**: Each component can be tested independently
- **📝 Maintainable**: Easy to add/remove features, clear responsibilities
- **📡 Unified Messaging**: Single message for robot coordination, atomic updates

### Communication Flow
```
┌─────────────────┐    WebSocket     ┌─────────────────┐    ROS2      ┌──────────────┐
│  Voice Agent    │◄────────────────►│  ROS2 Bridge    │◄────────────►│ Coffee Buddy │
│  (Console Mode) │  AGENT_STATUS    │  (Bridge Node)  │ AgentStatus │   System     │
│  Interactive    │  TOOL_EVENT      │  Integration    │ ToolEvent   │              │
└─────────────────┘   Port 8080      └─────────────────┘             └──────────────┘
```

### **Unified Messaging Architecture**

#### **🔄 WebSocket Events (Voice Agent → Bridge)**
- **`AGENT_STATUS`**: Comprehensive status updates (behavioral mode, speech status, emotion, text, etc.)
- **`TOOL_EVENT`**: Function tool execution tracking (started, completed, failed)
- **`STARTUP`**: Agent initialization and version info
- **`ACKNOWLEDGMENT`**: Command confirmations

#### **📡 ROS2 Messages (Bridge → Robot System)**
- **`AgentStatus`**: Single unified message containing all robot coordination context
- **`ToolEvent`**: Discrete tool call events for UI feedback and analytics

### **TTS and Audio Processing Flow**

Understanding how text-to-speech and audio synthesis works in the refactored architecture:

#### **🔄 Two TTS Pathways**

**Path 1: Normal Conversation (User-initiated)**
```
User Speech → STT → LLM → CoffeeBaristaAgent.tts_node() → Emotion Processing → Audio Playback
                                                          ↓
                                                    Agent Status Events
```

**Path 2: Manual Announcements (System-initiated)**
```
Virtual Requests/Greetings → StateManager.say_with_emotion() → session.say() → CoffeeBaristaAgent.tts_node() → Audio Playback
                                                                                                               ↓
                                                                                                         Agent Status Events
```

#### **📍 TTS Processing Components**

**1. TTS Override - `agents/coffee_barista_agent.py` (Lines 89-193)**
- **Method**: `async def tts_node(self, text, model_settings=None)`
- **Role**: **Central TTS bottleneck** - all speech goes through here
- **Functions**:
  - Intercepts streaming text from LLM or manual calls
  - Processes `emotion:text` delimiter format in real-time
  - Extracts emotions from first 50 characters of text stream
  - Updates agent's emotional state
  - Logs animated eye expressions
  - Updates speech text tracking for status events
  - Passes clean text to LiveKit's default TTS

**2. Manual TTS - `state/state_manager.py` (Lines 531-569)**
- **Method**: `async def say_with_emotion(self, text: str, emotion: str = None)`
- **Role**: Direct TTS for system announcements
- **Functions**:
  - Used for greetings, virtual request announcements, timeouts
  - Calls `await self.session.say(text)` directly
  - Still routes through `tts_node()` override for emotion processing
  - Bypasses LLM but preserves emotion handling

**3. Agent Status Events - `state/state_manager.py` (Lines 577-607)**
- **Method**: `async def _send_agent_status(...)`
- **Role**: Unified status broadcasting
- **Functions**:
  - Sends comprehensive agent status via WebSocket
  - Includes behavioral mode, speech status, emotion, text, conversation phase
  - Triggered by state transitions and speech events

**4. Tool Event Tracking - `tools/coffee_tools.py` (Lines 18-26, all tools)**
- **Function**: `async def send_tool_event(...)`
- **Role**: Track function tool execution
- **Functions**:
  - Send "started" events when tools begin execution
  - Send "completed" events with results when tools finish
  - Provide parameters and results for UI feedback

#### **🎵 Audio Synthesis and Playback**

**Final Audio Generation (Line 190 in `coffee_barista_agent.py`):**
```python
async for audio_frame in Agent.default.tts_node(self, processed_text, model_settings):
    yield audio_frame
```

**Audio Pipeline:**
1. **OpenAI TTS**: Uses model "tts-1" with voice "nova" (configurable)
2. **LiveKit Streaming**: Real-time audio frame streaming to connected clients
3. **Client Playback**: Audio plays through browser, room system, or connected devices

#### **🎭 Emotion Processing Integration**

**Emotion Flow in TTS Override:**
```python
# 1. Text stream arrives (with potential emotion:text format)
async for text_chunk in text:
    if ":" in first_chunk_buffer:
        # 2. Extract emotion from delimiter
        emotion = parts[0].strip()
        text_after_delimiter = parts[1]
        
        # 3. Update emotional state
        if emotion != self.state_manager.current_emotion:
            self.state_manager.current_emotion = emotion
            self.state_manager.log_animated_eyes(emotion)
        
        # 4. Yield clean text for audio synthesis
        yield text_after_delimiter
        
        # 5. Update speech text tracking for status events
        self.state_manager.current_speech_full_text += text_after_delimiter
```

#### **⚙️ Technical Details**

**Threading Model:**
- **Main Thread**: LiveKit agent and TTS processing
- **Wake Word Thread**: Porcupine audio processing (synchronous)
- **WebSocket Thread**: Order notification server

**Audio Configuration:**
- **STT**: OpenAI Whisper ("whisper-1")
- **TTS**: OpenAI TTS ("tts-1", voice configurable via `VOICE_AGENT_VOICE`)
- **VAD**: Silero Voice Activity Detection
- **Streaming**: Real-time audio frame streaming via LiveKit

**State Synchronization:**
- All TTS calls update `StateManager.current_emotion`
- Emotion changes trigger eye animation logging
- Session events coordinate conversation flow and TTS timing
- Agent status events provide atomic state updates

**Performance Characteristics:**
- **Minimal Buffering**: Only first 50 characters checked for emotion
- **Streaming**: Audio synthesis starts as soon as clean text is available
- **Low Latency**: Real-time processing for responsive conversations
- **Unified Events**: Single AgentStatus message provides complete context

## Dependencies

### Environment Variables
```bash
export OPENAI_API_KEY="your_openai_api_key"           # Required
export PORCUPINE_ACCESS_KEY="your_porcupine_key"      # Optional for wake word
export VOICE_AGENT_VOICE="nova"                       # Optional TTS voice  
export VOICE_AGENT_TEMPERATURE="0.7"                  # Optional LLM temperature
export WEBSOCKET_HOST="localhost"                     # Optional WebSocket host
export WEBSOCKET_PORT="8080"                          # Optional WebSocket port
```

### ROS2 Dependencies
- `rclpy`
- `std_msgs` 
- `geometry_msgs`
- `coffee_voice_agent_msgs` (custom message package)
- `websockets` (Python package)

### Python Dependencies (in setup.py)
- `livekit`
- `livekit-agents[openai,deepgram,silero,turn-detector]`
- `pvporcupine==3.0.5`
- `pvrecorder==1.2.7`
- `python-dotenv`
- `websockets`

## Installation & Usage

### 1. Build the Package
```bash
cd coffee_ws
# Build messages first
colcon build --packages-select coffee_voice_agent_msgs
# Build voice agent package
colcon build --packages-select coffee_voice_agent
source install/setup.bash
```

### 2. Run Voice Agent (Console Mode)

#### **🏗️ Refactored Version (Recommended)**
```bash
# Run refactored version with modular architecture
./src/coffee_voice_agent/scripts/run_main.sh

# Or after building:
./install/coffee_voice_agent/share/coffee_voice_agent/scripts/run_main.sh
```

#### **📚 Original Version (Reference)**
```bash
# Run original monolithic version
./src/coffee_voice_agent/scripts/run_voice_agent_original.sh

# Or after building:
./install/coffee_voice_agent/share/coffee_voice_agent/scripts/run_voice_agent_original.sh
```

**Console Controls (Both Versions):**
- `[Ctrl+B]` - Toggle between Text/Audio mode
- `[Q]` - Quit the application
- Wake word: Say **"hey barista"** to activate

**Which Version to Use?**
- **🏗️ Use refactored version** (`./run_main.sh`) for new development, easier maintenance, better testing
- **📚 Use original version** (`./run_voice_agent_original.sh`) if you prefer single-file simplicity or need proven stability

### **Quick Start Guide**

```bash
# 🚀 RECOMMENDED: Run refactored modular version
./run_main.sh

# 📚 REFERENCE: Run original monolithic version  
./run_voice_agent_original.sh
```

### 3. ROS2 Integration (Optional)

**Bridge Only** (if voice agent running separately):
```bash
ros2 launch coffee_voice_agent voice_agent_bridge.launch.py
```

**Complete System** (voice agent + bridge together):
```bash  
ros2 launch coffee_voice_agent voice_agent_system.launch.py
```

## ROS2 Topics (Bridge Node)

### Publishers (Voice Agent → ROS2)
- `/voice_agent/status` (`coffee_voice_agent_msgs/AgentStatus`) - **Unified agent status for robot coordination**
- `/voice_agent/tool_events` (`coffee_voice_agent_msgs/ToolEvent`) - **Function tool call tracking**  
- `/voice_agent/connected` (`std_msgs/Bool`) - Bridge connection status

### Subscribers (ROS2 → Voice Agent)
- `/voice_agent/virtual_requests` (`std_msgs/String`) - External coffee requests (JSON)
- `/voice_agent/commands` (`std_msgs/String`) - Voice agent commands (JSON)

## Message Types

### AgentStatus Message
```
# Behavioral mode: "dormant", "active", "connecting", "disconnecting"
string behavioral_mode

# Speech status: "idle", "speaking"  
string speech_status

# Current emotion: "friendly", "excited", "curious", "sleepy", etc.
string emotion

# Speech text (preview when speaking, full text when idle)
string speech_text

# Previous emotion for smooth transitions
string previous_emotion

# Conversation phase: "", "greeting", "discussion", "announcement", "goodbye"
string conversation_phase

# Last function tool used: "get_current_time", "get_coffee_menu", "", etc.
string last_tool_used

# Timestamp when the status was generated
builtin_interfaces/Time timestamp
```

### ToolEvent Message
```
# Tool name: "get_current_time", "get_coffee_menu", etc.
string tool_name

# Input parameters (JSON string array)
string[] parameters

# Tool output/result text
string result

# Status: "started", "completed", "failed"
string status

# Timestamp when the tool event occurred
builtin_interfaces/Time timestamp
```

## Virtual Requests

Send coffee requests to the voice agent via ROS2:

```bash
# New coffee order
ros2 topic pub /voice_agent/virtual_requests std_msgs/String '{
  "data": "{\"request_type\": \"NEW_COFFEE_REQUEST\", \"content\": \"Espresso\", \"priority\": \"normal\"}"
}'

# Order ready notification
ros2 topic pub /voice_agent/virtual_requests std_msgs/String '{
  "data": "{\"request_type\": \"ORDER_READY\", \"content\": \"Americano\", \"priority\": \"urgent\"}"
}'

# Order processing update
ros2 topic pub /voice_agent/virtual_requests std_msgs/String '{
  "data": "{\"request_type\": \"ORDER_PROCESSING\", \"content\": \"Cappuccino\", \"priority\": \"normal\"}"
}'
```

**Note:** The bridge automatically adds order IDs to create announcements like:
- *"New order alert! We have a Espresso (Order ABC123) request coming in!"*
- *"Order ready for pickup: Americano (Order XYZ789)!"*

**Message Format:**
- `request_type`: Type of request (NEW_COFFEE_REQUEST, ORDER_READY, ORDER_PROCESSING, etc.)
- `content`: Coffee type or order description  
- `priority`: Request priority (normal, urgent, low)

**⚠️ Important:** The `content` field should avoid colons (`:`) as they interfere with the voice agent's `emotion:text` delimiter system. Order IDs are automatically formatted as `(Order ABC123)` instead of `(Order: ABC123)` to prevent parsing conflicts.

## Robot Orchestration

### Agent Status Integration
```python
# Subscribe to unified agent status for comprehensive robot coordination
def agent_status_callback(msg):
    # Coordinate based on behavioral mode
    if msg.behavioral_mode == "dormant":
        enable_idle_mode()
    elif msg.behavioral_mode == "active":
        enable_conversation_mode()
    
    # Coordinate speech animations
    if msg.speech_status == "speaking":
        # Start speech animation with full context
        trigger_speech_animation(
            emotion=msg.emotion,
            text_preview=msg.speech_text,
            conversation_phase=msg.conversation_phase
        )
    elif msg.speech_status == "idle":
        # Return to listening pose
        return_to_neutral()
    
    # Handle conversation phases
    if msg.conversation_phase == "greeting":
        focus_on_user()
    elif msg.conversation_phase == "announcement":
        attention_getting_gesture()
    
    # Show last tool used context
    if msg.last_tool_used:
        update_context_display(msg.last_tool_used)

# Subscribe to tool events for UI feedback
def tool_event_callback(msg):
    if msg.status == "started":
        show_thinking_indicator(msg.tool_name)
    elif msg.status == "completed":
        hide_thinking_indicator()
        display_tool_result(msg.result)
```

### Topic Monitoring
```bash
# Monitor unified agent status
ros2 topic echo /voice_agent/status

# Monitor tool events
ros2 topic echo /voice_agent/tool_events

# Monitor bridge connection
ros2 topic echo /voice_agent/connected
```

## Configuration

### Launch File Parameters
```bash
# Bridge configuration
ros2 launch coffee_voice_agent voice_agent_bridge.launch.py \
    voice_agent_host:=192.168.1.100 \
    voice_agent_port:=8080 \
    reconnect_interval:=5.0

# System configuration  
ros2 launch coffee_voice_agent voice_agent_system.launch.py \
    voice_agent_port:=8080 \
    bridge_reconnect_interval:=3.0
```

## Smart Mode Detection

The bash launcher automatically detects the execution environment:

- **Interactive Terminal**: Uses console mode with full controls
- **Non-Interactive** (ROS2 launch): Automatically switches to start mode
- **Environment Setup**: Loads `.env` files and validates prerequisites

## Integration with Coffee Buddy

### 1. Expression System
```bash
# Bridge provides unified status for expression coordination
ros2 topic echo /voice_agent/status
```

### 2. Coffee Machine Integration  
```bash
# Send machine status updates to voice agent
ros2 topic pub /voice_agent/virtual_requests std_msgs/String '{
  "data": "{\"request_type\": \"ORDER_PROCESSING\", \"content\": \"Your Espresso is brewing!\", \"priority\": \"normal\"}"
}'
```

### 3. System Orchestration
```python
# Include in larger system launch files
IncludeLaunchDescription(
    PythonLaunchDescriptionSource([
        FindPackageShare('coffee_voice_agent'),
        '/launch/voice_agent_system.launch.py'
    ])
)
```

## Troubleshooting

### Voice Agent Issues
```bash
# Missing API keys
[ERROR] Missing required environment variables: ['OPENAI_API_KEY']
# Solution: Set OPENAI_API_KEY in environment or .env file

# Wake word not working  
[INFO] Wake Word Detection: ❌ Disabled (always-on mode)
# Solution: Set PORCUPINE_ACCESS_KEY environment variable

# Console mode not working via ROS2 launch
[WARNING] Not running in an interactive terminal
# Solution: Use direct script execution for console mode
```

### Bridge Connection Issues
```bash
# Bridge cannot connect to voice agent
[ERROR] WebSocket connection error: [Errno 111] Connection refused
# Solution: Ensure voice agent is running and WebSocket server is active

# Check WebSocket server status
curl -I http://localhost:8080
```

### Message Issues
```bash
# Could not import rosidl_typesupport_c
# Solution: Rebuild message package first
colcon build --packages-select coffee_voice_agent_msgs
colcon build --packages-select coffee_voice_agent
source install/setup.bash
```

### Message Format Issues
```bash
# Voice agent only speaks partial announcements or order IDs
[WARNING] Invalid emotion 'Your coffee (Order', keeping current emotion
# Problem: Message content contains colons which conflict with emotion:text delimiter
# Solution: Avoid colons in virtual request content - use "(Order ABC)" not "(Order: ABC)"

# Voice agent speaks wrong emotion or text
# Problem: The voice agent uses emotion:text format for TTS processing
# Solution: Ensure content doesn't contain colons that would split incorrectly
```

### Build Issues
```bash
# empy version conflict
AttributeError: module 'em' has no attribute 'BUFFERED_OPT'  
# Solution: pip install empy==3.3.4
```

## Development

### Package Structure
- **🏗️ Refactored Voice Agent**: Modular structure in `scripts/` (main.py + subdirectories)
- **📚 Original Voice Agent**: Monolithic implementation in `scripts/livekit_voice_agent.py`
- **Bridge Node**: ROS2 integration in `coffee_voice_agent/`
- **Launch Files**: System orchestration in `launch/`
- **Custom Messages**: Unified messaging in `coffee_voice_agent_msgs/`

### Adding New Features

#### **🏗️ Refactored Version (Recommended for Development)**
1. **Function Tools**: Add to `tools/coffee_tools.py` and register in `agents/coffee_barista_agent.py`
2. **State Logic**: Modify `state/state_manager.py` for conversation flow changes
3. **Configuration**: Update `config/settings.py` or `config/instructions.py`
4. **Utilities**: Add to appropriate `utils/*.py` file
5. **Agent Behavior**: Modify `agents/coffee_barista_agent.py` for I/O changes
6. **ROS2 Integration**: Modify `voice_agent_bridge.py`
7. **Messages**: Add fields to `AgentStatus` or create new message types

#### **📚 Original Version**
1. **Voice functionality**: Modify `livekit_voice_agent.py` (search through 1109 lines)
2. **ROS2 integration**: Modify `voice_agent_bridge.py`
3. **System integration**: Update launch files

### Development Benefits - Refactored Version
- **🔍 Easy Navigation**: Find features in dedicated files vs searching monolith
- **🧪 Component Testing**: Test StateManager, tools, utilities independently
- **🔧 Clean Changes**: Modify specific files without side effects
- **📝 Code Reviews**: Smaller, focused diffs instead of large file changes
- **🏗️ Parallel Development**: Multiple developers can work on different components
- **📡 Unified Architecture**: Single message type for robot coordination

### Testing Components

#### **🏗️ Refactored Version**
```bash
# Test refactored voice agent directly
./scripts/run_main.sh

# Test individual components (Python REPL)
python3 -c "
from state.state_manager import StateManager
from tools.coffee_tools import get_current_time_impl
# Test components independently
"

# Test bridge connection
ros2 run coffee_voice_agent voice_agent_bridge

# Test complete system
ros2 launch coffee_voice_agent voice_agent_system.launch.py

# Monitor unified messages
ros2 topic echo /voice_agent/status
ros2 topic echo /voice_agent/tool_events
```

#### **📚 Original Version**
```bash
# Test original voice agent directly
./scripts/run_voice_agent_original.sh

# Test bridge connection
ros2 run coffee_voice_agent voice_agent_bridge

# Test complete system  
ros2 launch coffee_voice_agent voice_agent_system.launch.py
```

## Design Principles

- **Separation of Concerns**: Voice processing vs. system integration
- **Console Mode Priority**: Interactive functionality preserved
- **Clean Architecture**: WebSocket bridge avoids threading conflicts
- **Flexibility**: Can run components separately or together
- **ROS2 Native**: Bridge follows ROS2 patterns and conventions
- **Unified Messaging**: Single source of truth for robot coordination
- **Atomic Updates**: Consistent state through comprehensive messages
- **Tool Transparency**: Complete visibility into function tool execution

## Future Enhancements

- [ ] Add service interfaces for synchronous voice agent control
- [ ] Add parameter server integration for dynamic configuration
- [ ] Add diagnostics and health monitoring
- [ ] Add audio stream bridging for ROS2 audio topics
- [ ] Add behavior tree integration for complex interaction flows
- [ ] Extend ToolEvent message for error reporting and debugging
- [ ] Add conversation transcript reconstruction from AgentStatus history