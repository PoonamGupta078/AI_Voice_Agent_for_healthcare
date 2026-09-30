import hashlib
import json
import logging
import os
import re
import time
from datetime import date
from typing import Any

import google.generativeai as genai

from careloop.providers.base import LLMClient, LLMErrorKind, LLMQuotaError, LLMResult

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".cache")
BUDGET_FILE = os.path.join(CACHE_DIR, "budget.json")

os.makedirs(CACHE_DIR, exist_ok=True)


class BudgetTracker:
    @staticmethod
    def get_calls_today() -> int:
        if not os.path.exists(BUDGET_FILE):
            return 0
        try:
            with open(BUDGET_FILE, "r") as f:
                data = json.load(f)
            if data.get("date") == str(date.today()):
                return data.get("calls", 0)
            return 0
        except Exception:
            return 0

    @staticmethod
    def increment():
        calls = BudgetTracker.get_calls_today()
        with open(BUDGET_FILE, "w") as f:
            json.dump({"date": str(date.today()), "calls": calls + 1}, f)

class GoogleLLMClient(LLMClient):
    def __init__(self, model_name: str = "gemini-2.5-flash-lite"):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.max_retries = 4
        self.base_delay = 5  # seconds

    def generate(
        self,
        messages: list[dict[str, str]],
        *,
        json_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 1000,
        stream: bool = False,
    ) -> LLMResult:

        system_parts = []
        history = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                if history and history[-1]["role"] == "user":
                    history[-1]["parts"][0] += "\n" + content
                else:
                    history.append({"role": "user", "parts": [content]})
            elif role in ("assistant", "model"):
                history.append({"role": "model", "parts": [content]})

        system_instruction = "\n\n".join(system_parts) if system_parts else None
        
        prompt_history = history[:-1] if len(history) > 1 else []
        prompt = history[-1]["parts"][0] if history else ""

        # ── Caching Logic ────────────────────────────────────────────────────────
        cache_key_str = f"{self.model_name}_{temperature}_{prompt}_{json.dumps(prompt_history)}_{system_instruction}_{json_schema}"
        cache_hash = hashlib.md5(cache_key_str.encode('utf-8')).hexdigest()
        cache_file = os.path.join(CACHE_DIR, f"{cache_hash}.json")
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cached_data = json.load(f)
                usage = cached_data.get("usage", {})
                if json_schema:
                    return LLMResult(json_data=cached_data.get("json_data"), usage=usage, latency_ms=0)
                return LLMResult(text=cached_data.get("text"), usage=usage, latency_ms=0)
            except Exception:
                pass

        model = genai.GenerativeModel(
            self.model_name,
            system_instruction=system_instruction,
        )

        gen_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if json_schema else "text/plain",
        )

        last_exc = None
        for attempt in range(self.max_retries):
            try:
                chat = model.start_chat(history=prompt_history)
                response = chat.send_message(prompt, generation_config=gen_config)
                text = response.text or ""
                usage = {}
                try:
                    um = response.usage_metadata
                    usage = {
                        "prompt_tokens": getattr(um, "prompt_token_count", 0),
                        "completion_tokens": getattr(um, "candidates_token_count", 0),
                        "total_tokens": getattr(um, "total_token_count", 0),
                    }
                except Exception:
                    pass

                # Cache result and increment budget
                BudgetTracker.increment()
                
                result_data = {"usage": usage}
                if json_schema:
                    try:
                        data = json.loads(text)
                        result_data["json_data"] = data
                        with open(cache_file, "w") as f:
                            json.dump(result_data, f)
                        return LLMResult(json_data=data, usage=usage, latency_ms=0)
                    except Exception:
                        return LLMResult(json_data={}, usage=usage, latency_ms=0)

                result_data["text"] = text
                with open(cache_file, "w") as f:
                    json.dump(result_data, f)
                return LLMResult(text=text, usage=usage, latency_ms=0)

            except Exception as e:
                last_exc = e
                err_str = str(e).lower()

                # Parse retry_delay
                retry_after = self.base_delay * (2 ** attempt)
                m = re.search(r"retry in (\d+)|retry_delay.*seconds:\s*(\d+)", err_str)
                if m:
                    retry_after = int(m.group(1) or m.group(2)) + 2

                # Determine error kind
                kind = LLMErrorKind.unknown
                if "429" in err_str or "exhausted" in err_str or "quota" in err_str:
                    if "per day" in err_str or "daily" in err_str or "generate_content_free_tier_requests" in err_str:
                        kind = LLMErrorKind.daily_quota
                    else:
                        kind = LLMErrorKind.per_minute_limit
                elif "503" in err_str or "unavailable" in err_str:
                    kind = LLMErrorKind.server_error

                # Daily quota: DO NOT RETRY, raise immediately
                if kind == LLMErrorKind.daily_quota:
                    raise LLMQuotaError(kind, f"Daily quota exhausted for {self.model_name}.", retry_after)

                # Transient errors: retry with backoff
                if kind in (LLMErrorKind.per_minute_limit, LLMErrorKind.server_error):
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Attempt {attempt+1} failed ({kind.value}). Retrying in {retry_after}s...")
                        time.sleep(retry_after)
                        continue

                # Unhandled or exhausted retries
                raise LLMQuotaError(kind, f"Failed after {attempt+1} attempts: {err_str}", retry_after)

        raise LLMQuotaError(LLMErrorKind.unknown, f"Max retries exceeded. Last error: {last_exc}")
