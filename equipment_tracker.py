#!/usr/bin/env python3
"""Equipment tracking LED controller — visualizes checkout authorization on a NeoPixel strip."""

import argparse
import enum
import json
import math
import threading
import time

import paho.mqtt.client as mqtt

from config import (
    BEARER_GRACE,
    BEARER_TAG,
    EQUIPMENT_TAG,
    FLASH_DURATION,
    FLASH_HZ,
    LED_BRIGHTNESS,
    LED_TOTAL,
    MQTT_HOST,
    MQTT_PORT,
    MQTT_TOPIC,
    PULSE_HZ,
    TAG_ALIASES,
    TAGS,
    TICK_INTERVAL,
    ZONE_ID,
    ZONE_NAME,
)

# ---------------------------------------------------------------------------
# Mock pixel class (for testing without hardware)
# ---------------------------------------------------------------------------

class MockPixels:
    def __init__(self, count):
        self._pixels = [(0, 0, 0)] * count

    def __setitem__(self, index, color):
        self._pixels[index] = color

    def __getitem__(self, index):
        return self._pixels[index]

    def fill(self, color):
        self._pixels = [color] * len(self._pixels)

    def show(self):
        pass


# ---------------------------------------------------------------------------
# Zone state enum
# ---------------------------------------------------------------------------

class ZoneState(enum.Enum):
    OFF = "OFF"
    SOLID_YELLOW = "SOLID_YELLOW"
    PULSE_YELLOW = "PULSE_YELLOW"
    FLASH_GREEN = "FLASH_GREEN"
    FLASH_RED = "FLASH_RED"


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

lock = threading.Lock()
zone_tags: set[str] = set()          # tags currently in the zone
current_state: ZoneState = ZoneState.OFF
flash_on: bool = False
flash_timer_end: float = 0.0         # monotonic time when flash expires
bearer_last_seen: float = 0.0        # monotonic time when T2 was last in zone
pixels = None
mock_mode = False


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

COLOR_YELLOW = (255, 255, 0)
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (255, 0, 0)
COLOR_OFF = (0, 0, 0)


# ---------------------------------------------------------------------------
# State logic
# ---------------------------------------------------------------------------

def compute_state_from_zone() -> ZoneState:
    """Determine state from current zone occupancy (ignoring flash overrides)."""
    if EQUIPMENT_TAG not in zone_tags:
        return ZoneState.OFF
    # Equipment is in zone
    if BEARER_TAG in zone_tags:
        return ZoneState.PULSE_YELLOW
    return ZoneState.SOLID_YELLOW


def bearer_present() -> bool:
    """Check if bearer is in zone or left within the grace window."""
    if BEARER_TAG in zone_tags:
        return True
    return (time.monotonic() - bearer_last_seen) < BEARER_GRACE


def on_tag_event(tag_id: str, event_type: str):
    """Process a tag enter/leave and update state. Called with lock held."""
    global current_state, flash_timer_end, bearer_last_seen

    if event_type == "entered station":
        zone_tags.add(tag_id)
    elif event_type == "left station":
        # Record when bearer leaves for grace window
        if tag_id == BEARER_TAG:
            bearer_last_seen = time.monotonic()
        zone_tags.discard(tag_id)

    # T1 leaving triggers flash logic
    if tag_id == EQUIPMENT_TAG and event_type == "left station":
        if bearer_present():
            current_state = ZoneState.FLASH_GREEN
            print(f"  -> FLASH_GREEN (authorized checkout)")
        else:
            current_state = ZoneState.FLASH_RED
            print(f"  -> FLASH_RED (unauthorized removal)")
        flash_timer_end = time.monotonic() + FLASH_DURATION
        return

    # If we're in a flash state, don't interrupt it
    if current_state in (ZoneState.FLASH_GREEN, ZoneState.FLASH_RED):
        return

    # Otherwise, recompute from zone
    current_state = compute_state_from_zone()


# ---------------------------------------------------------------------------
# LED output
# ---------------------------------------------------------------------------

def pulse_brightness() -> float:
    """Return 0.0–1.0 sinusoidal breathing value."""
    t = time.monotonic()
    return (math.sin(2 * math.pi * PULSE_HZ * t - math.pi / 2) + 1) / 2


def scale_color(color: tuple, brightness: float) -> tuple:
    return (int(color[0] * brightness), int(color[1] * brightness), int(color[2] * brightness))


