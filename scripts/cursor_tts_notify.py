#!/usr/bin/env python3
"""
Cursor TTS Notification Script

This script can be used to send TTS notifications from Cursor IDE or command line.

Usage:
    # Speak a custom message
    python scripts/cursor_tts_notify.py "Your message here"
    
    # Announce completion
    python scripts/cursor_tts_notify.py --completion
    
    # Announce prompt ready
    python scripts/cursor_tts_notify.py --prompt
    
    # Custom completion message
    python scripts/cursor_tts_notify.py --completion "Build finished successfully"
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.personal_assistant.tts_helper import get_tts, speak, announce_completion, announce_prompt


def main():
    parser = argparse.ArgumentParser(
        description="Send TTS notifications for Cursor IDE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Hello, this is a test"
  %(prog)s --completion
  %(prog)s --prompt
  %(prog)s --completion "Build finished successfully"
        """
    )
    
    parser.add_argument(
        "message",
        nargs="?",
        help="Custom message to speak"
    )
    
    parser.add_argument(
        "--completion",
        action="store_true",
        help="Announce task completion"
    )
    
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Announce that a prompt is ready"
    )
    
    parser.add_argument(
        "--async",
        action="store_true",
        dest="async_mode",
        help="Speak asynchronously (non-blocking)"
    )
    
    args = parser.parse_args()
    
    tts = get_tts()
    
    if not tts.enabled:
        print("TTS is disabled in configuration.")
        sys.exit(0)
    
    if args.completion:
        if args.message:
            announce_completion(args.message)
        else:
            announce_completion()
    elif args.prompt:
        if args.message:
            announce_prompt(args.message)
        else:
            announce_prompt()
    elif args.message:
        speak(args.message, async_mode=args.async_mode)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()

