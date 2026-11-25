"""Run with: python -m app.voice.worker dev (from backend)."""
import asyncio
import sys
from datetime import datetime, timezone
from livekit import api
from livekit.agents import Agent, AgentServer, AgentSession, cli
from livekit.plugins import deepgram, elevenlabs, google, silero

from app.agents.prompts import instructions
from app.agents.knowledge_tools import search_properties, get_property_details, search_company_knowledge
from app.agents.intelligence_tools import tools_for_session
from app.agents.automation_tools import tools_for_session as automation_tools_for_session
from app.core.config import Settings
from app.database import build_engine, session_factory
from app.models.voice_session import VoiceSession
from app.rag.embeddings import selected
from app.summaries.service import finalise_voice

settings = Settings()


class SalesAgent(Agent):
    def __init__(self, language: str, session_id: str | None = None) -> None:
        tools = [search_properties, get_property_details, search_company_knowledge]
        if session_id: tools += tools_for_session(session_id) + automation_tools_for_session(session_id)
        super().__init__(instructions=instructions(language), tools=tools)


server = AgentServer()


def update_session(session_id: str, status: str, reason: str | None = None) -> None:
    engine = build_engine(settings)
    try:
        with session_factory(engine)() as db:
            record = db.get(VoiceSession, session_id)
            if not record or record.status in ("COMPLETED", "FAILED"):
                return
            now = datetime.now(timezone.utc)
            record.status = status
            if status == "ACTIVE":
                record.started_at = now
            elif status in ("COMPLETED", "FAILED"):
                record.ended_at = now
                record.failure_reason = reason
                if record.started_at:
                    record.duration_seconds = max(0, int((now - record.started_at.replace(tzinfo=timezone.utc)).total_seconds()))
            db.commit()
    finally:
        engine.dispose()


def summarise_session(session_id: str, transient_text: str | None = None) -> None:
    engine = build_engine(settings)
    try:
        with session_factory(engine)() as db:
            finalise_voice(db, session_id, settings, transient_text)
    finally:
        engine.dispose()


async def limit_session(room: str) -> None:
    await asyncio.sleep(settings.voice_max_session_seconds)
    async with api.LiveKitAPI(url=settings.livekit_url, api_key=settings.livekit_api_key.get_secret_value(),
                              api_secret=settings.livekit_api_secret.get_secret_value()) as livekit:
        await livekit.room.delete_room(api.DeleteRoomRequest(room=room))


async def bound_context(session: AgentSession) -> None:
    """Keep recent call turns while preserving the first system instruction."""
    while True:
        await asyncio.sleep(10)
        session.history.truncate(max_items=30)


@server.rtc_session(agent_name=settings.livekit_agent_name)
async def voice_session(ctx):
    missing = [name for name, value in {
        "LIVEKIT_URL": settings.livekit_url,
        "LIVEKIT_API_KEY": settings.livekit_api_key.get_secret_value(),
        "LIVEKIT_API_SECRET": settings.livekit_api_secret.get_secret_value(),
        "DEEPGRAM_API_KEY": settings.deepgram_api_key.get_secret_value(),
        "GOOGLE_API_KEY": settings.google_api_key.get_secret_value(),
        "TTS_API_KEY": settings.tts_api_key.get_secret_value(),
        "TTS_MODEL": settings.tts_model,
        "TTS_VOICE_ID": settings.tts_voice_id,
    }.items() if not value]
    if missing or settings.tts_provider != "elevenlabs":
        raise RuntimeError("Voice worker configuration incomplete: " + ", ".join(missing))
    parts = ctx.job.metadata.split(":") if ctx.job.metadata else []
    session_id = parts[0] if len(parts) == 2 else None
    language = parts[1] if len(parts) == 2 and parts[1] in ("en", "hi", "hinglish") else settings.voice_default_language
    session = AgentSession(
        stt=deepgram.STT(model=settings.deepgram_stt_model or "nova-3", language=settings.deepgram_stt_language,
                         api_key=settings.deepgram_api_key.get_secret_value()),
        llm=google.LLM(model=settings.gemini_model or "gemini-2.5-flash",
                       api_key=settings.google_api_key.get_secret_value()),
        tts=elevenlabs.TTS(model=settings.tts_model, voice_id=settings.tts_voice_id,
                            api_key=settings.tts_api_key.get_secret_value()),
        vad=silero.VAD.load(),
    )
    timer = asyncio.create_task(limit_session(ctx.room.name))
    context_timer = asyncio.create_task(bound_context(session))
    disconnected = asyncio.Event()
    ctx.room.on("disconnected", lambda: disconnected.set())
    try:
        if settings.embedding_provider == "local":
            await asyncio.wait_for(asyncio.to_thread(lambda: selected(settings).embed(["property search warmup"], "RETRIEVAL_QUERY")), 90)
        await session.start(room=ctx.room, agent=SalesAgent(language, session_id))
        if session_id:
            await asyncio.to_thread(update_session, session_id, "ACTIVE")
        await session.generate_reply(instructions="Greet the customer as an AI assistant, then ask what kind of property they seek.")
        await disconnected.wait()
        if session_id:
            await asyncio.to_thread(update_session, session_id, "COMPLETED")
            transient = None
            if settings.voice_transcript_retention_enabled:
                parts = [item.text_content for item in session.history.items
                         if item.type == "message" and item.role == "user" and item.text_content]
                transient = "\n".join(parts[-8:])[:4000] or None
            try:
                await asyncio.wait_for(asyncio.to_thread(summarise_session, session_id, transient), 20)
            except Exception:
                # Completion metadata remains durable; a failed summary is retried via API.
                pass
    except Exception:
        if session_id:
            await asyncio.to_thread(update_session, session_id, "FAILED", "Voice worker stopped unexpectedly")
        raise
    finally:
        timer.cancel()
        context_timer.cancel()


if __name__ == "__main__":
    if any(command in sys.argv for command in ("dev", "start")):
        required = {
            "LIVEKIT_URL": settings.livekit_url,
            "LIVEKIT_API_KEY": settings.livekit_api_key.get_secret_value(),
            "LIVEKIT_API_SECRET": settings.livekit_api_secret.get_secret_value(),
            "DEEPGRAM_API_KEY": settings.deepgram_api_key.get_secret_value(),
            "GOOGLE_API_KEY": settings.google_api_key.get_secret_value(),
            "TTS_API_KEY": settings.tts_api_key.get_secret_value(),
            "TTS_MODEL": settings.tts_model,
            "TTS_VOICE_ID": settings.tts_voice_id,
        }
        missing = [name for name, value in required.items() if not value]
        if settings.tts_provider != "elevenlabs":
            missing.append("TTS_PROVIDER=elevenlabs")
        if missing:
            raise SystemExit("Voice worker configuration incomplete: " + ", ".join(missing))
    cli.run_app(server)
