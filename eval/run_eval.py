"""
Evaluation Run (M6)
Runs B0, B1, P (Full CareLoop) systems across personas and volunteer probability sweep.
Produces CSV and markdown tables in eval/results/.
"""
import csv
import os
import random
import sys
import time
from typing import Any

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from careloop.config import load_slots
from careloop.extraction.verifier import Verifier
from careloop.flags.engine import FlagEngine
from careloop.flags.lexical_net import LexicalSafetyNet
from careloop.planner.planner import QuestionPlanner
from careloop.providers.mock import MockLLMClient
from careloop.state.slot_store import EvidenceStore, SlotStore
from eval.metrics.metrics import (
    extraction_f1,
    information_gain_per_question,
    unnecessary_question_rate,
)

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_persona(persona_id: str) -> tuple:
    base = os.path.join(os.path.dirname(__file__), "personas")
    profile = load_yaml(os.path.join(base, "profiles.yaml"))[persona_id]
    truth = load_yaml(os.path.join(base, f"{persona_id}_truth.yaml"))
    return profile, truth


MOCK_PATIENT_RESPONSES_BY_SLOT = {
    "chest_pain": "no I don't have any chest pain today",
    "breathlessness": "no breathlessness",
    "recent_fall": "no I haven't fallen",
    "severe_dizziness_fainting": "no dizziness",
    "med_taken_today": "yes I took my morning tablet",
    "side_effects": "no side effects",
    "sleep_hours": "I slept about 7 hours",
    "activity_minutes": "I walked for about 30 minutes",
    "hydration_glasses": "I drank about 5 glasses of water",
    "mood_wellbeing": "my mood is okay, about 7 out of 10",
    "patient_concerns": "no concerns today",
    "weight_kg": "my weight is 70 kg",
    "default": "I'm doing okay today thank you",
}


def mock_patient_response(slot_id: str, fact_sheet: dict, volunteer_prob: float, rng: random.Random) -> str:
    """Generate a mock patient response - supports disclosure policy."""
    true_val = fact_sheet.get(slot_id)
    if true_val is None:
        return MOCK_PATIENT_RESPONSES_BY_SLOT.get(slot_id, MOCK_PATIENT_RESPONSES_BY_SLOT["default"])

    # Volunteer probability
    if rng.random() > volunteer_prob:
        return "I'm not sure"  # Vague non-answer

    if isinstance(true_val, bool):
        if true_val:
            return f"yes I have {slot_id.replace('_', ' ')}"
        else:
            return f"no I don't have {slot_id.replace('_', ' ')}"
    elif isinstance(true_val, (int, float)):
        return f"about {true_val}"
    return str(true_val)


