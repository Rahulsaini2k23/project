#!/usr/bin/env python3
"""
button_vision.py — Press button → capture image → Gemini analysis → TTS playback
Hardware : Raspberry Pi 4B  |  push button on GPIO  |  camera  |  USB speaker/mic
"""

import os
import time
import threading
import cv2
from PIL import Image
from gtts import gTTS
import pygame
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

# ── User-configurable settings ────────────────────────────────────────────────
BUTTON_PIN     = 17          # BCM GPIO pin the button is wired to (other leg → GND)
CAMERA_INDEX   = 0           # /dev/video0; try 1 if you have multiple cameras
GEMINI_MODEL   = "gemini-3-flash-preview"
VISION_PROMPT  = (
    "You are assisting a visually impaired person. "
    "Look at this image and describe what you see clearly and concisely "
    "in two or three sentences. Focus on people, objects, text, and surroundings."
)
TTS_LANG       = "en"
TMP_AUDIO_FILE = "/tmp/vision_reply.mp3"

# ALSA device for playback (None = system default).
# Run `aplay -l` on the RPi to list devices.
# Example for a USB speaker at card 1: "plughw:1,0"
AUDIO_DEVICE   = None
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


def _init_audio():
    """Initialise pygame mixer, optionally targeting a specific ALSA device."""
    if AUDIO_DEVICE:
        os.environ["SDL_AUDIODEV"] = AUDIO_DEVICE
    pygame.mixer.pre_init(frequency=44100, size=-16, channels=1, buffer=1024)
    pygame.mixer.init()


# ── Core pipeline ─────────────────────────────────────────────────────────────

def capture_image() -> Image.Image | None:
    """Open camera, grab one frame, return it as a PIL Image (or None on error)."""
    cam = cv2.VideoCapture(CAMERA_INDEX)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    time.sleep(0.4)                          # camera warm-up
    ok, frame = cam.read()
    cam.release()
    if not ok:
        print("[ERROR] Camera did not return a frame.")
        return None
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    print("[INFO] Image captured successfully.")
    return Image.fromarray(rgb)


def ask_gemini(model, pil_image: Image.Image) -> str:
    """Send the PIL image to Gemini and return the description text."""
    response = model.generate_content([VISION_PROMPT, pil_image])
    return response.text.strip()


def speak(text: str):
    """Convert text → MP3 via gTTS, then play through pygame."""
    print(f"[TTS] {text}")
    tts = gTTS(text=text, lang=TTS_LANG, slow=False)
    tts.save(TMP_AUDIO_FILE)
    pygame.mixer.music.load(TMP_AUDIO_FILE)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.05)


def run_pipeline(model):
    """Full button-press pipeline — runs in a background thread."""
    if not _processing_lock.acquire(blocking=False):
        print("[SKIP] Already handling a previous press — ignoring.")
        return
    try:
        speak("Capturing image, please wait.")

        image = capture_image()
        if image is None:
            speak("Camera error. Please check the camera connection and try again.")
            return

        speak("Analyzing the image.")
        try:
            description = ask_gemini(model, image)
            print(f"[GEMINI] {description}")
            speak(description)
        except Exception as exc:
            print(f"[ERROR] Gemini request failed: {exc}")
            speak("Sorry, I could not analyze the image. Please check the internet connection.")
    finally:
        _processing_lock.release()


# ── GPIO / input handling ─────────────────────────────────────────────────────

def _make_gpio_callback(model):
    def _callback(channel):
        threading.Thread(
            target=run_pipeline, args=(model,), daemon=True
        ).start()
    return _callback


def setup_gpio(model):
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(
        BUTTON_PIN,
        GPIO.FALLING,
        callback=_make_gpio_callback(model),
        bouncetime=600,           # ms — ignore bounces shorter than this
    )
    print(f"[GPIO] Ready. Listening on BCM pin {BUTTON_PIN}. Press button to capture.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    model = _init_gemini()
    _init_audio()

    if _GPIO_AVAILABLE:
        setup_gpio(model)
        print("[INFO] Running. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n[INFO] Shutting down.")
        finally:
            GPIO.cleanup()
            pygame.mixer.quit()
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
        finally:
            pygame.mixer.quit()


if __name__ == "__main__":
    main()
