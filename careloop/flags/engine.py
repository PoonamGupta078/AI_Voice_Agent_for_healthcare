"""
Deterministic Flag Engine (M3)
Rules live in config/flag_rules.yaml. Uses safe evaluator — no eval().
"""
import yaml
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from simpleeval import SimpleEval, EvalWithCompoundTypes
from careloop.models.data_models import FlagEvent, SlotStatus
from careloop.state.slot_store import SlotStore


FLAG_RULES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config", "flag_rules.yaml"
)
ROUTING_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config", "routing.yaml"
)


def _load_rules() -> Dict:
    with open(FLAG_RULES_PATH) as f:
        return yaml.safe_load(f)


def _load_routing() -> Dict:
    if os.path.exists(ROUTING_PATH):
        with open(ROUTING_PATH) as f:
            return yaml.safe_load(f)
    return {}


class SlotProxy:
    """Provides attribute access to slot states for expression evaluation."""
    def __init__(self, slot_store: SlotStore):
        self._store = slot_store

    def __getattr__(self, slot_id: str):
        return SlotStateProxy(self._store.get(slot_id))


class SlotStateProxy:
    def __init__(self, slot_state):
        self._state = slot_state

    @property
    def status(self) -> str:
        return self._state.status.value

    @property
    def value(self):
        return self._state.value

    # Allow attribute access for sub-values (e.g. state.chest_pain.severity)
    def __getattr__(self, name: str):
        if self._state.value and isinstance(self._state.value, dict):
            return self._state.value.get(name)
        return None


class TrendProxy:
    """Provides attribute access to trend findings for expression evaluation."""
    def __init__(self, trends: Optional[Dict] = None):
        self._trends = trends or {}

    def __getattr__(self, metric: str):
        return TrendMetricProxy(self._trends.get(metric, {}))


class TrendMetricProxy:
    def __init__(self, data: dict):
        self._data = data

    def __getattr__(self, attr: str):
        return self._data.get(attr, None)


class LexicalProxy:
    def __init__(self, lexical_hits: Dict[str, bool]):
        self._hits = lexical_hits

    @property
    def self_harm_expression(self) -> bool:
        return self._hits.get("self_harm", False)

    @property
    def chest_pain(self) -> bool:
        return self._hits.get("chest_pain", False)

    @property
    def breathlessness(self) -> bool:
        return self._hits.get("breathlessness", False)


class FlagEngine:
    """
    Evaluates flag rules against the current slot state and trends.
    Never uses Python eval() — uses simpleeval.
    """

    def __init__(self):
        self.rules_config = _load_rules()
        self.routing = _load_routing()
        self._raised_flags: Dict[str, str] = {}  # flag_id -> session_id (dedup)

    def _safe_eval(self, expression: str, names: Dict[str, Any]) -> bool:
        """Safely evaluate rule expression using simpleeval."""
        try:
            s = EvalWithCompoundTypes(names=names)
            result = s.eval(expression)
            return bool(result)
        except Exception:
            return False

    def evaluate(
        self,
        store: SlotStore,
        scope: str,
        session_id: str,
        trends: Optional[Dict] = None,
        lexical_hits: Optional[Dict[str, bool]] = None,
        evidence_ids: Optional[List[str]] = None,
    ) -> List[FlagEvent]:
        """
        Evaluate all rules with matching scope.
        Returns list of new FlagEvents.
        """
        events = []
        rules = self.rules_config.get("rules", [])
        version = self.rules_config.get("version", "0.1")
        source = self.rules_config.get("defaults", {}).get("source", "prototype/illustrative")

        names = {
            "state": SlotProxy(store),
            "trend": TrendProxy(trends),
            "lexical": LexicalProxy(lexical_hits or {}),
            "T": {},  # thresholds injected per rule
        }

        for rule in rules:
            if rule.get("scope") != scope:
                continue
            rule_id = rule.get("id", "UNKNOWN")
            level = rule.get("level", "yellow")

            # Dedup: skip if already raised in this session
            dedupe_key = f"{session_id}:{rule_id}"
            if dedupe_key in self._raised_flags and level != "red":
                continue

            # Inject thresholds
            thresholds = rule.get("thresholds", {})
            names["T"] = thresholds

            expression = rule.get("when", "False")
            try:
                triggered = self._safe_eval(expression, names)
            except Exception:
                triggered = False

            if triggered:
                route = rule.get("route", "nurse")
                msg = self._build_message(rule, level)
                event = FlagEvent(
                    flag_id=rule_id,
                    level=level,
                    message=msg,
                    evidence_ids=evidence_ids or [],
                    rule_version=version,
                    rule_source=source,
                    scope=scope,
                    routed_to=route,
                    raised_at=datetime.utcnow(),
                )
                self._raised_flags[dedupe_key] = session_id
                events.append(event)

        return events

    def _build_message(self, rule: Dict, level: str) -> str:
        templates = {
            "red": "⚠️ Urgent: A potential health concern has been identified. The care team has been informed.",
            "yellow": "📋 Note: A health concern has been flagged for clinical review.",
            "green": "✅ Positive: Patient is showing improvement in this area.",
        }
        return rule.get("patient_message_key", templates.get(level, templates["yellow"]))
