"""
Enhanced Text-to-Speech helper with queuing, summarization, pause/resume, and STT integration.

Features:
- Queued speech announcements (non-blocking)
- Automatic summarization to keep announcements concise
- Pause/resume functionality for "why" queries
- STT integration for voice commands
- Audio notifications for input needed
"""

import os
import sys
import json
import logging
import threading
import queue
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
import subprocess

logger = logging.getLogger(__name__)


class SpeechQueue:
    """Thread-safe queue for managing speech announcements."""
    
    def __init__(self, speak_fn: Callable[[str], None], max_queue_size: int = 10):
        self.speak_fn = speak_fn
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.paused = False
        self.current_speaking = False
        self.worker_thread = None
        self.stop_event = threading.Event()
        self._start_worker()
    
    def _start_worker(self):
        """Start the background worker thread."""
        if self.worker_thread is None or not self.worker_thread.is_alive():
            self.worker_thread = threading.Thread(target=self._worker, daemon=True)
            self.worker_thread.start()
    
    def _worker(self):
        """Background worker that processes speech queue."""
        while not self.stop_event.is_set():
            try:
                # Wait for item with timeout to allow checking stop_event
                try:
                    text = self.queue.get(timeout=0.5)
                except queue.Empty:
                    continue
                
                # Wait if paused
                while self.paused and not self.stop_event.is_set():
                    time.sleep(0.1)
                
                if not self.stop_event.is_set():
                    self.current_speaking = True
                    self.speak_fn(text)
                    self.current_speaking = False
                    self.queue.task_done()
            except Exception as e:
                logger.error(f"Speech queue worker error: {e}")
                self.current_speaking = False
    
    def enqueue(self, text: str, priority: bool = False):
        """Enqueue text to be spoken."""
        if priority:
            # For priority items, try to add to front (simple approach: clear and re-add)
            # In practice, we'll just add it and let it process
            pass
        try:
            self.queue.put_nowait(text)
        except queue.Full:
            logger.warning("Speech queue full, dropping message")
    
    def pause(self):
        """Pause speech output."""
        self.paused = True
    
    def resume(self):
        """Resume speech output."""
        self.paused = False
    
    def clear(self):
        """Clear the queue."""
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
    
    def stop(self):
        """Stop the worker thread."""
        self.stop_event.set()
        if self.worker_thread:
            self.worker_thread.join(timeout=1.0)


