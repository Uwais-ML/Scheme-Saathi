"""Main entry point for Scheme Saathi / Welfare Scheme Agent."""

import argparse
import sys
from agent.loop import run_agent_turn
from voice.stt import SpeechToText
from voice.tts import TextToSpeech

WELCOME_GREETING = "नमस्ते! मैं आपका योजना साथी हूँ। आज हम किस सरकारी योजना की जानकारी लें या आपकी क्या सहायता करूँ?"


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Welfare Scheme Agent (Scheme Saathi)")
    parser.add_argument(
        "--text",
        action="store_true",
        help="Run in text-only mode (bypasses microphone audio recording)",
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default="user_default",
        help="Unique identifier for the user session",
    )
    return parser.parse_args()


def main():
    """Run interactive agent session."""
    args = parse_args()
    user_id = args.user_id
    text_only = args.text

    stt = SpeechToText()
    tts = TextToSpeech()

    tts.speak(WELCOME_GREETING, play_audio=not text_only)

    print("\n--- Scheme Saathi प्रारंभ हो चुका है (प्रस्थान के लिए 'exit' या 'quit' टाइप करें) ---")

    while True:
        try:
            if text_only:
                user_input = input("\n[आप]: ").strip()
            else:
                print("\n[बोलें या लिखें]: ", end="")
                user_input = input().strip()

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                farewell = "धन्यवाद! फिर मिलेंगे।"
                tts.speak(farewell, play_audio=not text_only)
                break

            # Run agent turn
            def on_speech(msg: str):
                tts.speak(msg, play_audio=not text_only)

            run_agent_turn(
                user_input=user_input,
                user_id=user_id,
                on_speech=on_speech,
            )

        except (KeyboardInterrupt, EOFError):
            print("\nसत्र समाप्त हुआ।")
            break
        except Exception as exc:
            print(f"\n[त्रुटि]: {exc}")


if __name__ == "__main__":
    main()
