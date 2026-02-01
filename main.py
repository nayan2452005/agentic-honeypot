from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import re

app = FastAPI()

# ---------------- Models ----------------
class DetectRequest(BaseModel):
    text: str

# ---------------- Scam Detection Logic ----------------
SCAM_KEYWORDS = [
    "blocked", "verify", "urgent", "immediately", "upi",
    "click", "refund", "prize", "lottery", "suspended",
    "account freeze", "limited time"
]

def analyze_message(text: str):
    text_lower = text.lower()
    reasons = []

    # Keyword detection
    for word in SCAM_KEYWORDS:
        if word in text_lower:
            reasons.append(f"Suspicious keyword: '{word}'")

    # URL detection
    if re.search(r'https?://\S+', text):
        reasons.append("Suspicious link detected")

    # Phone number detection
    if re.search(r'\+?\d{10,13}', text):
        reasons.append("Phone number detected")

    # UPI detection
    if re.search(r'\b[\w.\-]{2,}@\w+\b', text):
        reasons.append("UPI ID detected")

    is_scam = len(reasons) >= 2

    risk_level = "LOW"
    if len(reasons) >= 4:
        risk_level = "HIGH"
    elif len(reasons) >= 2:
        risk_level = "MEDIUM"

    return is_scam, risk_level, reasons

# ---------------- API ----------------
@app.get("/")
def home():
    return {"message": "Scam Detection API is running"}

@app.post("/detect")
def detect_scam(req: DetectRequest):
    is_scam, risk, reasons = analyze_message(req.text)

    return {
        "isScam": is_scam,
        "riskLevel": risk,
        "reasons": reasons
    }

