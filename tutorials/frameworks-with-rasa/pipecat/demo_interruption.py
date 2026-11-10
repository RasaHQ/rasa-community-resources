"""Native queue/late-response control with scripted dialogue, no audio providers."""

import asyncio
import json
from rasa_dialogue.native_fixture import observe_late_response


async def main():
    for remove in [False, True]:
        print(json.dumps(await observe_late_response(remove_ownership_guard=remove)))


if __name__ == "__main__":
    asyncio.run(main())
