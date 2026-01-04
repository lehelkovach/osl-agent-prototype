"""
Speech-to-Text helper for voice commands and input.

Supports multiple backends:
- whisper (OpenAI Whisper, local)
- google (Google Speech-to-Text API)
- vosk (offline, lightweight)
- system (uses system STT if available)
"""

import os
import sys
import logging
import threading
import queue
from typing import Optional, Dict, Any, Callable
import subprocess

logger = logging.getLogger(__name__)


class STTHelper:
    """Speech-to-Text helper with multiple backend support."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize STT helper.
        
        Args:
            config: Configuration dict with keys:
                   - enabled: bool
                   - engine: "whisper", "google", "vosk", "system"
                   - model: model name/path (for whisper/vosk)
                   - language: language code (default: "en")
                   - continuous: bool (for continuous listening)
                   If None, loads from config files
        """
        if config is None:
            config = self._load_config()
        self.enabled = config.get("enabled", False)
        self.engine = config.get("engine", "system")
        self.model = config.get("model", None)
        self.language = config.get("language", "en")
        self.continuous = config.get("continuous", False)
        self.listening = False
        self._init_engine()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load STT configuration from config files."""
        import yaml
        from pathlib import Path
        
        default_config = {
            "enabled": False,
            "engine": "whisper",
            "model": "base",
            "language": "en",
            "continuous": False
        }
        
        repo_root = Path(__file__).parent.parent.parent
        tts_config_path = repo_root / "config" / "tts.yaml"
        default_config_path = repo_root / "config" / "default.yaml"
        
        for path in [tts_config_path, default_config_path]:
            if path.exists():
                try:
                    with open(path, 'r') as f:
                        user_config = yaml.safe_load(f)
                        if isinstance(user_config, dict) and "stt" in user_config:
                            default_config.update(user_config["stt"])
                            break
                except Exception as e:
                    logger.debug(f"Could not load STT config from {path}: {e}")
        
        return default_config
    
    def _init_engine(self):
        """Initialize the STT engine."""
        if not self.enabled:
            return
        
        if self.engine == "whisper":
            try:
                import whisper
                self._whisper_model = whisper.load_model(self.model or "base")
            except ImportError:
                logger.warning("whisper not installed, falling back to system STT")
                self.engine = "system"
            except Exception as e:
                logger.warning(f"Failed to initialize whisper: {e}, falling back to system STT")
                self.engine = "system"
        elif self.engine == "vosk":
            try:
                import vosk
                import json
                if not self.model:
                    logger.warning("Vosk model path required, falling back to system STT")
                    self.engine = "system"
                else:
                    self._vosk_model = vosk.Model(self.model)
                    self._vosk_rec = None
            except ImportError:
                logger.warning("vosk not installed, falling back to system STT")
                self.engine = "system"
            except Exception as e:
                logger.warning(f"Failed to initialize vosk: {e}, falling back to system STT")
                self.engine = "system"
        elif self.engine == "google":
            try:
                import speech_recognition as sr
                self._recognizer = sr.Recognizer()
            except ImportError:
                logger.warning("speech_recognition not installed, falling back to system STT")
                self.engine = "system"
            except Exception as e:
                logger.warning(f"Failed to initialize Google STT: {e}, falling back to system STT")
                self.engine = "system"
    
    def listen_once(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Listen for a single voice command.
        
        Args:
            timeout: Maximum time to wait for input (None = no timeout)
        
        Returns:
            Transcribed text or None if timeout/error
        """
        if not self.enabled:
            return None
        
        try:
            if self.engine == "whisper":
                return self._listen_whisper(timeout)
            elif self.engine == "vosk":
                return self._listen_vosk(timeout)
            elif self.engine == "google":
                return self._listen_google(timeout)
            else:
                return self._listen_system(timeout)
        except Exception as e:
            logger.error(f"STT error: {e}")
            return None
    
    def _listen_whisper(self, timeout: Optional[float]) -> Optional[str]:
        """Listen using Whisper."""
        try:
            import sounddevice as sd
            import numpy as np
            import tempfile
            import wave
            
            # Record audio
            sample_rate = 16000
            duration = timeout or 5.0
            
            logger.info("Listening...")
            audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='float32')
            sd.wait()
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
                with wave.open(tmp_path, 'wb') as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)
                    wf.setframerate(sample_rate)
                    wf.writeframes((audio * 32767).astype(np.int16).tobytes())
            
            # Transcribe
            result = self._whisper_model.transcribe(tmp_path, language=self.language)
            os.unlink(tmp_path)
            
            text = result.get("text", "").strip()
            return text if text else None
        except Exception as e:
            logger.error(f"Whisper STT error: {e}")
            return None
    
    def _listen_vosk(self, timeout: Optional[float]) -> Optional[str]:
        """Listen using Vosk."""
        try:
            import sounddevice as sd
            import json
            
            sample_rate = 16000
            duration = timeout or 5.0
            
            if self._vosk_rec is None:
                self._vosk_rec = vosk.KaldiRecognizer(self._vosk_model, sample_rate)
            
            logger.info("Listening...")
            audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16')
            sd.wait()
            
            # Process audio
            if self._vosk_rec.AcceptWaveform(audio.tobytes()):
                result = json.loads(self._vosk_rec.Result())
                text = result.get("text", "").strip()
                return text if text else None
            else:
                result = json.loads(self._vosk_rec.PartialResult())
                text = result.get("partial", "").strip()
                return text if text else None
        except Exception as e:
            logger.error(f"Vosk STT error: {e}")
            return None
    
    def _listen_google(self, timeout: Optional[float]) -> Optional[str]:
        """Listen using Google Speech Recognition."""
        try:
            import speech_recognition as sr
            
            with sr.Microphone() as source:
                self._recognizer.adjust_for_ambient_noise(source)
                logger.info("Listening...")
                audio = self._recognizer.listen(source, timeout=timeout)
            
            text = self._recognizer.recognize_google(audio, language=self.language)
            return text.strip() if text else None
        except sr.WaitTimeoutError:
            return None
        except Exception as e:
            logger.error(f"Google STT error: {e}")
            return None
    
    def _listen_system(self, timeout: Optional[float]) -> Optional[str]:
        """Listen using system STT (if available)."""
        # Try different system STT tools
        if sys.platform.startswith('linux'):
            # Try speech-dispatcher or other tools
            # For now, return None (system STT on Linux is complex)
            logger.warning("System STT not fully implemented for Linux")
            return None
        elif sys.platform == 'darwin':
            # macOS has built-in dictation, but it's not easily accessible via CLI
            logger.warning("System STT not fully implemented for macOS")
            return None
        elif sys.platform == 'win32':
            # Windows Speech Recognition
            logger.warning("System STT not fully implemented for Windows")
            return None
        
        return None
    
    def start_continuous_listening(self, callback: Callable[[str], None]):
        """
        Start continuous listening in background thread.
        
        Args:
            callback: Function to call with transcribed text
        """
        if not self.enabled or self.listening:
            return
        
        self.listening = True
        
        def listen_loop():
            while self.listening:
                text = self.listen_once(timeout=5.0)
                if text:
                    callback(text)
        
        thread = threading.Thread(target=listen_loop, daemon=True)
        thread.start()
    
    def stop_continuous_listening(self):
        """Stop continuous listening."""
        self.listening = False


# Global instance
_stt_instance: Optional[STTHelper] = None


def get_stt(config: Optional[Dict[str, Any]] = None) -> STTHelper:
    """Get or create the global STT instance."""
    global _stt_instance
    if _stt_instance is None:
        _stt_instance = STTHelper(config)
    return _stt_instance


def listen_once(timeout: Optional[float] = None) -> Optional[str]:
    """Convenience function to listen once."""
    stt = get_stt()
    if not stt.enabled:
        return None
    return stt.listen_once(timeout)

