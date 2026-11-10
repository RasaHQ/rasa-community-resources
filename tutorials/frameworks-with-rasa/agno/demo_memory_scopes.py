import json
import tempfile
from pathlib import Path

from shop_adviser.native_fixture import observe_memory_strategy

with tempfile.TemporaryDirectory() as directory:
    for reuse in [True, False]:
        for strategy in ["correct", "session-as-user", "omitted"]:
            print(
                json.dumps(
                    observe_memory_strategy(
                        Path(directory) / f"{strategy}-{reuse}.sqlite",
                        strategy,
                        reuse_agent=reuse,
                    ),
                    sort_keys=True,
                )
            )