def run_careloop_system(profile: dict, fact_sheet: dict, volunteer_prob: float,
                         seed: int, day: int, llms: dict[str, Any] = None) -> dict[str, Any]:
    """Run the full CareLoop system (P) for one session."""
    rng = random.Random(seed)
    llms = llms or {"conversation": MockLLMClient(), "extractor": MockLLMClient()}
    slots = load_slots()
    store = SlotStore(slots)
    evidence_store = EvidenceStore()
    planner = QuestionPlanner(slots, "daily")
    verifier = Verifier()
    flag_engine = FlagEngine()
    lexical_net = LexicalSafetyNet()

    questions_asked = 0
    repeated_questions = 0
    slots_resolved_per_q = []
    asked_slot_ids = []
    turns = []

    for step in range(12):  # max steps
        action = planner.next_action(store, questions_asked)
        if action.type == "close":
            break
        if action.type not in ("ask_slot", "followup"):
            continue

        slot_id = action.slot_id
        if slot_id in asked_slot_ids:
            repeated_questions += 1
        asked_slot_ids.append(slot_id)

        patient_response = mock_patient_response(slot_id, fact_sheet, volunteer_prob, rng)
        turns.append({"role": "user", "content": patient_response, "turn_id": f"t{step}"})

        # Simulate extraction (deterministic mock)
        from careloop.extraction.extractor import SlotUpdate
        from careloop.models.data_models import SlotStatus
        true_val = fact_sheet.get(slot_id)
        if true_val is not None and volunteer_prob >= rng.random():
            if isinstance(true_val, bool):
                status = SlotStatus.answered if true_val else SlotStatus.denied
            else:
                status = SlotStatus.answered
            quote_val = f"{true_val}" if not isinstance(true_val, bool) else ("yes" if true_val else "no")
            quote = f"{slot_id.replace('_', ' ')} {quote_val}"
            upd = SlotUpdate(slot_id=slot_id, status=status, value=true_val,
                             confidence=0.9, quote=quote)
            verified = verifier.verify([upd], turns)
            if verified and verified[0].status == "supported":
                prev = store.get(slot_id).status
                store.update(slot_id, upd.status, upd.value, upd.confidence, f"t{step}", upd.quote)
                new = store.get(slot_id).status
                if prev != new and new in (SlotStatus.answered, SlotStatus.denied):
                    slots_resolved_per_q.append(1)
                else:
                    slots_resolved_per_q.append(0)
            else:
                slots_resolved_per_q.append(0)
        else:
            slots_resolved_per_q.append(0)

        # Flag check
        lexical_hits = lexical_net.scan(patient_response)
        flags = flag_engine.evaluate(store, "realtime", f"sess_{seed}_{day}", lexical_hits=lexical_hits)
        if any(f.level == "red" for f in flags):
            planner.set_interrupt()

        questions_asked += 1

    coverage = store.coverage_rate()
    ig = information_gain_per_question(sum(slots_resolved_per_q), questions_asked)
    uqr = unnecessary_question_rate(repeated_questions, questions_asked)

    # Extraction F1 vs ground truth
    predicted = {sid: s.value for sid, s in store.all_states().items()
                 if s.value is not None}
    gt = {k: v for k, v in fact_sheet.items() if not isinstance(v, list)}
    f1_scores = extraction_f1(predicted, gt)

    return {
        "system": "P",
        "coverage": coverage,
        "ig": ig,
        "uqr": uqr,
        "questions_asked": questions_asked,
        "extraction_f1": f1_scores["f1"],
        "extraction_precision": f1_scores["precision"],
        "extraction_recall": f1_scores["recall"],
    }


def run_baseline_b0(profile: dict, fact_sheet: dict, volunteer_prob: float,
                     seed: int, day: int) -> dict[str, Any]:
    """B0: Naive LLM - no state tracking, random question order."""
    rng = random.Random(seed)
    slots = load_slots()
    # No state tracker - just ask random slots
    all_slots = list(slots)
    rng.shuffle(all_slots)
    questions_asked = 0
    slots_resolved = 0
    asked = []
    repeated = 0

    store = SlotStore(slots)  # Track for coverage measurement only
    from careloop.models.data_models import SlotStatus

    for spec in all_slots[:10]:
        if spec.slot_id in asked:
            repeated += 1
        asked.append(spec.slot_id)
        true_val = fact_sheet.get(spec.slot_id)
        if true_val is not None and rng.random() < volunteer_prob:
            if isinstance(true_val, bool):
                status = SlotStatus.answered if true_val else SlotStatus.denied
            else:
                status = SlotStatus.answered
            store.update(spec.slot_id, status, true_val, 0.8, f"t{questions_asked}", "yes")
            slots_resolved += 1
        questions_asked += 1

    coverage = store.coverage_rate()
    predicted = {sid: s.value for sid, s in store.all_states().items() if s.value is not None}
    gt = {k: v for k, v in fact_sheet.items() if not isinstance(v, list)}
    f1_scores = extraction_f1(predicted, gt)
    ig = information_gain_per_question(slots_resolved, questions_asked)
    uqr = unnecessary_question_rate(repeated, questions_asked)

    return {
        "system": "B0",
        "coverage": coverage,
        "ig": ig,
        "uqr": uqr,
        "questions_asked": questions_asked,
        "extraction_f1": f1_scores["f1"],
        "extraction_precision": f1_scores["precision"],
        "extraction_recall": f1_scores["recall"],
    }


