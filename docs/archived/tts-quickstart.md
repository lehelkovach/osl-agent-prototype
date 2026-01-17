# TTS/STT Quick Start

## What Was Added

A complete Text-to-Speech (TTS) and Speech-to-Text (STT) system that:

1. **Announces each step** as the agent completes it (non-blocking, queued)
2. **Summarizes announcements** to keep them concise
3. **Plays chime + message** when input is needed
4. **Supports voice commands** ("why", "continue", "stop", "pause")
5. **Pause/resume** functionality for asking questions mid-execution

## Quick Setup (Linux)

### 1. Install System TTS (easiest, works offline)

```bash
sudo apt-get install speech-dispatcher
# Test it: spd-say "Hello"
```

### 2. Enable TTS in Config

Edit `config/default.yaml`:

```yaml
tts:
  enabled: true
  engine: "system"  # Uses speech-dispatcher
  announce_completions: true
  announce_prompts: true
  summarize: true
  input_chime_enabled: true
```

### 3. Run the Agent

```bash
python main.py
# or
poetry run agent-service
```

The agent will now announce:
- "Plan ready with N steps"
- "Starting [action]"
- "Completed [result]"
- "All steps completed"
- Chime + "Ready for your input" when approval needed

## Enable Voice Commands (Optional)

### 1. Install Whisper STT

```bash
pip install openai-whisper sounddevice numpy
```

### 2. Enable STT in Config

```yaml
stt:
  enabled: true
  engine: "whisper"
  model: "base"  # First run downloads automatically
```

### 3. Use Voice Commands

- Say **"why"** to pause and get explanation
- Say **"continue"** to resume
- Say **"stop"** to stop execution

## Test It

```python
from src.personal_assistant.tts_helper import get_tts

tts = get_tts()
tts.speak("Testing TTS system")
tts.announce_step("Creating task", tool_name="tasks.create")
tts.announce_input_needed("Need approval", play_chime=True)
```

## Configuration Options

See `config/tts.yaml` or `docs/tts-stt-integration.md` for full options.

## Troubleshooting

- **No sound**: Check `spd-say "test"` works
- **Too verbose**: Set `announce_tool_starts: false` or reduce `max_announcement_length`
- **STT not working**: Check microphone with `arecord -d 5 test.wav`

## Files Created

- `src/personal_assistant/tts_helper.py` - TTS with queuing and summarization
- `src/personal_assistant/stt_helper.py` - STT with multiple backends
- `src/personal_assistant/tts_event_listener.py` - Event bus integration
- `src/personal_assistant/voice_command_handler.py` - Voice command processing
- `config/tts.yaml` - TTS/STT configuration
- `docs/tts-stt-integration.md` - Full documentation

