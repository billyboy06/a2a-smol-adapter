"""Example: Expose a smolagents CodeAgent as an A2A server."""

import os

from smolagents import CodeAgent, InferenceClientModel

from a2a_smol_adapter import SmolA2AServer

# Create a smolagents CodeAgent
model = InferenceClientModel()
agent = CodeAgent(tools=[], model=model, add_base_tools=True)

# Wrap it in an A2A server
server = SmolA2AServer(
    agent,
    name="smol-code-agent",
    description="A general-purpose code agent exposed via A2A",
    port=5001,
    api_key=os.environ.get("A2A_API_KEY"),  # optional: set env var to protect with Bearer token
    agent_timeout=60.0,  # optional: timeout after 60s (default: 120s)
    skills=[
        {
            "id": "code-gen",
            "name": "Python Code Generation",
            "description": "Generate and execute Python code to solve tasks",
            "tags": ["python", "code-generation"],
            "examples": [
                "Compute the first 20 Fibonacci numbers",
                "Parse a CSV file and compute statistics",
            ],
        }
    ],
)

if __name__ == "__main__":
    print(f"Starting A2A server: {server.agent_card.name}")
    print("Agent Card: http://localhost:5001/.well-known/agent-card.json")
    print("Health:     http://localhost:5001/health")
    print("JSON-RPC:   http://localhost:5001/")
    server.run()
