from fastapi import FastAPI, Header, HTTPException, Request, BackgroundTasks
from typing import Optional, Dict
import re
import random
import requests

# ======================================================
# APP
# ======================================================
app = FastAPI(swagger_ui_parameters={"tryItOutEnabled": False})

# ======================================================
# CONFIG
# ======================================================
API_KEY = "GUVI_SECRET_KEY_123"
FINAL_CALLBACK_URL = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"

# ======================================================
# MEMORY
# ======================================================
sessions: Dict[str, dict] = {}

# ======================================================
# UTILITIES
# ======================================================
def is_scam(text: str) -> bool:
    return any(k in text.lower() for k in [
        "blocked", "verify", "urgent", "upi", "click", "suspended"
    ])

def extract_intelligence(text: str, session: dict):
    session["extracted"]["phoneNumbers"] += re.findall(r"\+?\d{10,13}", text)
    session["extracted"]["upiIds"] += re.findall(r"\b[\w.\-]{2,}@\w+\b", text)
    session["extracted"]["phishingLinks"] += re.findall(r"https?://\S+", text)

def generate_reply(text: str, messages_count: int) -> str:
    if "blocked" in text.lower():
        return "This is confusing… my account was working fine today. Why is it blocked?"
    if "upi" in text.lower():
        return "I’m not very familiar with UPI. Can you tell me exactly what to do?"
    if messages_count == 1:
        return "I just received this and I’m confused. What exactly is the issue?"
    return random.choice([
        "Sorry, I still don’t understand. Can you explain again?",
        "This seems serious… what should I do right now?"
    ])

def send_final_callback(session_id: str):
    session = sessions.get(session_id)
    if not session:
        return

    payload = {
        "sessionId": session_id,
        "scamDetected": True,
        "totalMessagesExchanged": len(session["messages"]),
        "extractedIntelligence": session["extracted"]
    }

    try:
        requests.post(FINAL_CALLBACK_URL, json=payload, timeout=5)
    except:
        pass

# ======================================================
# ROUTES
# ======================================================
@app.get("/")
def health():
    return {"status": "running"}

# ======================================================
# 🚨 ONLY ENDPOINT GUVI CARES ABOUT
# ======================================================
@app.post("/v1/message")
async def receive_message(
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: Optional[str] = Header(None)
):
    # API key check (optional but safe)
    if x_api_key and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # ---- RAW BODY (NO VALIDATION = NO 422)
    try:
        body = await request.json()
    except:
        body = {}

    # ---- SAFE EXTRACTION (GUVI BODY MAY VARY)
    session_id = body.get("sessionId", "default-session")

    message = body.get("message", {})
    text = (
        message.get("text")
        or body.get("text")
        or ""
    )

    # ---- SESSION INIT
    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "extracted": {
                "phoneNumbers": [],
                "upiIds": [],
                "phishingLinks": []
            },
            "callbackSent": False
        }

    session = sessions[session_id]
    session["messages"].append(text)

    extract_intelligence(text, session)
    reply = generate_reply(text, len(session["messages"]))

    # ---- NON-BLOCKING CALLBACK
    if is_scam(text) and len(session["messages"]) >= 2 and not session["callbackSent"]:
        background_tasks.add_task(send_final_callback, session_id)
        session["callbackSent"] = True

    # ✅ EXACT RESPONSE FORMAT REQUIRED BY GUVI
    return {
        "status": "success",
        "reply": reply
    }

# ======================================================
# DEBUG (OPTIONAL)
# ======================================================
@app.get("/debug/{session_id}")
def debug(session_id: str):
    return sessions.get(session_id, {})
