"""Fetch a pinned public demo database; verify before installing it locally."""
import hashlib
from pathlib import Path
import urllib.request
ROOT = Path(__file__).resolve().parent
URL = "https://raw.githubusercontent.com/lerocha/chinook-database/7f67772503d71ba90f19283c38e93923addb43fa/ChinookDatabase/DataSources/Chinook_Sqlite.sqlite"
SHA256 = "7651ba378ac2fcd0dfc3c66fb101f7a7eed3ba39a612ec642b96e20702061f15"
if __name__ == "__main__":
    destination = ROOT / "data/chinook.sqlite"
    if destination.exists():
        data = destination.read_bytes()
    else:
        with urllib.request.urlopen(URL, timeout=30) as response:
            data = response.read()
    if hashlib.sha256(data).hexdigest() != SHA256:
        raise SystemExit("Database checksum mismatch; existing data left untouched")
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    print("Pinned Chinook database verified")
