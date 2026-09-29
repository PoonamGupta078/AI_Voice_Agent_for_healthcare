import os
import yaml
from typing import List, Dict, Any
from careloop.models.data_models import SlotSpec

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config")

def load_yaml(filename: str) -> Dict[str, Any]:
    with open(os.path.join(CONFIG_DIR, filename), "r") as f:
        return yaml.safe_load(f)

def load_slots() -> List[SlotSpec]:
    data = load_yaml("slots.yaml")
    return [SlotSpec(**s) for s in data.get("slots", [])]

def load_flag_rules() -> Dict[str, Any]:
    return load_yaml("flag_rules.yaml")
