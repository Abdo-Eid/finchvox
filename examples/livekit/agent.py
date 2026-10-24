import logging

import finchvox
from finchvox.livekit import upload_session_artifacts
from dotenv import load_dotenv
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, inference
from livekit.plugins import silero

load_dotenv()

logger = logging.getLogger("finchvox-livekit-example")

tracer_provider = finchvox.init_livekit(
    service_name="livekit-agent",
    endpoint="http://localhost:4317",
    metadata={"agent.version": "1.0.0"},
    capture_logs=True,
    allow_pii=True,  # Local replay: transcript/tool/response content is visible.
)


class VoiceAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are a helpful voice assistant. Keep responses brief and conversational.",
            stt=inference.STT(model="deepgram/nova-3"),
            llm=inference.LLM(model="openai/gpt-4o-mini"),
            tts=inference.TTS(model="cartesia/sonic"),
        )

    async def on_enter(self):
        self.session.generate_reply(instructions="Greet the user warmly.")


server = AgentServer()


async def on_session_end(ctx: JobContext) -> None:
    """Attach LiveKit's finalized report + local recording to Finchvox."""
    report = ctx.make_session_report()

    # on_session_end runs before LiveKit's final telemetry cleanup. Flush our
    # local OTLP exporter first so Finchvox can match report.job_id/room_id to
    # the trace that just ended.
    finchvox.flush_livekit(tracer_provider)
    try:
        trace_id = await upload_session_artifacts(report=report)
        logger.info("Finchvox replay finalized: trace_id=%s", trace_id)
    except Exception:
        # Keep observability failures from breaking normal job shutdown.
        logger.exception("Failed to finalize Finchvox session replay")


@server.rtc_session(on_session_end=on_session_end)
async def entrypoint(ctx: JobContext):
    async def flush_observability():
        finchvox.flush_livekit(tracer_provider)

    ctx.add_shutdown_callback(flush_observability)

    session = AgentSession(vad=silero.VAD.load())
    await session.start(agent=VoiceAgent(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
