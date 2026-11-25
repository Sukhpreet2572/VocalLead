"""Optional Gemini structured text intelligence. No provider request without credentials."""
from typing import Literal
from pydantic import BaseModel
from google import genai
from google.genai import types
from app.core.config import Settings
from app.intelligence.schemas import ProfileUpdate

class SentimentResult(BaseModel):
    sentiment: Literal["POSITIVE", "NEUTRAL", "NEGATIVE", "MIXED", "UNKNOWN"]
    business_signal: Literal["INTERESTED", "CONFUSED", "PRICE_CONCERN", "FRUSTRATED", "NOT_INTERESTED", "READY_TO_PROCEED", "UNSPECIFIED"]
    evidence: str

def extract_with_gemini(message: str, settings: Settings) -> ProfileUpdate:
    key = settings.google_api_key.get_secret_value()
    if not key: raise RuntimeError("Gemini credentials unavailable")
    with genai.Client(api_key=key) as client:
        response = client.models.generate_content(model=settings.gemini_model or "gemini-2.5-flash",
            contents="Extract only facts explicitly stated in this final customer turn. Omit unknown fields. Budget INR integer. Do not infer purchase intent from casual browsing.\n" + message,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=ProfileUpdate,
                temperature=0))
    return ProfileUpdate.model_validate_json(response.text)

def sentiment_with_gemini(message: str, settings: Settings) -> SentimentResult:
    key = settings.google_api_key.get_secret_value()
    if not key: raise RuntimeError("Gemini credentials unavailable")
    with genai.Client(api_key=key) as client:
        response = client.models.generate_content(model=settings.gemini_model or "gemini-2.5-flash",
            contents="Classify text sentiment separately from business intent. Use UNKNOWN and UNSPECIFIED when evidence is insufficient. Cite a short evidence phrase.\n" + message,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=SentimentResult,
                temperature=0))
    return SentimentResult.model_validate_json(response.text)
