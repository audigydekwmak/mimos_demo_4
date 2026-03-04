#!/usr/bin/env python3
"""Mock MQTT publisher for testing the equipment tracking controller."""

import json
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from config import MQTT_HOST, MQTT_PORT, MQTT_TOPIC, ZONE_ID, ZONE_NAME, TAGS

# Track current tag locations
tag_locations: dict[str, str] = {}  # tag_id -> zone_id


def publish_event(client: mqtt.Client, tag_id: str, event_type: str, zone_id: str):
    payload = {
        "tag_id": tag_id,
        "event_type": event_type,
        "data": {
            "station": zone_id,
            "restricted": "False",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    client.publish(MQTT_TOPIC, json.dumps(payload))
    role = TAGS.get(tag_id, "unknown")
    print(f"  Published: {tag_id}({role}) {event_type} @ {ZONE_NAME}")


def cmd_enter(client: mqtt.Client, parts: list[str]):
    if len(parts) < 3:
        print("Usage: enter <tag> <zone_number>  (e.g. enter T1 1)")
        return
    tag_id = parts[1].upper()
    zone_num = parts[2]
    if zone_num != "1":
        print("Only zone 1 exists in this demo.")
        return
    # If tag is already somewhere, leave first
    if tag_id in tag_locations:
        publish_event(client, tag_id, "left station", tag_locations[tag_id])
    publish_event(client, tag_id, "entered station", ZONE_ID)
    tag_locations[tag_id] = ZONE_ID


def cmd_leave(client: mqtt.Client, parts: list[str]):
    if len(parts) < 2:
        print("Usage: leave <tag>  (e.g. leave T1)")
        return
    tag_id = parts[1].upper()
    if tag_id not in tag_locations:
        print(f"Tag '{tag_id}' is not in any zone.")
        return
    publish_event(client, tag_id, "left station", tag_locations[tag_id])
    del tag_locations[tag_id]


def cmd_status():
    if not tag_locations:
        print("  No tags in zone.")
        return
    print(f"\n  {ZONE_NAME}:")
    for tag_id in sorted(tag_locations):
        role = TAGS.get(tag_id, "unknown")
        print(f"    {tag_id} ({role})")
    print()


def cmd_reset(client: mqtt.Client):
    for tag_id, zone_id in list(tag_locations.items()):
        publish_event(client, tag_id, "left station", zone_id)
    tag_locations.clear()
    print("  All tags cleared.")


def cmd_auto(client: mqtt.Client):
    """Automated demo sequence covering equipment checkout scenarios."""
    print("  Running auto demo sequence...\n")

    def step(desc, delay=2.0):
        print(f"\n  --- {desc} ---")
        time.sleep(0.3)

    def wait(sec=2.0):
        print(f"  ... waiting {sec}s")
        time.sleep(sec)

    # 1. T1 enters -> solid yellow
    step("T1 (equipment) enters zone -> SOLID YELLOW")
    cmd_enter(client, ["enter", "T1", "1"])
    wait(3.0)

    # 2. T2 enters -> pulse yellow
    step("T2 (bearer) also enters -> PULSE YELLOW")
    cmd_enter(client, ["enter", "T2", "1"])
    wait(3.0)

    # 3. T1 leaves while T2 is still in zone -> flash green (authorized checkout)
    step("T1 leaves while T2 still in zone -> FLASH GREEN (authorized checkout)")
    cmd_leave(client, ["leave", "T1"])
    wait(6.0)

    # Now T2 still in zone but no equipment -> should be OFF after flash
    step("T2 leaves (zone now empty) -> OFF")
    cmd_leave(client, ["leave", "T2"])
    wait(2.0)

    # 4. T1 enters again -> solid yellow
    step("T1 (equipment) enters again -> SOLID YELLOW")
    cmd_enter(client, ["enter", "T1", "1"])
    wait(3.0)

    # 5. T3 enters -> still solid yellow (T3 is unauthorized, doesn't change state)
    step("T3 (unauthorized) enters -> still SOLID YELLOW")
    cmd_enter(client, ["enter", "T3", "1"])
    wait(3.0)

    # 6. T1 leaves (T3 still there, no T2) -> flash red
    step("T1 leaves (only T3 present, no bearer) -> FLASH RED (unauthorized)")
    cmd_leave(client, ["leave", "T1"])
    wait(6.0)

    # 7. Cleanup
    step("Final cleanup")
    cmd_reset(client)
    wait(1.0)

    print("\n  Auto demo complete.\n")


def print_help():
    print("""
Commands:
  enter <tag> <zone>   -- Enter a tag into the zone (e.g. enter T1 1)
  leave <tag>          -- Remove tag from the zone
  status               -- Show tags in zone
  auto                 -- Run automated demo sequence
  reset                -- Remove all tags
  help                 -- Show this help
  quit / exit          -- Exit

Zone: 1 = """ + ZONE_NAME + """
Tags: """ + ", ".join(f"{t}({r})" for t, r in sorted(TAGS.items())) + """
""")


def main():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    client.loop_start()

    print(f"Mock publisher connected to {MQTT_HOST}:{MQTT_PORT}")
    print(f"Publishing to topic: {MQTT_TOPIC}")
    print_help()

    try:
        while True:
            try:
                line = input("mock> ").strip()
            except EOFError:
                break
            if not line:
                continue
            parts = line.split()
            cmd = parts[0].lower()

            if cmd == "enter":
                cmd_enter(client, parts)
            elif cmd == "leave":
                cmd_leave(client, parts)
            elif cmd == "status":
                cmd_status()
            elif cmd == "auto":
                cmd_auto(client)
            elif cmd == "reset":
                cmd_reset(client)
            elif cmd in ("help", "?"):
                print_help()
            elif cmd in ("quit", "exit", "q"):
                break
            else:
                print(f"Unknown command: '{cmd}'. Type 'help' for usage.")
    except KeyboardInterrupt:
        print()

    cmd_reset(client)
    client.loop_stop()
    client.disconnect()
    print("Disconnected.")


if __name__ == "__main__":
    main()
