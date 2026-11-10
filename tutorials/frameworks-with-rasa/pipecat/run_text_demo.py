"""Exercise the native dialogue adapter against your separately started Rasa server.

This reader-run command uses the configured model through Rasa. It sends text
frames and prints text; connect existing audio services with compose.with_rasa.
"""

import argparse
import asyncio
import json
from aiohttp import ClientSession
from rasa_dialogue.client import RasaRestClient
from rasa_dialogue.native_fixture import NativePipeline, context_frame
from rasa_dialogue.processor import RasaDialogueProcessor


async def run(args):
    async with ClientSession() as session:
        client = RasaRestClient(session, args.endpoint, args.sender)
        async with NativePipeline(RasaDialogueProcessor(client)) as p:
            await p.feed(context_frame(args.message))
            await p.settle_requests(timeout=15)
            print(
                json.dumps(
                    {
                        "sender": args.sender,
                        "text_replies": p.capture.text,
                        "operational_errors": [frame.error for frame in p.errors],
                    }
                )
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--endpoint", default="http://127.0.0.1:5020/webhooks/rest/webhook"
    )
    parser.add_argument("--sender", default="public-juniper-demo")
    parser.add_argument(
        "--message", default="Is maintenance planned for the north area?"
    )
    asyncio.run(run(parser.parse_args()))
