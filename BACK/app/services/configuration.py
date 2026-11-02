import json
from functools import lru_cache
from pathlib import Path
from typing import Any


@lru_cache(maxsize=1)
def get_config() -> dict[str, Any]:
    config_path = Path(__file__).resolve().parents[3] / "config.json"
    with config_path.open(encoding="utf-8") as config_file:
        return json.load(config_file)
