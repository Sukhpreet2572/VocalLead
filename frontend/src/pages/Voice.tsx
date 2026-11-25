import { useEffect, useRef, useState } from "react";
import {
  LiveKitRoom,
  RoomAudioRenderer,
  useVoiceAssistant,
  useTranscriptions,
  BarVisualizer,
  useRoomContext,
} from "@livekit/components-react";
import { RoomEvent, type Room } from "livekit-client";
import { API_BASE_URL } from "../services/api";
import "./voice.css";

type Availability = {
  available: boolean;
  missing: string[];
  transcript_retention_enabled: boolean;
  max_session_seconds: number;
};
type Created = {
  session_id: string;
  livekit_url: string;
  room_name: string;
  participant_token: string;
  status: string;
};
type Event = { id: number; text: string; at: Date };

function ownerKey(): string {
  const existing = sessionStorage.getItem("vocalead_voice_owner");
  if (existing) return existing;
  const fresh = crypto.randomUUID() + crypto.randomUUID();
  sessionStorage.setItem("vocalead_voice_owner", fresh);
  return fresh;
}

async function apiCall<T>(
  path: string,
  method = "GET",
  body?: object,
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/voice${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-Voice-Owner": ownerKey(),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(
      error?.error?.message || `Voice API failed (HTTP ${response.status})`,
    );
  }
  return response.json() as Promise<T>;
}

function CallRoom({
  session,
  onEnded,
  addEvent,
}: {
  session: Created;
  onEnded: () => void;
  addEvent: (text: string) => void;
}) {
  const [muted, setMuted] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState("");
  const [ending, setEnding] = useState(false);
  useEffect(() => {
    const timer = window.setInterval(
      () => setSeconds((value) => value + 1),
      1000,
    );
    return () => window.clearInterval(timer);
  }, []);
  return (
    <LiveKitRoom
      serverUrl={session.livekit_url}
      token={session.participant_token}
      connect
      audio
      video={false}
      onConnected={() => addEvent("Browser connected to room")}
      onError={(caught) => {
        setError(caught.message);
        addEvent("Room connection failed");
      }}
    >
      <RoomAudioRenderer />
      <ConnectedControls
        session={session}
        addEvent={addEvent}
        onEnded={onEnded}
        muted={muted}
        setMuted={setMuted}
        ending={ending}
        setEnding={setEnding}
        setError={setError}
        seconds={seconds}
        error={error}
      />
    </LiveKitRoom>
  );
}

function ConnectedControls({
  session,
  onEnded,
  addEvent,
  muted,
  setMuted,
  ending,
  setEnding,
  setError,
  seconds,
  error,
}: {
  session: Created;
  onEnded: () => void;
  addEvent: (text: string) => void;
  muted: boolean;
  setMuted: (value: boolean) => void;
  ending: boolean;
  setEnding: (value: boolean) => void;
  setError: (value: string) => void;
  seconds: number;
  error: string;
}) {
  const room: Room = useRoomContext();
  useEffect(() => {
    const disconnected = () => {
      addEvent("LiveKit room disconnected");
      void apiCall(`/sessions/${session.session_id}/end`, "POST").catch(() => {
        addEvent("Server cleanup needs retry");
      });
      onEnded();
    };
    const joined = () => addEvent("Participant joined the room");
    room
      .on(RoomEvent.Disconnected, disconnected)
      .on(RoomEvent.ParticipantConnected, joined);
    return () => {
      room
        .off(RoomEvent.Disconnected, disconnected)
        .off(RoomEvent.ParticipantConnected, joined);
    };
  }, [room, addEvent, onEnded, session.session_id]);
  const end = async () => {
    if (ending) return;
    setEnding(true);
    try {
      await apiCall(`/sessions/${session.session_id}/end`, "POST");
      await room.disconnect();
      addEvent("Call ended");
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Could not end room on server",
      );
    } finally {
      onEnded();
    }
  };
  const toggleMute = async () => {
    try {
      await room.localParticipant.setMicrophoneEnabled(muted);
      setMuted(!muted);
    } catch {
      setError(
        "Microphone could not be changed. Check browser permission and device.",
      );
    }
  };
  return (
    <>
      <div className="voice-connected">
        <div className="voice-call-heading">
          <strong>Live conversation</strong>
          <span>
            {Math.floor(seconds / 60)}:{String(seconds % 60).padStart(2, "0")}
          </span>
        </div>
        <AgentPanel addEvent={addEvent} />
        <p>
          Room: {session.room_name} · Session: {session.session_id}
        </p>
        <button className="button" onClick={toggleMute} disabled={!room}>
          {muted ? "Unmute microphone" : "Mute microphone"}
        </button>
        <button
          className="button voice-end"
          onClick={() => void end()}
          disabled={ending}
        >
          {ending ? "Ending…" : "End call"}
        </button>
        {error && (
          <p className="error-banner" role="alert">
            {error}
          </p>
        )}
      </div>
    </>
  );
}

