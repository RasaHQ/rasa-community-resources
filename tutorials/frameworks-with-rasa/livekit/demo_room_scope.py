"""Actual native stream observations for two synthetic rooms."""
import asyncio,json
from rasa_room.native_fixture import observe_two_rooms
async def main():
    for mutate in (False,True): print(json.dumps(await observe_two_rooms(participant_only=mutate),sort_keys=True))
if __name__=="__main__":asyncio.run(main())
