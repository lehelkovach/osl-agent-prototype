#!/usr/bin/env python3
"""
Quick script to speak a brief synopsis using the TTS system.

Usage:
    python scripts/speak_synopsis.py "Your message here"
    python scripts/speak_synopsis.py --synopsis  # Speaks a brief summary of what was accomplished
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.personal_assistant.tts_helper import get_tts


def speak_synopsis():
    """Speak a brief synopsis of what was accomplished."""
    synopsis = """
    TTS and STT system has been integrated. 
    The agent now announces each step as it completes, with automatic summarization to keep announcements concise.
    When input is needed, a chime plays followed by a message.
    Voice commands are available: say 'why' to pause, 'continue' to resume, or 'stop' to halt execution.
    All announcements are queued and non-blocking, so they don't slow down agent execution.
    """
    
    tts = get_tts()
    if not tts.enabled:
        print("TTS is disabled. Enable it in config/default.yaml or config/tts.yaml")
        return
    
    print("Speaking synopsis...")
    tts.speak(synopsis.strip(), summarize=False)


def main():
    parser = argparse.ArgumentParser(description="Speak text or synopsis using TTS")
    parser.add_argument("message", nargs="?", help="Message to speak")
    parser.add_argument("--synopsis", action="store_true", help="Speak brief synopsis of accomplishments")
    parser.add_argument("--summarize", action="store_true", help="Enable summarization")
    
    args = parser.parse_args()
    
    tts = get_tts()
    
    if not tts.enabled:
        print("TTS is disabled. Enable it in config/default.yaml:")
        print("  tts:")
        print("    enabled: true")
        print("    engine: \"system\"")
        sys.exit(1)
    
    if args.synopsis:
        speak_synopsis()
    elif args.message:
        tts.speak(args.message, summarize=args.summarize)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

