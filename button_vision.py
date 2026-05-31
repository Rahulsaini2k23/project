#!/usr/bin/env python3
"""
button_vision.py — Press button → capture image → Gemini analysis → TTS playback
Hardware : Raspberry Pi 4B  |  push button on GPIO  |  camera  |  USB speaker/mic
"""

import os
import time
import threading
import io
from PIL import Image
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ── User-configurable settings ────────────────────────────────────────────────
BUTTON_PIN     = 17          # BCM GPIO pin the button is wired to (other leg → GND)
GEMINI_MODEL   = "gemini-3-flash-preview"
VISION_PROMPT  = (
    "You are assisting a visually impaired person. "
    "Look at this image and describe what you see clearly and concisely "
    "in two or three sentences. Focus on people, objects, text, and surroundings."
)

# Flask server URL — Gemini result is POSTed here so the browser speaks it.
SERVER_URL     = "http://localhost:5000"
# ─────────────────────────────────────────────────────────────────────────────

# ── GPIO import (gracefully degrades to keyboard-Enter on non-RPi machines) ──
try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except (ImportError, RuntimeError):
    _GPIO_AVAILABLE = False
    print("[WARN] RPi.GPIO not found — running in test mode (press Enter to trigger).")

# ── Global state ──────────────────────────────────────────────────────────────
_processing_lock = threading.Lock()


# ── Initialisation ────────────────────────────────────────────────────────────

def _init_gemini():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Add it to a .env file or export it as an environment variable."
        )
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(GEMINI_MODEL)


def push_to_browser(text: str):
    """POST Gemini text to Flask → SSE → browser speak()."""
    try:
        requests.post(
            f"{SERVER_URL}/vision/result",
            json={"text": text},
            timeout=5,
        )
        print("[PUSH] Sent to browser.")
    except Exception as exc:
        print(f"[PUSH ERROR] Could not reach server: {exc}")


# ── Core pipeline ─────────────────────────────────────────────────────────────

def capture_image() -> Image.Image | None:
    """Fetch one JPEG frame from the server's /capture endpoint."""
    try:
        resp = requests.get(f"{SERVER_URL}/capture", timeout=10)
        resp.raise_for_status()
        image = Image.open(io.BytesIO(resp.content)).convert("RGB")
        print("[INFO] Image captured via server.")
        return image
    except Exception as exc:
        print(f"[ERROR] Could not fetch image from server: {exc}")
        return None


def ask_gemini(model, pil_image: Image.Image) -> str:
    """Send the PIL image to Gemini and return the description text."""
    response = model.generate_content([VISION_PROMPT, pil_image])
    return response.text.strip()


def run_pipeline(model):
    """Full button-press pipeline — runs in a background thread."""
    if not _processing_lock.acquire(blocking=False):
        print("[SKIP] Already handling a previous press — ignoring.")
        return
    try:
        push_to_browser("Capturing image, please wait.")

        image = capture_image()
        if image is None:
            push_to_browser("Camera error. Please check the camera connection and try again.")
            return

        push_to_browser("Analyzing the image.")
        try:
            description = ask_gemini(model, image)
            print(f"[GEMINI] {description}")
            push_to_browser(description)
        except Exception as exc:
            print(f"[ERROR] Gemini request failed: {exc}")
            push_to_browser("Sorry, I could not analyze the image. Please check the internet connection.")
    finally:
        _processing_lock.release()


# ── GPIO / input handling ─────────────────────────────────────────────────────

def poll_button(model):
    """Poll the button pin every 50 ms — avoids add_event_detect kernel bugs."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    print(f"[GPIO] Polling BCM pin {BUTTON_PIN}. Press button to capture.")

    last_state = GPIO.HIGH
    debounce_until = 0.0

    while True:
        state = GPIO.input(BUTTON_PIN)
        now = time.monotonic()
        # Detect falling edge (HIGH → LOW) outside debounce window
        if last_state == GPIO.HIGH and state == GPIO.LOW and now >= debounce_until:
            debounce_until = now + 0.6          # 600 ms debounce
            threading.Thread(
                target=run_pipeline, args=(model,), daemon=True
            ).start()
        last_state = state
        time.sleep(0.05)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    model = _init_gemini()

    if _GPIO_AVAILABLE:
        try:
            poll_button(model)          # blocks here; exits on Ctrl+C
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down.")
        finally:
            GPIO.cleanup()
    else:
        # Non-RPi test mode: press Enter to simulate a button press
        print("[TEST] Press Enter to simulate a button press. Ctrl+C to quit.\n")
        try:
            while True:
                input()
                threading.Thread(
                    target=run_pipeline, args=(model,), daemon=True
                ).start()
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down.")


if __name__ == "__main__":
    main()
