"""Load and expose resume profile."""

import json
from pathlib import Path
from functools import lru_cache

PROFILE_PATH = Path(__file__).resolve().parent.parent.parent / "shared" / "resume_profile.json"


@lru_cache
def load_profile() -> dict:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)