def run_baseline_b1(profile: dict, fact_sheet: dict, volunteer_prob: float,
                     seed: int, day: int) -> dict[str, Any]:
    """B1: Checklist LLM - asks slots in fixed order without state tracking."""
    rng = random.Random(seed)
    slots = load_slots()
    # B1 follows a fixed checklist (sorted by tier then slot_id)
    ordered_slots = sorted(slots, key=lambda s: (s.tier, s.slot_id))
    questions_asked = 0
    slots_resolved = 0
    asked = []
    repeated = 0
    store = SlotStore(slots)
    from careloop.models.data_models import SlotStatus

    for spec in ordered_slots[:10]:
        if spec.slot_id in asked:
            repeated += 1
        asked.append(spec.slot_id)
        true_val = fact_sheet.get(spec.slot_id)
        if true_val is not None and rng.random() < volunteer_prob:
            if isinstance(true_val, bool):
                status = SlotStatus.answered if true_val else SlotStatus.denied
            else:
                status = SlotStatus.answered
            store.update(spec.slot_id, status, true_val, 0.85, f"t{questions_asked}", "yes")
            slots_resolved += 1
        questions_asked += 1

    coverage = store.coverage_rate()
    predicted = {sid: s.value for sid, s in store.all_states().items() if s.value is not None}
    gt = {k: v for k, v in fact_sheet.items() if not isinstance(v, list)}
    f1_scores = extraction_f1(predicted, gt)
    ig = information_gain_per_question(slots_resolved, questions_asked)
    uqr = unnecessary_question_rate(repeated, questions_asked)

    return {
        "system": "B1",
        "coverage": coverage,
        "ig": ig,
        "uqr": uqr,
        "questions_asked": questions_asked,
        "extraction_f1": f1_scores["f1"],
        "extraction_precision": f1_scores["precision"],
        "extraction_recall": f1_scores["recall"],
    }


