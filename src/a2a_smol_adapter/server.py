"""SmolA2AServer — Exposes a smolagents CodeAgent as an A2A-compliant server."""

from __future__ import annotations

import asyncio
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

from smolagents import CodeAgent

logger = logging.getLogger(__name__)


class SmolAgentExecutor(AgentExecutor):
    """Bridges A2A task execution to a smolagents CodeAgent."""

    def __init__(self, agent: CodeAgent) -> None:
        if not agent:
            raise ValueError("agent is required")
        self._agent = agent

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Run the smolagents CodeAgent with the incoming message text."""
        if not context.current_task:
            raise ValueError("RequestContext must have a current_task")
        if not context.message:
            raise ValueError("RequestContext must have a message")

        task = context.current_task
        user_message = context.message

        # Extract text from the incoming A2A message
        prompt = _extract_text(user_message)

        # Update status to working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.working),
                final=False,
            )
        )

        # Run the smolagents CodeAgent in a thread (it's synchronous)
        loop = asyncio.get_running_loop()
        try:
            result = await loop.run_in_executor(None, self._agent.run, prompt)
        except Exception as exc:
            logger.error("Agent execution failed for task %s: %s", task.id, exc, exc_info=True)
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task.id,
                    context_id=task.context_id,
                    status=TaskStatus(state=TaskState.failed),
                    final=True,
                )
            )
            return

        # Package the result as an A2A artifact
        result_text = str(result) if result is not None else ""
        artifact = build_text_artifact(result_text, str(uuid.uuid4()))
        artifact_event = TaskArtifactUpdateEvent(
            task_id=task.id,
            context_id=task.context_id,
            artifact=artifact,
        )
        await event_queue.enqueue_event(artifact_event)

        # Mark task as completed
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel is not supported for smolagents CodeAgent."""
        task = context.current_task
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task.id,
                context_id=task.context_id,
                status=TaskStatus(state=TaskState.canceled),
                final=True,
            )
        )


def _extract_text(message: Message) -> str:
    """Extract plain text from an A2A Message.

    Raises:
        ValueError: If message has no text parts.
    """
    if not message or not message.parts:
        raise ValueError("Message must have at least one part")

    parts = []
    for part in message.parts:
        if hasattr(part, "text"):
            parts.append(part.text)

    if not parts:
        raise ValueError("Message contains no text parts")

    return "\n".join(parts)


class SmolA2AServer:
    """A2A-compliant server wrapping a smolagents CodeAgent.

    Usage:
        from smolagents import CodeAgent, InferenceClientModel
        from a2a_smol_adapter import SmolA2AServer

        agent = CodeAgent(tools=[], model=InferenceClientModel())
        server = SmolA2AServer(agent, name="my-smol-agent", port=5000)
        server.run()
    """

    def __init__(
        self,
        agent: CodeAgent,
        *,
        name: str = "smol-agent",
        description: str = "A smolagents CodeAgent exposed via A2A protocol",
        version: str = "0.1.0",
        host: str = "0.0.0.0",
        port: int = 5000,
        skills: list[dict] | None = None,
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

        # Build the AgentCard
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
            capabilities=AgentCapabilities(streaming=False),
            skills=[AgentSkill(**s) for s in default_skills],
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
        )

        # Build the A2A server stack
        self._executor = SmolAgentExecutor(agent)
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
        """Build and return the FastAPI app (for testing or custom deployment)."""
        return self._app_builder.build(title=f"A2A: {self._agent_card.name}")

    def run(self) -> None:
        """Start the server with uvicorn."""
        app = self.build_app()
        uvicorn.run(app, host=self._host, port=self._port)
