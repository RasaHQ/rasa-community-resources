"""Run ONLY in an owned, qualified zeocore Python 3.14 environment.

No dependency is downloaded by this bridge. Core's approved exact version is a
deployment input still to be supplied; absence fails closed.
"""

import sys


def main() -> int:
    try:
        from zeo_core.contracts.ui.wire import UiRefused, validate_bytes

    except Exception:
        return 1

    try:
        raw = sys.stdin.buffer.read(262_145)
        result = validate_bytes(raw)
        sys.stdout.write(result.model_dump_json(by_alias=True, exclude_unset=True))
        return 0
    except UiRefused:
        return 2
    except Exception:
        # Never print provider data, raw payloads, credentials or error values.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