def run_eval(mini: bool = False):
    """Run the full evaluation matrix."""
    global run_eval_llms
    llms_to_use = globals().get("run_eval_llms", {"conversation": MockLLMClient(), "extractor": MockLLMClient()})
    
    results = []
    persona_ids = ["persona_a"]  # For mini; full adds persona_b, persona_c
    if not mini:
        persona_ids = ["persona_a", "persona_b", "persona_c"]

    volunteer_probs = [0.9, 0.7, 0.5, 0.3]
    seeds = [42, 123, 777]
    days_to_eval = [3, 7, 11] if not mini else [11]  # Day 11 has RED flag for persona A

    for persona_id in persona_ids:
        profile, truth = load_persona(persona_id)
        for volunteer_prob in volunteer_probs:
            for seed in seeds:
                for day_idx in days_to_eval:
                    if day_idx - 1 >= len(truth["days"]):
                        continue
                    fact_sheet = truth["days"][day_idx - 1]["slots"]
                    planted = truth["days"][day_idx - 1].get("planted_events", [])

                    for system_fn, system_name in [
                        (run_careloop_system, "P"),
                        (run_baseline_b0, "B0"),
                        (run_baseline_b1, "B1"),
                    ]:
                        if system_name == "P":
                            row = system_fn(profile, fact_sheet, volunteer_prob, seed, day_idx, llms=llms_to_use)
                        else:
                            row = system_fn(profile, fact_sheet, volunteer_prob, seed, day_idx)
                        row.update({
                            "persona": persona_id,
                            "volunteer_prob": volunteer_prob,
                            "seed": seed,
                            "day": day_idx,
                            "planted_events": len(planted),
                        })
                        results.append(row)
                        print(f"  {persona_id} | p={volunteer_prob} | seed={seed} | day={day_idx} | {system_name} "
                              f"-> cov={row['coverage']:.2f} ig={row['ig']:.2f} f1={row['extraction_f1']:.2f}")

    # Write CSV
    tag = "mini" if mini else "full"
    csv_path = os.path.join(RESULTS_DIR, f"eval_{tag}.csv")
    if results:
        with open(csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
        print(f"\nResults saved to {csv_path}")

    # Write markdown table
    md_path = os.path.join(RESULTS_DIR, f"eval_{tag}.md")
    with open(md_path, "w") as f:
        f.write(f"# CareLoop Evaluation Results ({tag.upper()})\n\n")
        f.write("*Results from MOCK providers — offline deterministic run.*\n\n")
        f.write("> All thresholds are prototype/illustrative. Not clinical recommendations.\n\n")

        # Summary by system and volunteer_prob
        from collections import defaultdict
        agg: dict[str, dict[float, list]] = defaultdict(lambda: defaultdict(list))
        for row in results:
            agg[row["system"]][row["volunteer_prob"]].append(row)

        f.write("## Summary: Coverage and Extraction F1 by System and Volunteer Probability\n\n")
        f.write("| System | p=0.9 cov | p=0.7 cov | p=0.5 cov | p=0.3 cov | p=0.9 F1 | p=0.7 F1 | p=0.5 F1 | p=0.3 F1 |\n")
        f.write("|--------|-----------|-----------|-----------|-----------|----------|----------|----------|----------|\n")
        for sys_name in ["P", "B1", "B0"]:
            row_vals = []
            for metric in ["coverage", "extraction_f1"]:
                for prob in [0.9, 0.7, 0.5, 0.3]:
                    vals = [r[metric] for r in agg[sys_name][prob]]
                    mean = sum(vals) / len(vals) if vals else 0.0
                    row_vals.append(f"{mean:.2f}")
            f.write(f"| **{sys_name}** | {' | '.join(row_vals)} |\n")

        f.write("\n\n## All Results\n\n")
        f.write("| Persona | p | Seed | Day | System | Coverage | IG | UQR | F1 |\n")
        f.write("|---------|---|------|-----|--------|----------|----|-----|----|\n")
        for row in results:
            f.write(
                f"| {row['persona']} | {row['volunteer_prob']} | {row['seed']} | {row['day']} "
                f"| {row['system']} | {row['coverage']:.2f} | {row['ig']:.2f} | {row['uqr']:.2f} | {row['extraction_f1']:.2f} |\n"
            )

    print(f"Markdown table saved to {md_path}")
    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mini", action="store_true", help="Run mini evaluation only")
    parser.add_argument("--provider", type=str, default="mock", help="Provider (mock or google)")
    parser.add_argument("--patients", type=int, default=3, help="Number of patients to evaluate")
    parser.add_argument("--days", type=int, default=3, help="Number of days to evaluate")
    parser.add_argument("--seed", type=int, default=42, help="Seed to use for single run")
    args = parser.parse_args()
    
    llms = {}
    if args.provider == "google":
        from careloop.providers.google_llm import GoogleLLMClient
        # Budget warning for google provider
        estimated_calls = args.patients * args.days * 1 * 12 * 2  # up to 12 turns, 2 calls per turn (conversation + extractor)
        print(f"⚠️ WARNING: Running real evaluation against {args.provider}.")
        print(f"⚠️ Estimated API calls: ~{estimated_calls}")
        if estimated_calls > 15:
            print("⚠️ This might exceed your free tier quota (20/day)!")
        print("Starting in 3 seconds...")
        time.sleep(3)
        llms = {
            "conversation": GoogleLLMClient(model_name="gemini-2.5-flash-lite"),
            "extractor": GoogleLLMClient(model_name="gemini-2.5-flash-lite")
        }
    else:
        llms = {"conversation": MockLLMClient(), "extractor": MockLLMClient()}
        
    global run_eval_llms
    run_eval_llms = llms
    
    print(f"Running {'mini' if args.mini else 'full'} evaluation with {args.provider} provider...")
    run_eval(mini=args.mini)