def update_leds():
    """Map current state to LED colors and push to strip."""
    if current_state == ZoneState.OFF:
        color = COLOR_OFF
    elif current_state == ZoneState.SOLID_YELLOW:
        color = COLOR_YELLOW
    elif current_state == ZoneState.PULSE_YELLOW:
        b = pulse_brightness()
        color = scale_color(COLOR_YELLOW, b)
    elif current_state == ZoneState.FLASH_GREEN:
        color = COLOR_GREEN if flash_on else COLOR_OFF
    elif current_state == ZoneState.FLASH_RED:
        color = COLOR_RED if flash_on else COLOR_OFF
    else:
        color = COLOR_OFF

    pixels.fill(color)
    pixels.show()


# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------

def on_connect(client, userdata, flags, rc, properties=None):
    print(f"Connected to MQTT broker (rc={rc})")
    client.subscribe(MQTT_TOPIC)
    print(f"Subscribed to {MQTT_TOPIC}")


def resolve_tag_id(raw_id: str) -> str:
    """Map hardware tag ID to display ID (e.g. 'C39D' -> 'T1')."""
    return TAG_ALIASES.get(raw_id, raw_id)


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    raw_tag_id = payload.get("tag_id")
    event_type = payload.get("event_type", "")
    zone_id = payload.get("data", {}).get("station", "")

    print(f"  [MQTT] tag={raw_tag_id} event={event_type} zone={zone_id}")

    if not raw_tag_id or zone_id != ZONE_ID:
        return

    tag_id = resolve_tag_id(raw_tag_id)
    tag_role = TAGS.get(tag_id, "unknown")

    with lock:
        if event_type == "entered station":
            print(f"  [{ZONE_NAME}] +{tag_id} ({tag_role})")
        elif event_type == "left station":
            print(f"  [{ZONE_NAME}] -{tag_id} ({tag_role})")
        on_tag_event(tag_id, event_type)


# ---------------------------------------------------------------------------
# Tick loop
# ---------------------------------------------------------------------------

def tick_loop():
    """Background loop: toggle flash, expire flash timers, refresh LEDs."""
    global flash_on, current_state
    last = time.monotonic()
    flash_period = 1.0 / FLASH_HZ
    flash_elapsed = 0.0

    while True:
        time.sleep(TICK_INTERVAL)
        now = time.monotonic()
        dt = now - last
        last = now

        # Update flash toggle
        flash_elapsed += dt
        if flash_elapsed >= flash_period / 2:
            flash_on = not flash_on
            flash_elapsed = 0.0

        with lock:
            # Check flash timer expiry
            if current_state in (ZoneState.FLASH_GREEN, ZoneState.FLASH_RED):
                if now >= flash_timer_end:
                    current_state = compute_state_from_zone()

            update_leds()

            if mock_mode:
                state_label = current_state.value
                if current_state in (ZoneState.FLASH_GREEN, ZoneState.FLASH_RED):
                    state_label = current_state.value if flash_on else ""
                elif current_state == ZoneState.PULSE_YELLOW:
                    state_label = f"PULSE({pulse_brightness():.0%})"

                tags_str = ",".join(sorted(zone_tags)) if zone_tags else "(empty)"
                print(f"\r  State: [{state_label:<13s}]  Zone: {tags_str}", end="", flush=True)


# ---------------------------------------------------------------------------
# Initialization & main
# ---------------------------------------------------------------------------

def init_pixels(use_mock: bool):
    global pixels, mock_mode
    mock_mode = use_mock
    if use_mock:
        print("Running in MOCK mode (no hardware)")
        pixels = MockPixels(LED_TOTAL)
    else:
        import board
        import neopixel_spi as neopixel

        spi = board.SPI()
        pixels = neopixel.NeoPixel_SPI(
            spi, LED_TOTAL, brightness=LED_BRIGHTNESS, auto_write=False
        )
        print(f"NeoPixel SPI initialized ({LED_TOTAL} LEDs, brightness={LED_BRIGHTNESS})")


def main():
    parser = argparse.ArgumentParser(description="Equipment tracking LED controller")
    parser.add_argument("--mock", action="store_true", help="Run without real LEDs")
    args = parser.parse_args()

    init_pixels(args.mock)

    # Clear strip
    pixels.fill((0, 0, 0))
    pixels.show()

    # Start background tick thread
    tick_thread = threading.Thread(target=tick_loop, daemon=True)
    tick_thread.start()

    # MQTT
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to MQTT broker at {MQTT_HOST}:{MQTT_PORT} ...")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)

    print("Equipment tracker running. Ctrl+C to quit.")
    print(f"Zone: {ZONE_NAME} ({ZONE_ID})")
    print(f"Equipment tag: {EQUIPMENT_TAG}, Bearer tag: {BEARER_TAG}")
    print(f"Known tags: {', '.join(f'{t}({r})' for t, r in sorted(TAGS.items()))}")
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        pixels.fill((0, 0, 0))
        pixels.show()
        client.disconnect()


if __name__ == "__main__":
    main()
