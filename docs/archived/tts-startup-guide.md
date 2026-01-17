# Ensuring TTS Works at Startup

## Automatic Startup Announcement

When you start the agent service, TTS will automatically:
1. Initialize when the service starts
2. Announce: "Agent service started. TTS system active."

This happens in the FastAPI `startup` event handler.

## Verification Steps

### 1. Check TTS is Enabled

Ensure in `config/default.yaml`:
```yaml
tts:
  enabled: true
  engine: "system"  # or pyttsx3, gtts
```

### 2. Verify System TTS Works

Test your system TTS directly:
```bash
spd-say "Test message"
# or
espeak "Test message"
```

### 3. Start the Service

```bash
# Using the service script
poetry run agent-service

# Or directly
uvicorn src.personal_assistant.service:main --reload
```

You should hear: **"Agent service started. TTS system active."**

### 4. Check Logs

Look for these log messages:
```
tts_initialized_at_startup engine=system enabled=True
service_starting
tts_startup_announcement message="Agent service started. TTS system active."
```

## Troubleshooting

### No Startup Announcement

1. **Check TTS is enabled**: Verify `tts.enabled: true` in config
2. **Check system TTS**: Run `spd-say "test"` manually
3. **Check logs**: Look for TTS initialization errors
4. **Check audio**: Ensure your system audio is working

### TTS Not Initializing

If you see `TTS not available` in logs:
- Check that `src.personal_assistant.tts_helper` can be imported
- Verify config file is readable
- Check for Python import errors

### Startup Announcement Too Quiet/Fast

Adjust in config:
```yaml
tts:
  rate: 120  # Slower speech (default: 150)
  volume: 1.0  # Louder (default: 0.8)
```

## Manual Test

You can manually test TTS initialization:
```python
from src.personal_assistant.tts_helper import get_tts

tts = get_tts()
print(f"TTS enabled: {tts.enabled}")
print(f"TTS engine: {tts.engine}")
tts.speak("TTS test message")
```

## What Happens at Startup

1. Service loads config
2. `default_agent_from_env()` creates agent
3. `build_app()` registers TTS event listeners
4. FastAPI `startup` event fires
5. TTS announces: "Agent service started. TTS system active."
6. Service is ready to accept requests

The startup announcement confirms TTS is working and ready to announce agent actions.

