import os
from typing import Any

import yaml

from careloop.models.data_models import SlotSpec

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

def load_yaml(filename: str) -> dict[str, Any]:
    with open(os.path.join(CONFIG_DIR, filename), "r") as f:
        return yaml.safe_load(f)

def load_slots() -> list[SlotSpec]:
    data = load_yaml("slots.yaml")
    return [SlotSpec(**s) for s in data.get("slots", [])]

def load_flag_rules() -> dict[str, Any]:
    return load_yaml("flag_rules.yaml")
