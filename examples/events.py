"""Receive state-change events from Home Assistant entities."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from haclient import HAClient


async def main() -> None:
    url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]

    async with HAClient(url, token=token) as ha:
        motion = ha.binary_sensor("front_door_motion")
        door = ha.binary_sensor("front_door_contact")

        @motion.on_state_change
        async def on_motion(old: Any, new: Any) -> None:
            if new and new.get("state") == "on":
                print("Motion detected!")

        @door.on_state_change
        def on_door(old: Any, new: Any) -> None:
            state = new.get("state") if new else "unknown"
            print(f"Door is now {state}")

        print("Listening for events. Ctrl+C to quit.")
        while True:
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())
