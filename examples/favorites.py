"""List and play favorites from a media player."""

from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv

from ha_client import HAClient

load_dotenv()


async def main() -> None:
    url = os.environ["HA_URL"]
    token = os.environ["HA_TOKEN"]

    async with HAClient(url, token=token) as ha:
        player = ha.media_player("entertainment")
        favs = await player.favorites()
        for fav in favs:
            print(fav)
            # print(f"  {fav.media_content_type}: {fav.title}")

        # if favs:
        #    print(f"Playing: {favs[0].title}")
        #    #await favs[0].play()


if __name__ == "__main__":
    asyncio.run(main())
