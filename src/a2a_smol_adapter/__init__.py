"""A2A-Smol-Adapter: Bridge between smolagents and the A2A protocol."""

from a2a_smol_adapter.server import SmolA2AServer
from a2a_smol_adapter.client_tool import SmolA2ADelegateTool

__all__ = ["SmolA2AServer", "SmolA2ADelegateTool"]
__version__ = "0.1.0"
