# TTS/STT Integration Guide

This guide explains how to use the Text-to-Speech (TTS) and Speech-to-Text (STT) features with the agent.

## Features

### Text-to-Speech (TTS)
- **Queued announcements**: Non-blocking speech output with automatic queuing
- **Automatic summarization**: Keeps announcements concise (configurable max length)
- **Step-by-step announcements**: Announces each tool execution as it completes
- **Pause/resume**: Can pause for questions ("why") and resume
- **Input notifications**: Plays chime + message when input is needed
- **Multiple engines**: Supports system TTS (espeak/spd-say), pyttsx3, or Google TTS

### Speech-to-Text (STT)
- **Voice commands**: "why", "continue", "resume", "stop", "pause"
- **Continuous listening**: Optional background listening mode
- **Multiple engines**: Whisper (local), Google STT, Vosk (offline), or system STT

## Configuration

### Basic Setup

Edit `config/default.yaml` or `config/tts.yaml`:

```yaml
tts:
  enabled: true
  engine: "system"  # system, pyttsx3, or gtts
  rate: 150  # words per minute
  volume: 0.8
  announce_completions: true
  announce_prompts: true
  summarize: true  # Auto-summarize to keep announcements concise
  max_announcement_length: 20  # words
  input_chime_enabled: true

stt:
  enabled: false  # Set to true to enable voice commands
  engine: "whisper"  # whisper, google, vosk, or system
  model: "base"  # For whisper: tiny/base/small/medium/large
  language: "en"
  continuous: false
```

### System TTS Setup (Linux)

The default "system" engine uses Linux TTS tools. Install one of:

```bash
# Option 1: Speech Dispatcher (recommended)
sudo apt-get install speech-dispatcher
# Test: spd-say "Hello"

# Option 2: espeak
sudo apt-get install espeak
# Test: espeak "Hello"

# Option 3: Festival
sudo apt-get install festival
# Test: echo "Hello" | festival --tts
```

### Advanced TTS Engines

#### pyttsx3 (Cross-platform)
```bash
pip install pyttsx3
```

Then set `engine: "pyttsx3"` in config.

#### Google TTS (requires internet)
```bash
pip install gtts playsound
```

Then set `engine: "gtts"` in config.

### STT Setup

#### Whisper (Recommended, local, offline)
```bash
pip install openai-whisper sounddevice numpy
```

Then set:
```yaml
stt:
  enabled: true
  engine: "whisper"
  model: "base"  # or tiny/small/medium/large
```

#### Google STT (requires internet)
```bash
pip install SpeechRecognition
```

Then set:
```yaml
stt:
  enabled: true
  engine: "google"
```

#### Vosk (Offline, lightweight)
```bash
pip install vosk sounddevice
# Download a model from https://alphacephei.com/vosk/models
# Extract to a directory, e.g., ~/vosk-models/en-us
```

Then set:
```yaml
stt:
  enabled: true
  engine: "vosk"
  model: "/path/to/vosk-models/en-us"
```

## Usage

### Automatic Announcements

When TTS is enabled, the agent automatically announces:
- **Plan ready**: "Plan ready with N steps"
- **Tool start**: "Starting [tool action]"
- **Tool complete**: "Completed [tool result]"
- **Execution complete**: "All steps completed"
- **Input needed**: Chime + "Ready for your input"

### Voice Commands

When STT is enabled, you can use voice commands:

- **"why"** or **"pause"**: Pause execution and ask for explanation
- **"continue"** or **"resume"**: Resume execution after pause
- **"stop"**: Stop execution and wait for instructions

### Programmatic Usage

```python
from src.personal_assistant.tts_helper import get_tts, announce_step, announce_input_needed
from src.personal_assistant.stt_helper import get_stt, listen_once
from src.personal_assistant.voice_command_handler import get_voice_handler

# TTS
tts = get_tts()
tts.speak("Hello, this is a test")
tts.announce_step("Creating task", tool_name="tasks.create")
tts.announce_input_needed("Need approval to run shell command", play_chime=True)

# STT
stt = get_stt()
text = stt.listen_once(timeout=5.0)  # Listen for 5 seconds
if text:
    print(f"Heard: {text}")

# Voice commands
handler = get_voice_handler()
handler.start_continuous_listening()  # Start background listening
# Commands are automatically processed
```

### Integration with Agent Events

The TTS system automatically listens to agent events:
- `tool_start`: Announces tool start
- `tool_invoked`: Announces tool completion
- `execution_completed`: Announces overall completion
- `plan_ready`: Announces plan summary
- `input_needed`: Plays chime + message

To emit `input_needed` events from your code:

```python
agent.event_bus.emit("input_needed", {
    "message": "Need approval to run shell command",
    "play_chime": True
})
```

## Customization

### Custom Chime Sound

Set a custom chime file in config:

```yaml
tts:
  input_chime_path: "/path/to/your/chime.wav"
```

### Custom Voice Commands

```python
from src.personal_assistant.voice_command_handler import get_voice_handler

handler = get_voice_handler()

def handle_custom_command():
    print("Custom command executed!")

handler.register_command("custom", handle_custom_command)
```

### Adjusting Announcement Verbosity

```yaml
tts:
  summarize: true  # Enable summarization
  max_announcement_length: 15  # Shorter announcements (words)
  announce_tool_starts: false  # Don't announce tool starts, only completions
```

## Troubleshooting

### TTS Not Working

1. Check that TTS is enabled: `tts.enabled: true`
2. Test system TTS: `spd-say "test"` or `espeak "test"`
3. Check logs for TTS errors

### STT Not Working

1. Check that STT is enabled: `stt.enabled: true`
2. Test microphone: `arecord -d 5 test.wav` (Linux)
3. For Whisper: Ensure model is downloaded (first run downloads automatically)
4. Check logs for STT errors

### Speech Queue Full

If you see "Speech queue full" warnings:
- Increase `max_queue_size` in config
- Reduce announcement frequency
- Disable `announce_tool_starts` if too verbose

## Examples

### Example: Announce Shell Command Execution

```python
from src.personal_assistant.tts_helper import get_tts

tts = get_tts()
tts.announce_step("Running backup script", tool_name="shell.run")
# ... execute command ...
tts.announce_step("Backup completed successfully")
```

### Example: Request Approval with Voice

```python
from src.personal_assistant.tts_helper import get_tts
from src.personal_assistant.stt_helper import get_stt

tts = get_tts()
stt = get_stt()

tts.announce_input_needed("Need approval to delete files. Say 'continue' to proceed or 'stop' to cancel.")
response = stt.listen_once(timeout=10.0)
if response and "continue" in response.lower():
    # Proceed with deletion
    pass
else:
    # Cancel
    tts.speak("Cancelled")
```

## Notes

- TTS announcements are non-blocking and queued automatically
- Speech is automatically summarized to keep announcements concise
- Voice commands work best in quiet environments
- Whisper STT requires initial model download (automatic on first use)
- System TTS (Linux) works offline and requires no extra dependencies

