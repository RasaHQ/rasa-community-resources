import asyncio,json
from rasa_room.room_fixture import observe_late_text
async def main():
    for reconnect in (False,True):
        for guarded in (False,True):print(json.dumps(await observe_late_text(guarded=guarded,reconnect=reconnect),sort_keys=True))
if __name__=="__main__":asyncio.run(main())
