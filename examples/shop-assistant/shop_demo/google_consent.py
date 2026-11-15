"""Compatibility entry point for the Codespace paste-back sign-in command."""
from .google_signin import main

if __name__ == "__main__":
    raise SystemExit(main())
