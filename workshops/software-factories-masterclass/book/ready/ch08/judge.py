"""Use the existing factory for this data-only task, with its own profile."""
from pathlib import Path
import sys
from factory_engine import factory

ROOT = Path(__file__).resolve().parent


def main(task, candidate, output):
    return factory.main(task, candidate, output, pack_root=ROOT,
                        environment_path=ROOT / 'environment.json', strict=True)


if __name__ == '__main__':
    raise SystemExit(main(*sys.argv[1:4]))
