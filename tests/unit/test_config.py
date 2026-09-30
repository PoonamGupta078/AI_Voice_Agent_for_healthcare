from careloop.config import load_flag_rules, load_slots


def test_load_slots():
    slots = load_slots()
    assert len(slots) > 0
    assert any(s.slot_id == "chest_pain" for s in slots)

def test_load_flag_rules():
    rules = load_flag_rules()
    assert "rules" in rules
    assert len(rules["rules"]) > 0
