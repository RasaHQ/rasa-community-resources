"""Show the same checked advice result with different native memory inputs."""

import json
import tempfile
from pathlib import Path
from shop_adviser.native_fixture import observe_handoff_owner_mutation

if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as directory:
        print(
            json.dumps(
                observe_handoff_owner_mutation(Path(directory) / "memory.sqlite"),
                indent=2,
            )
        )
