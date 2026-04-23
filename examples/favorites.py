"""List and play favorites from a media player."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from haclient import HAClient

load_dotenv()


async def main() -> None:
    url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]

    async with HAClient(url, token=token) as ha:
        player = ha.media_player("entertainment")
        favs = await player.favorites()
        for fav in favs:
            print(fav)


if __name__ == "__main__":
    asyncio.run(main())
