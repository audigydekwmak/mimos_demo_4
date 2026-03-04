# MQTT
# MQTT_HOST = "192.168.0.183"
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "tag/events"

# Tags — role-based for equipment tracking
# T1 = equipment, T2 = authorized bearer, T3/T4 = unauthorized
TAGS = {
    "T1": "equipment",
    "T2": "bearer",
    "T3": "unauthorized",
    "T4": "unauthorized",
}

EQUIPMENT_TAG = "T1"
BEARER_TAG = "T2"

# Single zone
ZONE_ID = "Demo4_zone_1"
ZONE_NAME = "Equipment Zone"

# LED strip
LED_TOTAL = 60
LED_BRIGHTNESS = 0.8

# Timing
FLASH_HZ = 2.5           # Flashes per second (green/red flash)
FLASH_DURATION = 5.0      # How long flash states last (seconds)
PULSE_HZ = 0.5            # Breathing cycles per second
TICK_INTERVAL = 0.05       # Update loop interval in seconds
