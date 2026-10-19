"""Run ONLY in an owned, qualified zeocore Python 3.14 environment.

No dependency is downloaded by this bridge. The exact selected source commit
is declared in core-validator-input.json; its owned installed qualification is
still a host input, and absence fails closed.
"""

import sys


def main() -> int:
    try:
        from zeo_core.contracts.ui import UiRefused, validate_bytes

    except Exception:
        return 1

    try:
        raw = sys.stdin.buffer.read(262_145)
        result = validate_bytes(raw)
        sys.stdout.write(result.model_dump_json(by_alias=True, exclude_unset=True))
        return 0
    except UiRefused:
        # Python itself can exit 2 for a missing script. Require a bridge marker
        # as well as a distinct code before reporting a canonical refusal.
        sys.stdout.write("ZEO_UI_REFUSED_V1\n")
        return 65
    except Exception:
        # Never print provider data, raw payloads, credentials or error values.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
