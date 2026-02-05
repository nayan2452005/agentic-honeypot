from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict
import re
import random
import requests

# ======================================================
# APP CONFIG (Swagger enabled, Try-it-out disabled)
# ======================================================
app = FastAPI(
    swagger_ui_parameters={
        "tryItOutEnabled": False
    }
)

# ======================================================
# CONFIG
# ======================================================
API_KEY = "GUVI_SECRET_KEY_123"
FINAL_CALLBACK_URL = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"

# ======================================================
# IN-MEMORY STORAGE
# ======================================================
sessions: Dict[str, dict] = {}

# ======================================================
# MODELS (GUVI FLEXIBLE + SAFE)
# ======================================================
class Message(BaseModel):
    sender: Optional[str] = ""
    text: str
    timestamp: Optional[str] = ""

    class Config:
        extra = "allow"


class RequestBody(BaseModel):
    sessionId: str
    message: Message
    conversationHistory: Optional[List[Message]] = []
    metadata: Optional[dict] = {}

    class Config:
        extra = "allow"


# Simple GUVI tester model (fallback / webhook-style)
class GuviRequest(BaseModel):
    message: str

    class Config:
        extra = "allow"

# ======================================================
# SCAM DETECTION
# ======================================================
def is_scam(text: str) -> bool:
    keywords = ["blocked", "verify", "urgent", "upi", "click", "suspended"]
    return any(k in text.lower() for k in keywords)

# ======================================================
# INTELLIGENCE EXTRACTION
# ======================================================
def extract_intelligence(text: str, session: dict):
    session["extracted"]["phoneNumbers"].extend(
        re.findall(r'\+?\d{10,13}', text)
    )
    session["extracted"]["upiIds"].extend(
        re.findall(r'\b[\w.\-]{2,}@\w+\b', text)
    )
    session["extracted"]["phishingLinks"].extend(
        re.findall(r'https?://\S+', text)
    )

    for k in ["urgent", "verify", "blocked", "suspended"]:
        if k in text.lower():
            session["extracted"]["suspiciousKeywords"].append(k)

# ======================================================
# HUMAN-LIKE AGENT RESPONSE
# ======================================================
def generate_agent_reply(text: str, session: dict) -> str:
    text_lower = text.lower()
    messages = session["messages"]

    fillers = ["umm", "uh", "hmm", "wait", "sorry", "okay"]
    filler = random.choice(fillers)

    if "upi" in text_lower:
        return f"{filler} I actually have two UPI IDs. Which one should I use?"

    if "http" in text_lower or "click" in text_lower:
        return f"{filler} this link isn’t opening properly. Is there another way?"

    if "blocked" in text_lower or "suspended" in text_lower:
        return "This is really sudden… my account was working fine today. Why is it blocked?"

    if "call" in text_lower or "number" in text_lower:
        return "I’m at work right now and can’t take calls. Can you explain it here?"

    if len(messages) == 1:
        return "I just got this message and I’m honestly confused… what exactly is the issue?"

    return random.choice([
        "Sorry, I’m still not fully getting this. Can you explain again?",
        "This is a bit confusing for me… what should I do first?",
        "I don’t usually handle these things. Can you guide me step by step?"
    ])

# ======================================================
# FINAL CALLBACK TO GUVI
# ======================================================
def send_final_callback(session_id: str):
    session = sessions.get(session_id)
    if not session:
        return

    payload = {
        "sessionId": session_id,
        "scamDetected": True,
        "totalMessagesExchanged": len(session["messages"]),
        "extractedIntelligence": session["extracted"],
        "agentNotes": "Human-like confusion, clarification, and adaptive probing used"
    }

    try:
        requests.post(FINAL_CALLBACK_URL, json=payload, timeout=5)
    except Exception:
        pass

# ======================================================
# ROUTES
# ======================================================

@app.get("/")
def health():
    return {"status": "Agentic HoneyPot API running"}

# ------------------------------------------------------
# MAIN GUVI HONEYPOT ENDPOINT
# ------------------------------------------------------
@app.post("/v1/message")
def receive_message(
    body: RequestBody,
    x_api_key: Optional[str] = Header(None)
):
    if x_api_key is not None and x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    session_id = body.sessionId
    text = body.message.text

    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "extracted": {
                "bankAccounts": [],
                "upiIds": [],
                "phishingLinks": [],
                "phoneNumbers": [],
                "suspiciousKeywords": []
            },
            "callbackSent": False
        }

    session = sessions[session_id]
    session["messages"].append(text)

    extract_intelligence(text, session)
    scam = is_scam(text)
    reply = generate_agent_reply(text, session)

    if scam and len(session["messages"]) >= 2 and not session["callbackSent"]:
        send_final_callback(session_id)
        session["callbackSent"] = True

    if not scam:
        return {
            "status": "ok",
            "scamDetected": False
        }

    return {
        "status": "success",
        "scamDetected": True,
        "reply": reply
    }

# ------------------------------------------------------
# SIMPLE GUVI TESTER WEBHOOK (NO 422 GUARANTEED)
# ------------------------------------------------------
@app.post("/webhook")
async def webhook(
    data: GuviRequest,
    x_api_key: Optional[str] = Header(None)
):
    if x_api_key is not None and x_api_key != API_KEY:
        return {"status": "error", "reason": "Invalid API key"}

    return {
        "status": "success",
        "received_message": data.message
    }

# ------------------------------------------------------
# DEBUG ENDPOINT
# ------------------------------------------------------
@app.get("/debug/session/{session_id}")
def debug_session(session_id: str):
    return sessions.get(session_id, {})
