"""SmolA2AServer — Exposes a smolagents CodeAgent as an A2A-compliant server."""

from __future__ import annotations

import asyncio
import hmac
import logging
import uuid

import uvicorn
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Message,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)
from a2a.utils.helpers import build_text_artifact
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from smolagents import CodeAgent

logger = logging.getLogger(__name__)

# Paths excluded from API key auth
_AUTH_EXEMPT_PATHS = {"/.well-known/agent-card.json", "/health"}


class _ApiKeyMiddleware(BaseHTTPMiddleware):
    """Validates Bearer token on all requests except exempt paths."""

    def __init__(self, app, api_key: str) -> None:
        super().__init__(app)
        self._api_key = api_key

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _AUTH_EXEMPT_PATHS:
            return await call_next(request)

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer ") or not hmac.compare_digest(
            auth_header[7:], self._api_key
        ):
            return JSONResponse(
                status_code=401,
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized: invalid or missing API key",
                    },
                },
            )
        return await call_next(request)


class SmolAgentExecutor(AgentExecutor):
    """Bridges A2A task execution to a smolagents CodeAgent."""

    def __init__(self, agent: CodeAgent, *, agent_timeout: float = 120.0) -> None:
        if not agent:
            raise ValueError("agent is required")
        if agent_timeout <= 0:
            raise ValueError("agent_timeout must be a positive number")
        self._agent = agent
        self._agent_timeout = agent_timeout

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        if not context.message:
            raise ValueError("RequestContext must have a message")

        task_id = context.task_id
        context_id = context.context_id
        prompt = _extract_text(context.message)

        # Emit: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        # Run agent synchronously in executor with timeout
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(
                loop.run_in_executor(None, self._agent.run, prompt),
                timeout=self._agent_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Agent execution timed out for task %s after %ss",
                task_id,
                self._agent_timeout,
            )
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.failed),
                    final=True,
                )
            )
            return
        except Exception as exc:
            logger.error("Agent execution failed for task %s: %s", task_id, exc, exc_info=True)
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.failed),
                    final=True,
                )
            )
            return

        # Emit: artifact
        result_text = str(result) if result is not None else ""
        artifact = build_text_artifact(result_text, str(uuid.uuid4()))
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(task_id=task_id, context_id=context_id, artifact=artifact)
        )

        # Emit: completed
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
        )

    async def execute_streaming(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute with streaming — emits intermediate working events from agent steps."""
        if not context.message:
            raise ValueError("RequestContext must have a message")

        task_id = context.task_id
        context_id = context.context_id
        prompt = _extract_text(context.message)

        # Emit: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        def _run_streaming() -> tuple[list[str], str]:
            """Run agent.run(stream=True) in a thread, collecting steps."""
            steps: list[str] = []
            final_result = None
            for step in self._agent.run(prompt, stream=True):
                step_text = str(step) if step is not None else ""
                if step_text:
                    steps.append(step_text)
                final_result = step
            result = str(final_result) if final_result is not None else ""
            return steps, result

        loop = asyncio.get_running_loop()
        try:
            steps, result_text = await asyncio.wait_for(
                loop.run_in_executor(None, _run_streaming),
                timeout=self._agent_timeout,
            )
        except asyncio.TimeoutError:
            logger.error(
                "Agent streaming timed out for task %s after %ss",
                task_id,
                self._agent_timeout,
            )
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.failed),
                    final=True,
                )
            )
            return
        except Exception as exc:
            logger.error("Agent streaming failed for task %s: %s", task_id, exc, exc_info=True)
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.failed),
                    final=True,
                )
            )
            return

        # Emit intermediate working events for each step
        for step_text in steps:
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.working),
                    final=False,
                )
            )

        # Emit: artifact
        artifact = build_text_artifact(result_text, str(uuid.uuid4()))
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(task_id=task_id, context_id=context_id, artifact=artifact)
        )

        # Emit: completed
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )


def _extract_text(message: Message) -> str:
    """Extract text content from an A2A Message.

    Handles both SDK Part wrapper objects (Part.root.text) and plain objects
    with a direct .text attribute (e.g., mocks in tests).
    """
    if not message or not message.parts:
        raise ValueError("Message must have at least one part")
    _MAX_PROMPT_SIZE = 100_000  # 100KB limit to prevent abuse
    texts: list[str] = []
    total_size = 0
    for part in message.parts:
        text = None
        # Direct .text attribute (plain objects, mocks)
        if hasattr(part, "text") and isinstance(getattr(part, "text", None), str):
            text = part.text
        # SDK Part wrapper: actual part is in .root
        elif hasattr(part, "root") and hasattr(part.root, "text"):
            text = str(part.root.text)
        if text is not None:
            total_size += len(text)
            if total_size > _MAX_PROMPT_SIZE:
                raise ValueError(
                    f"Message text exceeds maximum size of {_MAX_PROMPT_SIZE} characters"
                )
            texts.append(text)
    if not texts:
        raise ValueError("Message contains no text parts")
    return "\n".join(texts)


class SmolA2AServer:
    """A2A-compliant server wrapping a smolagents CodeAgent."""

    def __init__(
        self,
        agent: CodeAgent,
        *,
        name: str = "smol-agent",
        description: str = "A smolagents CodeAgent exposed via A2A protocol",
        version: str = "0.1.0",
        host: str = "127.0.0.1",
        port: int = 5000,
        skills: list[dict] | None = None,
        api_key: str | None = None,
        agent_timeout: float = 120.0,
    ) -> None:
        if not agent:
            raise ValueError("agent is required")
        if not name:
            raise ValueError("name is required")
        if not isinstance(port, int) or port < 1 or port > 65535:
            raise ValueError("port must be an integer between 1 and 65535")

        self._agent = agent
        self._host = host
        self._port = port
        self._api_key = api_key
        self._version = version

        default_skills = skills or [
            {
                "id": "general",
                "name": "General Task",
                "description": "Execute a general-purpose task using Python code generation",
                "tags": ["code-generation", "python"],
                "examples": ["Compute the factorial of 10", "List files in a directory"],
            }
        ]

        self._agent_card = AgentCard(
            name=name,
            description=description,
            version=version,
            url=f"http://{host}:{port}/",
            capabilities=AgentCapabilities(streaming=True),
            skills=[AgentSkill(**s) for s in default_skills],
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
        )

        self._executor = SmolAgentExecutor(agent, agent_timeout=agent_timeout)
        self._task_store = InMemoryTaskStore()
        self._handler = DefaultRequestHandler(
            agent_executor=self._executor,
            task_store=self._task_store,
        )
        self._app_builder = A2AFastAPIApplication(
            agent_card=self._agent_card,
            http_handler=self._handler,
        )

    @property
    def agent_card(self) -> AgentCard:
        return self._agent_card

    def build_app(self):
        """Build the FastAPI app with auth middleware and health endpoint."""
        app = self._app_builder.build(title=f"A2A: {self._agent_card.name}")

        @app.get("/health")
        async def health():
            return {
                "status": "ok",
                "agent": self._agent_card.name,
                "version": self._version,
            }

        if self._api_key:
            app.add_middleware(_ApiKeyMiddleware, api_key=self._api_key)

        return app

    def run(self) -> None:
        app = self.build_app()
        uvicorn.run(app, host=self._host, port=self._port)