class TTSHelper:
    """Enhanced Text-to-Speech helper with queuing and summarization."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize TTS helper with configuration.
        
        Args:
            config_path: Path to TTS config file. If None, looks for:
                        - config/tts.yaml
                        - config/default.yaml (tts section)
        """
        self.config = self._load_config(config_path)
        self.enabled = self.config.get("enabled", True)
        self.engine = self.config.get("engine", "system")  # system, pyttsx3, gtts
        self.voice = self.config.get("voice", None)
        self.rate = self.config.get("rate", 150)  # words per minute
        self.volume = self.config.get("volume", 0.8)  # 0.0 to 1.0
        self.announce_completions = self.config.get("announce_completions", True)
        self.announce_prompts = self.config.get("announce_prompts", True)
        self.completion_phrase = self.config.get("completion_phrase", "Task completed")
        self.prompt_phrase = self.config.get("prompt_phrase", "Ready for your input")
        self.summarize = self.config.get("summarize", True)
        self.max_announcement_length = self.config.get("max_announcement_length", 20)  # words
        self.input_chime_enabled = self.config.get("input_chime_enabled", True)
        self.input_chime_path = self.config.get("input_chime_path", None)
        
        # Initialize TTS engine
        self._init_engine()
        
        # Create speech queue
        self.speech_queue = SpeechQueue(self._speak_sync, max_queue_size=self.config.get("max_queue_size", 10))
        
        # State for pause/resume
        self._paused_for_question = False
        self._pending_explanation = None
    
    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load TTS configuration from file."""
        default_config = {
            "enabled": True,
            "engine": "system",
            "voice": None,
            "rate": 150,
            "volume": 0.8,
            "announce_completions": True,
            "announce_prompts": True,
            "completion_phrase": "Task completed",
            "prompt_phrase": "Ready for your input",
            "summarize": True,
            "max_announcement_length": 20,
            "max_queue_size": 10,
            "input_chime_enabled": True,
            "input_chime_path": None
        }
        
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    if config_path.endswith('.json'):
                        user_config = json.load(f)
                    else:
                        import yaml
                        user_config = yaml.safe_load(f)
                    if isinstance(user_config, dict) and "tts" in user_config:
                        user_config = user_config["tts"]
                    default_config.update(user_config)
            except Exception as e:
                logger.warning(f"Failed to load TTS config from {config_path}: {e}")
        
        # Try default locations
        if not config_path:
            repo_root = Path(__file__).parent.parent.parent
            tts_config_path = repo_root / "config" / "tts.yaml"
            default_config_path = repo_root / "config" / "default.yaml"
            
            for path in [tts_config_path, default_config_path]:
                if path.exists():
                    try:
                        import yaml
                        with open(path, 'r') as f:
                            user_config = yaml.safe_load(f)
                            if isinstance(user_config, dict):
                                if "tts" in user_config:
                                    user_config = user_config["tts"]
                                default_config.update(user_config)
                            break
                    except Exception as e:
                        logger.debug(f"Could not load config from {path}: {e}")
        
        return default_config
    
    def _init_engine(self):
        """Initialize the TTS engine based on configuration."""
        if not self.enabled:
            return
        
        if self.engine == "pyttsx3":
            try:
                import pyttsx3
                self._engine = pyttsx3.init()
                if self.voice:
                    voices = self._engine.getProperty('voices')
                    for v in voices:
                        if self.voice.lower() in v.name.lower() or self.voice.lower() in v.id.lower():
                            self._engine.setProperty('voice', v.id)
                            break
                self._engine.setProperty('rate', self.rate)
                self._engine.setProperty('volume', self.volume)
            except ImportError:
                logger.warning("pyttsx3 not installed, falling back to system TTS")
                self.engine = "system"
                self._engine = None
            except Exception as e:
                logger.warning(f"Failed to initialize pyttsx3: {e}, falling back to system TTS")
                self.engine = "system"
                self._engine = None
        elif self.engine == "gtts":
            try:
                from gtts import gTTS
                import tempfile
                import playsound
                self._gtts = gTTS
                self._playsound = playsound
                self._tempfile = tempfile
            except ImportError:
                logger.warning("gTTS/playsound not installed, falling back to system TTS")
                self.engine = "system"
            except Exception as e:
                logger.warning(f"Failed to initialize gTTS: {e}, falling back to system TTS")
                self.engine = "system"
        else:
            # system TTS (espeak, festival, say, etc.)
            self._engine = None
    
    def _summarize_text(self, text: str, max_words: int = None) -> str:
        """Summarize text to keep announcements concise."""
        if not self.summarize:
            return text
        
        max_words = max_words or self.max_announcement_length
        words = text.split()
        
        if len(words) <= max_words:
            return text
        
        # Simple summarization: take first few words + key action words
        # Look for action verbs and important nouns
        action_words = ["completed", "finished", "executing", "running", "creating", "updating", "searching", "found"]
        important_words = []
        for word in words:
            if any(action in word.lower() for action in action_words):
                important_words.append(word)
        
        # Take first few words + important words
        summary = words[:max_words//2]
        if important_words:
            summary.extend(important_words[:max_words//2])
        
        # Ensure we don't exceed max_words
        summary = summary[:max_words]
        return " ".join(summary)
    
    def _speak_sync(self, text: str, prefer_spd_say: bool = False):
        """Synchronous speech (called by queue worker).
        
        Args:
            text: Text to speak
            prefer_spd_say: If True, prefer spd-say (for completion announcements)
        """
        if not self.enabled or not text:
            return
        
        try:
            if self.engine == "pyttsx3" and self._engine:
                self._engine.say(text)
                self._engine.runAndWait()
            elif self.engine == "gtts":
                self._speak_gtts(text, async_mode=False)
            else:
                # System TTS
                self._speak_system(text, async_mode=False, prefer_spd_say=prefer_spd_say)
        except Exception as e:
            logger.error(f"TTS error: {e}")
    
    def speak(self, text: str, summarize: Optional[bool] = None, priority: bool = False, prefer_spd_say: bool = False):
        """
        Queue text to be spoken (non-blocking).
        
        Args:
            text: Text to speak
            summarize: Whether to summarize (overrides config)
            priority: If True, try to prioritize this message
            prefer_spd_say: If True, prefer spd-say for this announcement (for completions)
        """
        if not self.enabled or not text:
            return
        
        should_summarize = summarize if summarize is not None else self.summarize
        if should_summarize:
            text = self._summarize_text(text)
        
        # Store prefer_spd_say flag with text for queue worker
        # We'll pass it through by modifying the queue to handle tuples
        if prefer_spd_say:
            # For now, we'll use a wrapper function that calls _speak_sync with prefer_spd_say
            def speak_with_spd(text_to_speak):
                self._speak_sync(text_to_speak, prefer_spd_say=True)
            self.speech_queue.enqueue((text, speak_with_spd), priority=priority)
        else:
            self.speech_queue.enqueue(text, priority=priority)
    
    def _speak_gtts(self, text: str, async_mode: bool):
        """Speak using Google TTS (requires internet)."""
        try:
            tts = self._gtts.gTTS(text=text, lang='en')
            with self._tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp:
                tmp_path = tmp.name
                tts.save(tmp_path)
            
            if async_mode:
                import threading
                def play_and_cleanup():
                    self._playsound.playsound(tmp_path)
                    os.unlink(tmp_path)
                thread = threading.Thread(target=play_and_cleanup)
                thread.daemon = True
                thread.start()
            else:
                self._playsound.playsound(tmp_path)
                os.unlink(tmp_path)
        except Exception as e:
            logger.error(f"gTTS error: {e}")
    
    def _speak_system(self, text: str, async_mode: bool, prefer_spd_say: bool = False):
        """Speak using system TTS (espeak, festival, spd-say, say).
        
        Args:
            text: Text to speak
            async_mode: Whether to speak asynchronously
            prefer_spd_say: If True, only use spd-say (for completion announcements)
        """
        commands = []
        
        if sys.platform.startswith('linux'):
            if prefer_spd_say:
                # Force spd-say for completion announcements
                if self._command_exists('spd-say'):
                    commands.append(['spd-say', text])
                else:
                    logger.warning("spd-say requested but not found. Install 'spd-say' for completion announcements.")
            else:
                # Normal priority: spd-say first, then fallbacks
                if self._command_exists('spd-say'):
                    commands.append(['spd-say', text])
                elif self._command_exists('espeak'):
                    rate_arg = str(int(self.rate * 0.6))
                    commands.append(['espeak', '-s', rate_arg, text])
                elif self._command_exists('festival'):
                    commands.append(['festival', '--tts', '--pipe'])
        elif sys.platform == 'darwin':
            rate_arg = str(int(self.rate / 10))
            commands.append(['say', '-r', rate_arg, text])
        elif sys.platform == 'win32':
            escaped_text = text.replace("'", "''")
            commands.append([
                'powershell', '-Command',
                f"Add-Type -AssemblyName System.Speech; $speak = New-Object System.Speech.Synthesis.SpeechSynthesizer; $speak.Rate = {self.rate - 150}; $speak.Speak('{escaped_text}')"
            ])
        
        for cmd in commands:
            try:
                if async_mode:
                    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                return
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        
        logger.warning("No system TTS command found. Install 'spd-say', 'espeak', or 'festival' on Linux.")
    
    def _command_exists(self, command: str) -> bool:
        """Check if a command exists in PATH."""
        try:
            subprocess.run(['which', command], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _play_chime(self):
        """Play a chime sound for input notifications."""
        if not self.input_chime_enabled:
            return
        
        # Try custom chime path first
        if self.input_chime_path and os.path.exists(self.input_chime_path):
            try:
                if sys.platform.startswith('linux'):
                    subprocess.Popen(['paplay', self.input_chime_path], 
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['afplay', self.input_chime_path],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif sys.platform == 'win32':
                    import winsound
                    winsound.PlaySound(self.input_chime_path, winsound.SND_FILENAME)
            except Exception as e:
                logger.debug(f"Could not play custom chime: {e}")
        else:
            # Generate a simple beep using system tools
            try:
                if sys.platform.startswith('linux'):
                    # Use beep or speaker-test
                    if self._command_exists('beep'):
                        subprocess.Popen(['beep', '-f', '800', '-l', '200'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    elif self._command_exists('speaker-test'):
                        # Generate a short tone
                        subprocess.Popen(['speaker-test', '-t', 'sine', '-f', '800', '-l', '1'],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif sys.platform == 'darwin':
                    subprocess.Popen(['say', '-v', 'Bells', 'ding'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                elif sys.platform == 'win32':
                    import winsound
                    winsound.Beep(800, 200)
            except Exception as e:
                logger.debug(f"Could not play system chime: {e}")
    
    def announce_step(self, step_description: str, tool_name: Optional[str] = None):
        """
        Announce a step completion with automatic summarization.
        
        Args:
            step_description: Description of what was completed
            tool_name: Optional tool name for context
        """
        if not self.announce_completions:
            return
        
        # Create concise announcement
        if tool_name:
            announcement = f"{tool_name}: {step_description}"
        else:
            announcement = step_description
        
        self.speak(announcement, summarize=True)
    
    def announce_completion(self, message: Optional[str] = None):
        """Announce task completion using spd-say."""
        if self.announce_completions:
            text = message or self.completion_phrase
            # Use spd-say specifically for completion announcements
            self.speak(text, summarize=False, priority=True, prefer_spd_say=True)
    
    def announce_input_needed(self, message: Optional[str] = None, play_chime: bool = True):
        """
        Announce that input is needed (with optional chime).
        
        Args:
            message: Custom message (default: prompt_phrase)
            play_chime: Whether to play chime sound
        """
        if play_chime:
            self._play_chime()
        
        if self.announce_prompts:
            text = message or self.prompt_phrase
            self.speak(text, summarize=False, priority=True)
    
    def pause_for_question(self):
        """Pause speech output for user question."""
        self.speech_queue.pause()
        self._paused_for_question = True
    
    def resume_after_question(self):
        """Resume speech output after question answered."""
        self.speech_queue.resume()
        self._paused_for_question = False
    
    def explain_current_action(self, explanation: str):
        """Provide explanation for current action (when paused)."""
        if self._paused_for_question:
            self.speak(explanation, summarize=False, priority=True)
    
    def stop(self):
        """Stop TTS system and cleanup."""
        self.speech_queue.stop()


# Global instance (lazy initialization)
_tts_instance: Optional[TTSHelper] = None


def get_tts() -> TTSHelper:
    """Get or create the global TTS instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = TTSHelper()
    return _tts_instance


def speak(text: str, summarize: Optional[bool] = None, priority: bool = False):
    """Convenience function to speak text."""
    get_tts().speak(text, summarize, priority)


def announce_step(step_description: str, tool_name: Optional[str] = None):
    """Convenience function to announce step."""
    get_tts().announce_step(step_description, tool_name)


def announce_completion(message: Optional[str] = None):
    """Convenience function to announce completion."""
    get_tts().announce_completion(message)


def announce_input_needed(message: Optional[str] = None, play_chime: bool = True):
    """Convenience function to announce input needed."""
    get_tts().announce_input_needed(message, play_chime)
