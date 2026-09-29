from enum import Enum
from typing import Any, Literal, Optional, List, Tuple
from pydantic import BaseModel, Field
from datetime import datetime, date

class SlotStatus(str, Enum):
    not_asked = "not_asked"
    asked_unclear = "asked_unclear"
    answered = "answered"
    denied = "denied"
    declined = "declined"          # optional 5th state

class SlotState(BaseModel):
    slot_id: str
    status: SlotStatus = SlotStatus.not_asked
    value: Optional[Any] = None                    # bool | number | str | dict
    confidence: float = 0.0
    source_turn_id: Optional[str] = None
    quote: Optional[str] = None
    asked_count: int = 0
    updated_at: Optional[datetime] = None
    unclear_reason: Optional[str] = None

class SlotSpec(BaseModel):                          # loaded from config/slots.yaml
    slot_id: str
    domain: Literal["safety","medication","symptom","vital","sleep","activity",
                    "nutrition","hydration","wellbeing","concern","appointment"]
    value_type: Literal["bool","number","text","enum","scale_0_10","list"]
    unit: Optional[str] = None
    tier: Literal[1,2,3]                            # 1 = safety-critical
    frequency: Literal["every_session","daily","weekly","conditional"]
    conditions: List[str] = Field(default_factory=list)                      # personas/conditions where relevant
    followups: List[str] = Field(default_factory=list)                       # slot_ids asked if positive
    ask_intents: List[str]                          # phrasing intents for the LLM
    normal_range_ref: Optional[str] = None          # config key, never hardcoded

class EvidenceRecord(BaseModel):
    evidence_id: str
    patient_id: str
    session_id: str
    turn_id: Optional[str]
    slot_id: Optional[str]
    value: Any
    quote: Optional[str]
    source_type: Literal["patient_statement","patient_reported_measurement","computed"]
    timestamp: datetime

class PlannerAction(BaseModel):
    type: Literal["ask_slot","followup","educate","confirm","close","escalate_message"]
    slot_id: Optional[str] = None
    intent: Optional[str] = None
    tone_hint: Literal["neutral","warm","reassuring","brief"] = "warm"
    must_confirm: bool = False

class FlagEvent(BaseModel):
    flag_id: str
    level: Literal["red","yellow","green"]
    message: str
    evidence_ids: List[str]
    rule_version: str
    rule_source: str                                # "prototype/illustrative" | "clinician-configured"
    scope: Literal["realtime","end_of_session","longitudinal"]
    routed_to: Optional[str] = None
    raised_at: datetime

class TrendFinding(BaseModel):
    metric: str
    window_days: int
    direction: Literal["improving","worsening","stable","insufficient_data"]
    baseline: Optional[float]
    latest: Optional[float]
    delta: Optional[float]
    series: List[Tuple[date, Optional[float]]]
    evidence_ids: List[str]

class ReportClaim(BaseModel):
    claim_id: str
    section: Literal["overview","red","yellow","green","trends","concerns","followup","gaps"]
    type: str                                       # metric_change | flag | adherence | gap | concern | ...
    facts: dict[str, Any]                           # the ONLY source of numbers for the sentence
    evidence_ids: List[str]
    severity: Optional[Literal["red","yellow","green"]] = None

class ClinicianReport(BaseModel):
    patient_id: str
    period: Tuple[date, date]
    sections: dict[str, List[dict]]                 # each item: {claim_id, sentence, evidence_ids}
    generated_at: datetime
    verification: dict                              # pass/fail, fallbacks used
    disclaimer: str
