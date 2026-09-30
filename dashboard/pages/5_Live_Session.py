"""
Page 5: Live Session — text-based check-in with CareLoop agent
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import io
import re
import time

import speech_recognition as sr
import streamlit as st
import yaml
from dotenv import load_dotenv
from gtts import gTTS

from careloop.conversation.session_manager import SessionManager
from careloop.providers.mock import MockLLMClient

load_dotenv()

st.set_page_config(page_title="Live Session — CareLoop", page_icon="💬", layout="wide")
st.title("💬 Live Check-in Session")
st.caption("Now with Live Voice! (Microphone support via Streamlit 1.40+)")

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

profiles_raw = load_yaml(os.path.join(BASE, "profiles.yaml"))
persona_options = {p["name"]: pid for pid, p in profiles_raw.items()}
selected_name = st.sidebar.selectbox("Select Patient", list(persona_options.keys()))
selected_pid = persona_options[selected_name]
profile = profiles_raw[selected_pid]

# Add optional API key input
st.sidebar.markdown("---")
default_key = os.environ.get("GOOGLE_API_KEY", "")
api_key = st.sidebar.text_input("Gemini API Key (for real LLM)", value=default_key, type="password", help="Leave empty to use Mock LLM")
voice_mode = st.sidebar.toggle("🎤 Enable Voice Mode", value=True)

if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key
    
# Session state management
if "session" not in st.session_state or st.sidebar.button("🔄 New Session"):
    from careloop.providers.mock import MockLLMClient
    providers_config = load_yaml(os.path.join(os.path.dirname(__file__), "..", "..", "config", "providers.yaml"))
    
    llms = {}
    if api_key:
        from careloop.providers.google_llm import GoogleLLMClient
        for role in ["conversation", "extractor", "verifier", "judge"]:
            cfg = providers_config.get(role, {})
            if cfg.get("provider") == "google" and cfg.get("model"):
                llms[role] = GoogleLLMClient(model_name=cfg["model"])
        st.toast("Using Gemini API from config", icon="🤖")
    else:
        llms = {"conversation": MockLLMClient(), "extractor": MockLLMClient()}
        st.toast("Using Mock LLM", icon="🤖")
        
    skip_verifier = st.sidebar.checkbox("Skip Verifier Layer", value=True)
    session = SessionManager(selected_pid, profile, llms, session_type="daily", skip_verifier=skip_verifier)
    greeting = session.start()
    st.session_state.session = session
    st.session_state.chat_history = [{"role": "assistant", "content": greeting}]
    st.session_state.flags = []
    st.session_state.latency_log = []
    st.session_state.audio_key = 0        # rotating key to reset mic widget
    st.session_state.last_audio_hash = None  # prevent re-processing same clip
    
    # Generate audio for the very first greeting if voice mode is on
    if voice_mode:
        tts = gTTS(text=greeting, lang='en', slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        st.session_state.latest_audio = fp.getvalue()
    else:
        st.session_state.latest_audio = None

# Ensure keys exist even across hot-reloads
if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None

session: SessionManager = st.session_state.session

# Sidebar metrics
st.sidebar.markdown("---")
st.sidebar.metric("Slot Coverage", f"{session.slot_store.coverage_rate():.0%}")
st.sidebar.metric("Questions Asked", session.questions_asked)
st.sidebar.metric("Flags Raised", len(session.flags_raised))

if api_key:
    from careloop.providers.google_llm import BudgetTracker
    st.sidebar.markdown("---")
    calls = BudgetTracker.get_calls_today()
    st.sidebar.metric("API Calls Today", calls)
    if calls > 15:
        st.sidebar.warning("⚠️ Approaching free tier limit (20).")

if st.session_state.get("fallback_mode"):
    st.warning("⚠️ **Running in Fallback Mode** (LLM quota reached). Some responses are pre-scripted.", icon="🛡️")

# Display chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Play the latest audio if available
if st.session_state.get("latest_audio") and voice_mode:
    st.audio(st.session_state.latest_audio, format="audio/mp3", autoplay=True)
    # Clear it so it doesn't replay on re-renders (like filter changes)
    st.session_state.latest_audio = None

# Input
if not session.session_closed:
    user_input = None
    
    if voice_mode:
        # Use rotating key so widget resets after each submission (prevents repeat)
        audio_val = st.audio_input(
            "🎤 Speak to CareLoop — record, then stop",
            key=f"audio_{st.session_state.audio_key}"
        )
        if audio_val is not None:
            # Hash the audio bytes to detect if this is the same clip
            import hashlib
            audio_hash = hashlib.md5(audio_val.getvalue()).hexdigest()
            if audio_hash != st.session_state.last_audio_hash:
                st.session_state.last_audio_hash = audio_hash
                with st.spinner("Transcribing your voice..."):
                    try:
                        r = sr.Recognizer()
                        audio_val.seek(0)
                        with sr.AudioFile(audio_val) as source:
                            audio_data = r.record(source)
                        user_input = r.recognize_google(audio_data)
                        if user_input:
                            st.info(f'You said: "{user_input}"')
                    except sr.UnknownValueError:
                        st.warning("Could not understand audio. Please try again.")
                    except Exception as e:
                        st.error(f"Transcription error: {e}")
    else:
        user_input = st.chat_input("Type your response here...")
        
    if user_input:
        # Increment audio_key to reset microphone widget for next turn
        st.session_state.audio_key += 1

        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("CareLoop is thinking..."):
            try:
                result = session.turn(user_input)
            except RuntimeError as e:
                err = str(e)
                if "quota" in err.lower() or "429" in err or "exhausted" in err.lower():
                    st.error(
                        "🚫 **API quota exhausted.** The free Gemini tier allows only 20 requests/day. "
                        "Please wait until tomorrow or use a paid API key at [ai.dev](https://ai.dev). "
                        "Your session data is preserved — you can still view the report."
                    )
                else:
                    st.error(f"⚠️ Error: {e}")
                st.stop()
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    import re
                    m = re.search(r"retry in (\d+)", str(e).lower())
                    wait = int(m.group(1)) if m else 60
                    st.warning(f"⏳ Rate limited. Auto-retrying in {wait}s... (free tier: 20 req/day)")
                    time.sleep(wait)
                    result = session.turn(user_input)
                else:
                    raise

        reply = result["reply"]
        
        # Generate TTS response
        if voice_mode:
            try:
                tts = gTTS(text=reply, lang='en', slow=False)
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                st.session_state.latest_audio = fp.getvalue()
            except Exception as e:
                st.error(f"TTS Error: {e}")

        st.session_state.chat_history.append({"role": "assistant", "content": reply})

        # Process flags
        for flag in result.get("new_flags", []):
            level = flag.get("level", "yellow")
            if level == "red":
                st.toast(f"🔴 RED FLAG: {flag['message']}", icon="🚨")
            else:
                st.toast(f"🟡 {flag['message']}")

        st.rerun()
else:
    # On session close, persist the real data globally for the Report page
    summary = session.close()
    st.session_state["completed_session"] = {
        "patient_id": selected_pid,
        "profile": profile,
        "slot_store": session.slot_store,
        "evidence_store": session.evidence_store,
        "flags_raised": session.flags_raised,
        "turns": session.turns,
        "summary": summary,
    }
    st.success("✅ Session closed. Your conversation has been saved.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 View Clinician Report", type="primary"):
            st.switch_page("pages/2_Report.py")
    with col2, st.expander("📊 Session Summary JSON"):
        st.json(summary)
