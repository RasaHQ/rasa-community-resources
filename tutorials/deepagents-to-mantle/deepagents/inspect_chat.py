"""Retain a single native chat's messages locally, including tool results."""
import argparse
import asyncio
import json
from pathlib import Path
from agent import create_agent


def save(messages, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never replace a previous conversation receipt.
    with path.open('x') as handle:
        json.dump([m.model_dump(mode='json') for m in messages], handle, indent=2)
        handle.write('\n')


async def main(question: str, path: Path):
    graph = create_agent()
    result = await graph.ainvoke(
        {'messages': [{'role': 'user', 'content': question}]},
        {'recursion_limit': 40},
    )
    save(result['messages'], path)
    print(result['messages'][-1].content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        raise SystemExit('Output already exists; choose a new receipt path')
    asyncio.run(main(args.question, args.out))
