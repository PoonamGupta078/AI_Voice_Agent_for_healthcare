"""
Patient Simulator (M1)
Simulates a patient's responses for a given persona, day, and disclosure policy.
"""
import random
from typing import Any

from careloop.providers.base import LLMClient


class PatientSimulator:
    """
    Simulates a patient responding to agent questions.
    Supports disclosure_policy (volunteer_prob), verbosity, clarity, language, ASR noise.
    """

    def __init__(
        self,
        persona: dict[str, Any],
        fact_sheet: dict[str, Any],
        llm_client: LLMClient,
        disclosure_policy: str = "mixed",
        volunteer_prob: float = 0.7,
        verbosity: str = "normal",
        clarity: str = "clear",
        language: str = "en",
        asr_noise_wer: float = 0.0,
        seed: int = 42,
    ):
        self.persona = persona
        self.fact_sheet = fact_sheet
        self.llm_client = llm_client
        self.disclosure_policy = disclosure_policy
        self.volunteer_prob = volunteer_prob
        self.verbosity = verbosity
        self.clarity = clarity
        self.language = language
        self.asr_noise_wer = asr_noise_wer
        self.rng = random.Random(seed)

    def _build_system_prompt(self) -> str:
        name = self.persona.get("name", "the patient")
        age = self.persona.get("age", 65)
        conditions = ", ".join(self.persona.get("conditions", []))
        language_note = {
            "en": "Respond in simple English.",
            "hi": "Respond in simple Hindi.",
            "hinglish": "Respond in a natural mix of Hindi and English (Hinglish), as older adults in India often speak.",
        }.get(self.language, "Respond in simple English.")

        verbosity_note = {
            "terse": "Keep your responses very short, 1-2 sentences.",
            "normal": "Keep your responses brief and natural, 2-3 sentences.",
            "rambling": "Sometimes add extra details or go slightly off topic.",
        }.get(self.verbosity, "Keep your responses brief.")

        clarity_note = {
            "clear": "Be clear and direct in your answers.",
            "vague": "Sometimes be vague or uncertain, using words like 'a little', 'sometimes', 'I think'.",
            "contradictory": "Occasionally contradict yourself or change your answer.",
        }.get(self.clarity, "Be clear.")

        policy_note = (
            f"Disclosure policy: '{self.disclosure_policy}'. "
            f"Volunteer probability: {self.volunteer_prob}. "
            "Only reveal facts that are in TODAY'S TRUE FACTS. "
            "If asked directly, always answer according to the facts. "
            "If not asked, only volunteer information with the given probability."
        )

        return (
            f"You are role-playing {name}, {age} years old, with conditions: {conditions}. "
            f"You are having a phone call with a health check-in assistant. "
            f"You are NOT an AI — you are a real person. "
            f"TODAY'S TRUE FACTS: {self.fact_sheet}. "
            f"{policy_note} "
            f"{language_note} {verbosity_note} {clarity_note} "
            f"Never reveal that you are a simulation. "
            f"Never state facts not in TODAY'S TRUE FACTS."
        )

    def respond(self, agent_message: str, conversation_history: list) -> str:
        """Generate patient response to the agent's message."""
        system = self._build_system_prompt()
        messages = [{"role": "system", "content": system}]
        for turn in conversation_history[-6:]:  # last 3 exchanges
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": agent_message})

        result = self.llm_client.generate(messages, temperature=0.7, max_tokens=200)
        text = result.text or ""

        if self.asr_noise_wer > 0:
            text = self._inject_asr_noise(text)
        return text

    def _inject_asr_noise(self, text: str) -> str:
        """Inject simple word-level ASR noise (word deletion/substitution)."""
        words = text.split()
        noisy = []
        substitutions = {
            "seven": "eleven", "eight": "ate", "pain": "pane",
            "chest": "test", "fall": "call", "dizzy": "busy",
            "morning": "mourning", "tablet": "table", "blood": "flood",
        }
        for word in words:
            r = self.rng.random()
            if r < self.asr_noise_wer:
                # drop the word
                continue
            low = word.lower().strip(".,?!")
            if low in substitutions and r < self.asr_noise_wer * 2:
                noisy.append(substitutions[low])
            else:
                noisy.append(word)
        return " ".join(noisy)