function AgentPanel({ addEvent }: { addEvent: (text: string) => void }) {
  const { state, audioTrack } = useVoiceAssistant();
  const transcripts = useTranscriptions();
  const bottom = useRef<HTMLDivElement>(null);
  useEffect(() => {
    addEvent(`Agent state: ${state}`);
  }, [state, addEvent]);
  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);
  return (
    <>
      <div className="voice-agent-state">
        Agent: <strong>{state}</strong>
        {audioTrack && (
          <BarVisualizer state={state} trackRef={audioTrack} barCount={12} />
        )}
      </div>
      <section
        className="voice-transcript"
        aria-label="Live transcript"
        aria-live="polite"
      >
        <h3>Live transcript</h3>
        {transcripts.length === 0 ? (
          <p>Spoken words will appear here once the agent transcribes them.</p>
        ) : (
          transcripts.map((item) => (
            <div className="voice-line" key={item.streamInfo.id}>
              <strong>
                {item.participantInfo.identity.startsWith("visitor-")
                  ? "You"
                  : "Agent"}
              </strong>
              <p>{item.text}</p>
              <small>
                {item.streamInfo.attributes?.["lk.transcription_final"] ===
                "true"
                  ? "Final"
                  : "Interim"}
              </small>
            </div>
          ))
        )}
        <div ref={bottom} />
      </section>
    </>
  );
}

export function Voice() {
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [session, setSession] = useState<Created | null>(null);
  const [language, setLanguage] = useState("en");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [events, setEvents] = useState<Event[]>([]);
  const addEvent = useRef((text: string) =>
    setEvents((current) => [
      ...current,
      { id: Date.now() + Math.random(), text, at: new Date() },
    ]),
  ).current;
  useEffect(() => {
    void apiCall<Availability>("/availability")
      .then(setAvailability)
      .catch(() =>
        setError("Cannot check voice configuration. Start the backend."),
      );
  }, []);
  const start = async () => {
    setBusy(true);
    setError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "This browser cannot access a microphone. Use localhost or HTTPS in a recent browser.",
        );
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      const created = await apiCall<Created>("/sessions", "POST", {
        preferred_language: language,
        consent_acknowledged: consent,
      });
      setSession(created);
      addEvent("Voice session created");
    } catch (caught) {
      setError(
        caught instanceof Error ? caught.message : "Could not start call",
      );
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="voice-page">
      <div className="page-heading">
        <div>
          <div className="eyebrow">REAL-TIME VOICE</div>
          <h1>Live Voice Agent</h1>
          <p>Speak with VocaLead AI about your property requirements.</p>
        </div>
      </div>
      <div className="detail-grid">
        <section className="panel voice-main">
          <h2>VocaLead AI · Real estate assistant</h2>
          {!session ? (
            <>
              <p className="voice-muted">
                Your conversation is private to this call. Property listings and
                booking are not connected yet.
              </p>
              <label className="voice-label">
                Conversation language
                <select
                  value={language}
                  onChange={(event) => setLanguage(event.target.value)}
                >
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="hinglish">Hinglish</option>
                </select>
              </label>
              <div className="voice-consent">
                <strong>Before you start</strong>
                <p>
                  You will speak with an AI assistant. Your microphone audio is
                  processed by LiveKit and external speech, language and voice
                  providers. Browser microphone permission is required. The
                  server does not retain audio or transcripts by default. You
                  can end the call at any time.
                </p>
                <label>
                  <input
                    type="checkbox"
                    checked={consent}
                    onChange={(event) => setConsent(event.target.checked)}
                  />{" "}
                  I understand and agree to start this voice interaction.
                </label>
              </div>
              {availability && !availability.available && (
                <div className="error-banner">
                  Voice setup required: {availability.missing.join(", ")}. Add
                  these variables to the root .env and restart the API and
                  worker.
                </div>
              )}
              <button
                className="button voice-start"
                disabled={!consent || !availability?.available || busy}
                onClick={() => void start()}
              >
                {busy ? "Connecting…" : "Start call"}
              </button>
            </>
          ) : (
            <CallRoom
              session={session}
              addEvent={addEvent}
              onEnded={() => setSession(null)}
            />
          )}
          {error && (
            <p className="error-banner" role="alert">
              {error}
            </p>
          )}
        </section>
        <section className="panel voice-activity">
          <h2>Agent activity</h2>
          <p className="voice-muted">
            Actual room and agent lifecycle events appear here.
          </p>
          {events.length === 0 ? (
            <p>No call activity yet.</p>
          ) : (
            <ol>
              {events.map((event) => (
                <li key={event.id}>
                  <time>{event.at.toLocaleTimeString()}</time> {event.text}
                </li>
              ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
