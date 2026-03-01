"""Example: Use SmolA2ADelegateTool to call a remote A2A agent."""

import os

from smolagents import CodeAgent, InferenceClientModel

from a2a_smol_adapter import SmolA2ADelegateTool

# Create a delegation tool pointing to a remote A2A agent
delegate = SmolA2ADelegateTool(
    remote_url="http://localhost:5001/",
    api_key=os.environ.get("A2A_API_KEY"),  # optional: must match server's api_key
    max_retries=2,  # retry on network errors with exponential backoff
)

# Create a local agent with the delegation tool
model = InferenceClientModel()
agent = CodeAgent(tools=[delegate], model=model)

if __name__ == "__main__":
    result = agent.run(
        "Use the delegate_to_a2a tool to ask the remote agent to compute the factorial of 20."
    )
    print(f"Result: {result}")
