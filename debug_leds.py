#!/usr/bin/env python3
"""Debug script -- test LED colors and effects for the equipment tracking controller."""

import math
import time

import board
import neopixel_spi as neopixel

from config import LED_TOTAL, LED_BRIGHTNESS, PULSE_HZ, FLASH_HZ

spi = board.SPI()
pixels = neopixel.NeoPixel_SPI(spi, LED_TOTAL, brightness=LED_BRIGHTNESS, auto_write=False)

print(f"LED strip: {LED_TOTAL} LEDs, brightness={LED_BRIGHTNESS}")
print("Starting debug sequence... Ctrl+C to quit\n")

colors = [
    ("RED",     (255, 0, 0)),
    ("GREEN",   (0, 255, 0)),
    ("YELLOW",  (255, 255, 0)),
    ("WHITE",   (255, 255, 255)),
]

try:
    # 1) Fill entire strip with each color
    for name, color in colors:
        print(f"  All LEDs -> {name}")
        pixels.fill(color)
        pixels.show()
        time.sleep(1.5)

    # 2) Chase one pixel across the strip
    print("\n  Running chase (yellow)...")
    pixels.fill((0, 0, 0))
    pixels.show()
    for i in range(LED_TOTAL):
        pixels.fill((0, 0, 0))
        pixels[i] = (255, 255, 0)
        pixels.show()
        time.sleep(0.05)

    # 3) Solid yellow (equipment in zone, no bearer)
    print("\n  Solid yellow (SOLID_YELLOW state)...")
    pixels.fill((255, 255, 0))
    pixels.show()
    time.sleep(2)

    # 4) Pulse yellow (equipment + bearer in zone)
    print("  Pulse yellow (PULSE_YELLOW state)...")
    start = time.monotonic()
    while time.monotonic() - start < 5.0:
        t = time.monotonic()
        b = (math.sin(2 * math.pi * PULSE_HZ * t - math.pi / 2) + 1) / 2
        color = (int(255 * b), int(255 * b), 0)
        pixels.fill(color)
        pixels.show()
        time.sleep(0.03)

    # 5) Flash green (authorized checkout)
    print("  Flash green (FLASH_GREEN state)...")
    flash_period = 1.0 / FLASH_HZ
    for _ in range(12):
        pixels.fill((0, 255, 0))
        pixels.show()
        time.sleep(flash_period / 2)
        pixels.fill((0, 0, 0))
        pixels.show()
        time.sleep(flash_period / 2)

    # 6) Flash red (unauthorized checkout)
    print("  Flash red (FLASH_RED state)...")
    for _ in range(12):
        pixels.fill((255, 0, 0))
        pixels.show()
        time.sleep(flash_period / 2)
        pixels.fill((0, 0, 0))
        pixels.show()
        time.sleep(flash_period / 2)

    print("\nDone. LEDs off.")
    pixels.fill((0, 0, 0))
    pixels.show()

except KeyboardInterrupt:
    print("\nInterrupted. LEDs off.")
    pixels.fill((0, 0, 0))
    pixels.show()
