import os
import sys
import io
import hashlib
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import speech_recognition as sr
import streamlit as st
import yaml
from dotenv import load_dotenv
from gtts import gTTS

from careloop.conversation.session_manager import SessionManager
from careloop.providers.mock import MockLLMClient

load_dotenv()

st.set_page_config(page_title="CareLoop — Live Check-in", page_icon="💬", layout="wide")
st.title("💬 CareLoop Health Check-in")
st.caption("A compassionate voice-guided wellness check-in for your patient.")

BASE = os.path.join(os.path.dirname(__file__), "..", "..", "eval", "personas")

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

profiles_raw = load_yaml(os.path.join(BASE, "profiles.yaml"))
persona_options = {p["name"]: pid for pid, p in profiles_raw.items()}

st.sidebar.markdown("### 👤 Patient")
selected_name = st.sidebar.selectbox("Select Patient", list(persona_options.keys()))
selected_pid = persona_options[selected_name]
profile = profiles_raw[selected_pid]

st.sidebar.markdown("---")
default_key = os.environ.get("GOOGLE_API_KEY", "")
api_key = st.sidebar.text_input("Gemini API Key (for real LLM)", value=default_key, type="password", help="Leave empty to use offline Mock mode")
voice_mode = st.sidebar.toggle("🎤 Enable Voice Mode", value=True)
skip_verifier = st.sidebar.checkbox("Skip Verifier (saves quota)", value=True)

if api_key:
    os.environ["GOOGLE_API_KEY"] = api_key

new_session_clicked = st.sidebar.button("🔄 Start New Session")

if "session" not in st.session_state or new_session_clicked:
    providers_config = load_yaml(os.path.join(os.path.dirname(__file__), "..", "..", "config", "providers.yaml"))
    llms = {}
    if api_key:
        from careloop.providers.google_llm import GoogleLLMClient
        for role in ["conversation", "extractor", "verifier", "judge"]:
            cfg = providers_config.get(role, {})
            if cfg.get("provider") == "google" and cfg.get("model"):
                llms[role] = GoogleLLMClient(model_name=cfg["model"])
        st.toast("Connected to Gemini AI", icon="🤖")
    else:
        llms = {"conversation": MockLLMClient(), "extractor": MockLLMClient()}
        st.toast("Running in offline mode", icon="💡")

    session = SessionManager(selected_pid, profile, llms, session_type="daily", skip_verifier=skip_verifier)
    greeting = session.start()

    st.session_state.session = session
    st.session_state.chat_history = [{"role": "assistant", "content": greeting}]
    st.session_state.audio_key = 0
    st.session_state.last_audio_hash = None
    st.session_state.fallback_mode = False

    if voice_mode:
        try:
            tts = gTTS(text=greeting, lang="en", slow=False)
            fp = io.BytesIO()
            tts.write_to_fp(fp)
            st.session_state.latest_audio = fp.getvalue()
        except Exception:
            st.session_state.latest_audio = None
    else:
        st.session_state.latest_audio = None

if "audio_key" not in st.session_state:
    st.session_state.audio_key = 0
if "last_audio_hash" not in st.session_state:
    st.session_state.last_audio_hash = None

session: SessionManager = st.session_state.session

st.sidebar.markdown("---")
st.sidebar.markdown("### 📊 Session Progress")
coverage = session.slot_store.coverage_rate()
st.sidebar.progress(coverage, text=f"Coverage: {coverage:.0%}")
st.sidebar.metric("Questions Asked", session.questions_asked)

flags = session.flags_raised
red_flags = [f for f in flags if f.level == "red"]
yellow_flags = [f for f in flags if f.level == "yellow"]
if red_flags:
    st.sidebar.error(f"🔴 {len(red_flags)} Red Flag(s) Raised")
if yellow_flags:
    st.sidebar.warning(f"🟡 {len(yellow_flags)} Yellow Flag(s)")

if api_key:
    from careloop.providers.google_llm import BudgetTracker
    calls = BudgetTracker.get_calls_today()
    st.sidebar.markdown("---")
    st.sidebar.metric("API Calls Today", calls, help="Free tier limit: 20 calls/day")
    if calls > 15:
        st.sidebar.warning("⚠️ Approaching daily quota limit.")

if st.session_state.get("fallback_mode"):
    st.info("ℹ️ Running in assisted mode — responses are being guided by built-in templates while the AI recovers from a rate limit. Your answers are still being recorded accurately.", icon="🛡️")

for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state.get("latest_audio") and voice_mode:
    st.audio(st.session_state.latest_audio, format="audio/mp3", autoplay=True)
    st.session_state.latest_audio = None

if not session.session_closed:
    user_input = None

    if voice_mode:
        audio_val = st.audio_input(
            "🎤 Speak your response — press the mic to record, then stop",
            key=f"audio_{st.session_state.audio_key}"
        )
        if audio_val is not None:
            audio_hash = hashlib.md5(audio_val.getvalue()).hexdigest()
            if audio_hash != st.session_state.last_audio_hash:
                st.session_state.last_audio_hash = audio_hash
                with st.spinner("Listening..."):
                    try:
                        recognizer = sr.Recognizer()
                        audio_val.seek(0)
                        with sr.AudioFile(audio_val) as source:
                            audio_data = recognizer.record(source)
                        user_input = recognizer.recognize_google(audio_data)
                        if user_input:
                            st.success(f'You said: *"{user_input}"*')
                    except sr.UnknownValueError:
                        st.warning("I could not make out what you said. Please try speaking again, slowly and clearly.")
                    except Exception as e:
                        st.error(f"Could not process audio: {e}")
    else:
        user_input = st.chat_input("Type your response here...")

    if user_input:
        st.session_state.audio_key += 1
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        with st.spinner("CareLoop is preparing a response..."):
            try:
                result = session.turn(user_input)
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                st.stop()

        reply = result["reply"]

        if voice_mode:
            try:
                tts = gTTS(text=reply, lang="en", slow=False)
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                st.session_state.latest_audio = fp.getvalue()
            except Exception:
                pass

        st.session_state.chat_history.append({"role": "assistant", "content": reply})

        for flag in result.get("new_flags", []):
            level = flag.get("level", "yellow")
            message = flag.get("message", "A health concern was noted.")
            if level == "red":
                st.toast(f"🔴 Urgent: {message}", icon="🚨")
            else:
                st.toast(f"🟡 Note: {message}")

        st.rerun()

else:
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
    st.success("✅ Check-in complete. Thank you for taking care of your health today.")
    st.info("Your responses have been saved and a full clinical report has been generated for your care team.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📋 View Clinician Report", type="primary", use_container_width=True):
            st.switch_page("pages/2_Report.py")
    with col2:
        if st.button("📈 View Health Trends", use_container_width=True):
            st.switch_page("pages/3_Trends.py")
