#!/usr/bin/env python3
"""LED counter — chases a pixel down the strip, pausing every 10 LEDs so you can count."""

import time
import board
import neopixel_spi as neopixel

# Start with a high guess — only lit pixels will be visible
MAX_LEDS = 150
BRIGHTNESS = 0.5

spi = board.SPI()
pixels = neopixel.NeoPixel_SPI(spi, MAX_LEDS, brightness=BRIGHTNESS, auto_write=False)

pixels.fill((0, 0, 0))
pixels.show()

print(f"Chasing a pixel across up to {MAX_LEDS} LEDs.")
print("Watch the strip — note the last LED number that lights up.\n")

try:
    for i in range(MAX_LEDS):
        pixels.fill((0, 0, 0))
        pixels[i] = (255, 255, 0)
        pixels.show()

        if (i + 1) % 10 == 0:
            print(f"  LED #{i + 1}")
            time.sleep(1.0)
        else:
            time.sleep(0.15)

    print(f"\nReached {MAX_LEDS}. All LEDs off.")
    pixels.fill((0, 0, 0))
    pixels.show()

except KeyboardInterrupt:
    print(f"\nStopped. Last LED attempted: #{i + 1}")
    pixels.fill((0, 0, 0))
    pixels.show()
