"""
Voice command handler that integrates STT with the agent for voice interactions.

Supports:
- "why" command to pause and explain current action
- "continue" command to resume after pause
- "stop" command to stop execution
- Continuous listening mode for hands-free operation
"""

import logging
import threading
from typing import Optional, Dict, Any, Callable
from src.personal_assistant.stt_helper import get_stt, STTHelper
from src.personal_assistant.tts_helper import get_tts

logger = logging.getLogger(__name__)


class VoiceCommandHandler:
    """Handles voice commands and integrates with agent execution."""
    
    def __init__(self, stt: Optional[STTHelper] = None, tts=None):
        """
        Initialize voice command handler.
        
        Args:
            stt: STTHelper instance (if None, uses global instance)
            tts: TTSHelper instance (if None, uses global instance)
        """
        self.stt = stt or get_stt()
        self.tts = tts or get_tts()
        self.listening = False
        self.paused = False
        self.current_explanation = None
        self.command_callbacks: Dict[str, Callable[[], None]] = {}
        
        # Register default commands
        self.register_command("why", self._handle_why)
        self.register_command("continue", self._handle_continue)
        self.register_command("resume", self._handle_continue)
        self.register_command("stop", self._handle_stop)
        self.register_command("pause", self._handle_pause)
    
    def register_command(self, command: str, callback: Callable[[], None]):
        """Register a voice command handler."""
        self.command_callbacks[command.lower()] = callback
    
    def _handle_why(self):
        """Handle 'why' command - pause and explain current action."""
        if not self.paused:
            self.paused = True
            self.tts.pause_for_question()
            self.tts.speak("Paused. What would you like to know?", summarize=False, priority=True)
    
    def _handle_continue(self):
        """Handle 'continue' command - resume execution."""
        if self.paused:
            self.paused = False
            self.tts.resume_after_question()
            self.tts.speak("Resuming", summarize=False, priority=True)
    
    def _handle_stop(self):
        """Handle 'stop' command - stop execution."""
        self.paused = True
        self.tts.pause_for_question()
        self.tts.speak("Stopped. Waiting for instructions.", summarize=False, priority=True)
    
    def _handle_pause(self):
        """Handle 'pause' command - pause execution."""
        self._handle_why()
    
    def explain_action(self, explanation: str):
        """Provide explanation for current action (when paused for 'why')."""
        if self.paused:
            self.tts.explain_current_action(explanation)
    
    def process_command(self, text: str) -> bool:
        """
        Process a voice command.
        
        Args:
            text: Transcribed text
        
        Returns:
            True if command was recognized and handled
        """
        if not text:
            return False
        
        text_lower = text.lower().strip()
        
        # Check for registered commands
        for command, callback in self.command_callbacks.items():
            if command in text_lower:
                try:
                    callback()
                    return True
                except Exception as e:
                    logger.error(f"Error executing command '{command}': {e}")
        
        return False
    
    def start_continuous_listening(self):
        """Start continuous listening for voice commands."""
        if not self.stt.enabled:
            logger.warning("STT not enabled, cannot start continuous listening")
            return
        
        if self.listening:
            return
        
        self.listening = True
        
        def listen_loop():
            while self.listening:
                try:
                    text = self.stt.listen_once(timeout=5.0)
                    if text:
                        logger.info(f"Voice command received: {text}")
                        handled = self.process_command(text)
                        if not handled:
                            # Not a recognized command, could be passed to agent
                            logger.debug(f"Unrecognized voice input: {text}")
                except Exception as e:
                    logger.error(f"Error in voice listening loop: {e}")
        
        thread = threading.Thread(target=listen_loop, daemon=True)
        thread.start()
        logger.info("Continuous voice listening started")
    
    def stop_continuous_listening(self):
        """Stop continuous listening."""
        self.listening = False
        if self.stt:
            self.stt.stop_continuous_listening()
        logger.info("Continuous voice listening stopped")


# Global instance
_voice_handler_instance: Optional[VoiceCommandHandler] = None


def get_voice_handler(stt_config: Optional[Dict[str, Any]] = None) -> VoiceCommandHandler:
    """Get or create the global voice command handler."""
    global _voice_handler_instance
    if _voice_handler_instance is None:
        stt = get_stt(stt_config) if stt_config else get_stt()
        _voice_handler_instance = VoiceCommandHandler(stt=stt)
    return _voice_handler_instance

