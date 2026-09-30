"""
sim_demo: Run a simulated multi-turn conversation for one persona/day.
Usage: python -m eval.simulator.run
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import yaml

from eval.simulator.mock_simulator_llm import MockSimulatorLLMClient
from eval.simulator.patient_simulator import PatientSimulator


def load_yaml(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    base = os.path.join(os.path.dirname(__file__), "..")
    profile = load_yaml(os.path.join(base, "personas", "profiles.yaml"))["persona_c"]
    truth = load_yaml(os.path.join(base, "personas", "persona_c_truth.yaml"))
    day_data = truth["days"][11]  # Day 12 - the RED FLAG day

    llm = MockSimulatorLLMClient(seed=42)
    sim = PatientSimulator(
        persona=profile,
        fact_sheet=day_data["slots"],
        llm_client=llm,
        volunteer_prob=0.7,
        verbosity="normal",
        clarity="clear",
        language="en",
        seed=42,
    )

    agent_questions = [
        "Good morning! How are you feeling today?",
        "Have you had any chest pain or tightness?",
        "Are you feeling any breathlessness or shortness of breath?",
        "Did you take all your medications this morning?",
        "What was your weight this morning?",
        "Is there anything you'd like me to pass on to your doctor?",
    ]

    print("=== CareLoop Simulator Demo: Persona C, Day 12 ===")
    history = []
    for q in agent_questions:
        print(f"\nAgent: {q}")
        response = sim.respond(q, history)
        print(f"Patient: {response}")
        history.append({"role": "assistant", "content": q})
        history.append({"role": "user", "content": response})

    print("\n=== Planted Events on this day ===")
    for ev in day_data.get("planted_events", []):
        print(f"  [{ev['flag_level'].upper()}] {ev['description']}")


if __name__ == "__main__":
    main()
