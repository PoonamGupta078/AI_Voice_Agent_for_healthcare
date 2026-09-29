"""
Evaluation Metrics (M6)
Compute: coverage, information gain per question (IG), unnecessary question rate (UQR),
extraction F1, pertinent-negative accuracy, unsupported-claim rate, flag recall/precision.
"""
from typing import Any, Dict, List, Optional


def required_slot_coverage(session_result: Dict[str, Any]) -> float:
    """Fraction of required slots that were answered or denied."""
    return session_result.get("slot_coverage", 0.0)


def information_gain_per_question(slots_resolved: int, questions_asked: int) -> float:
    """Newly resolved slots / total questions asked."""
    if questions_asked == 0:
        return 0.0
    return slots_resolved / questions_asked


def unnecessary_question_rate(repeated_questions: int, total_questions: int) -> float:
    """Questions about already-answered slots / total questions."""
    if total_questions == 0:
        return 0.0
    return repeated_questions / total_questions


def extraction_f1(
    predicted: Dict[str, Any],
    ground_truth: Dict[str, Any],
    numeric_tolerance: float = 0.1,
) -> Dict[str, float]:
    """Compute P, R, F1 for slot extraction vs ground truth."""
    tp = fp = fn = 0
    for slot_id, true_val in ground_truth.items():
        pred_val = predicted.get(slot_id)
        if pred_val is None:
            fn += 1
        elif isinstance(true_val, (int, float)) and isinstance(pred_val, (int, float)):
            if abs(float(true_val) - float(pred_val)) <= numeric_tolerance * (abs(float(true_val)) + 1e-9):
                tp += 1
            else:
                fp += 1
                fn += 1
        elif str(true_val).lower() == str(pred_val).lower():
            tp += 1
        else:
            fp += 1
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def flag_recall_precision(
    raised_flags: List[str],
    planted_events: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Compute flag recall and precision vs planted events."""
    planted_ids = {ev["event_id"] for ev in planted_events}
    planted_levels = {ev["event_id"]: ev["flag_level"] for ev in planted_events}

    tp = sum(1 for f in raised_flags if f in planted_ids)
    fp = sum(1 for f in raised_flags if f not in planted_ids)
    fn = len(planted_ids) - tp

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    return {"precision": precision, "recall": recall, "tp": tp, "fp": fp, "fn": fn}


def unsupported_claim_rate(claims: List[Dict], verified_claims: List[Dict]) -> float:
    """Fraction of claims not supported by evidence."""
    if not claims:
        return 0.0
    unsupported = sum(1 for c in verified_claims if not c.get("supported", True))
    return unsupported / len(claims)
