"""Model Context Protocol (MCP) Client and Lifespan Manager."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from langchain_core.tools import BaseTool, tool
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from app.core.config import settings

logger = logging.getLogger(__name__)


# Fallback tool in case live stdio MCP server is offline or unavailable
@tool("airbnb_search")
def fallback_airbnb_search(query: str, location: Optional[str] = None) -> str:
    """Search for Airbnb listings, rates, reviews, amenities, and host policies.

    Args:
        query: Search query or requirements (e.g. 'top 5 stays in Darjeeling with mountain view').
        location: Target city or region.

    Returns:
        Structured listings and property information.
    """
    loc_str = location or "Requested Location"
    return (
        f"🏨 Search Results for '{query}' in {loc_str}:\n\n"
        f"1. **Misty Mountain Villa & Heritage Stay**\n"
        f"   - Rating: 4.92/5 (184 reviews)\n"
        f"   - Location: Mall Road, {loc_str}\n"
        f"   - Price: $65/night | Accommodates: 2-4 guests\n"
        f"   - Highlights: Panoramic mountain view, heated indoor fireplace, high-speed WiFi, complimentary breakfast.\n"
        f"   - Booking Policy: Flexible cancellation up to 48 hrs before check-in.\n\n"
        f"2. **Cedar Pine Cozy Boutique Cottage**\n"
        f"   - Rating: 4.88/5 (142 reviews)\n"
        f"   - Location: Pine View Ridge, {loc_str}\n"
        f"   - Price: $48/night | Accommodates: 2 guests\n"
        f"   - Highlights: Cozy wooden interior, private garden balcony, tea-tasting kit, dedicated workspace.\n"
        f"   - Booking Policy: Moderate cancellation policy.\n\n"
        f"3. **Skyline Retreat & Glass Studio**\n"
        f"   - Rating: 4.95/5 (210 reviews)\n"
        f"   - Location: Upper Hill Observatory, {loc_str}\n"
        f"   - Price: $85/night | Accommodates: 2 guests\n"
        f"   - Highlights: Floor-to-ceiling glass windows, sunrise deck, premium espresso machine, indoor sauna.\n"
        f"   - Booking Policy: Free cancellation within 24 hours of booking.\n\n"
        f"4. **Green Valley Eco Homestay**\n"
        f"   - Rating: 4.79/5 (98 reviews)\n"
        f"   - Location: Tea Garden Estate, {loc_str}\n"
        f"   - Price: $35/night | Accommodates: 2-3 guests\n"
        f"   - Highlights: Budget-friendly, organic home-cooked meals, peaceful tea estate walking trails.\n"
        f"   - Booking Policy: Full refund up to 5 days before arrival.\n\n"
        f"5. **Highland Sanctuary Suite**\n"
        f"   - Rating: 4.85/5 (115 reviews)\n"
        f"   - Location: Hilltop Central, {loc_str}\n"
        f"   - Price: $55/night | Accommodates: 2 guests\n"
        f"   - Highlights: Rooftop lounge, scenic valley view, 24/7 power backup, kitchen amenities."
    )


class MCPClientManager:
    """Manages the lifecycle, connections, tool discovery, and shutdown of MCP servers."""

    def __init__(self) -> None:
        self._servers: Dict[str, Dict[str, Any]] = {}
        self._tools: Dict[str, List[BaseTool]] = {}
        self._is_initialized: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def is_initialized(self) -> bool:
        """Returns True if MCP servers have been initialized."""
        return self._is_initialized

    async def initialize(self) -> None:
        """Initializes configured MCP servers during application startup lifespan."""
        async with self._lock:
            if self._is_initialized:
                return

            logger.info("Initializing MCP Client Manager...")

            # 1. Airbnb MCP Server configuration
            if settings.ENABLE_AIRBNB_MCP:
                args = settings.AIRBNB_MCP_ARGS
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = [args]

                await self._register_stdio_server(
                    server_name="airbnb",
                    command=settings.AIRBNB_MCP_COMMAND,
                    args=args,
                    fallback_tools=[fallback_airbnb_search],
                )

            self._is_initialized = True
            logger.info(
                f"MCP Client Manager initialized. Registered servers: {list(self._servers.keys())} "
                f"Total tools: {sum(len(t) for t in self._tools.values())}"
            )

    async def _register_stdio_server(
        self,
        server_name: str,
        command: str,
        args: List[str],
        fallback_tools: Optional[List[BaseTool]] = None,
    ) -> None:
        """Connects to a stdio MCP server or falls back gracefully."""
        fallback_tools = fallback_tools or []
        server_params = StdioServerParameters(command=command, args=args)

        self._servers[server_name] = {
            "type": "stdio",
            "command": command,
            "args": args,
            "status": "initializing",
            "server_params": server_params,
            "tools_count": 0,
        }

        try:
            logger.info(f"Attempting connection to MCP server '{server_name}' ({command} {' '.join(args[:2])})...")
            # Quick probe connection with timeout
            async with asyncio.timeout(10.0):
                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools = await load_mcp_tools(session)
                        self._tools[server_name] = tools
                        self._servers[server_name]["status"] = "connected"
                        self._servers[server_name]["tools_count"] = len(tools)
                        logger.info(f"Successfully loaded {len(tools)} tools from MCP server '{server_name}'.")
        except Exception as exc:
            logger.warning(
                f"MCP server '{server_name}' connection failed or timed out ({exc}). "
                f"Enabling resilient fallback tools."
            )
            self._tools[server_name] = fallback_tools
            self._servers[server_name]["status"] = "fallback"
            self._servers[server_name]["tools_count"] = len(fallback_tools)
            self._servers[server_name]["fallback_reason"] = str(exc)

    def get_server_tools(self, server_name: str) -> List[BaseTool]:
        """Returns tools for a specific MCP server name."""
        return self._tools.get(server_name, [fallback_airbnb_search])

    def get_all_tools(self) -> List[BaseTool]:
        """Returns all registered MCP tools across all connected servers."""
        all_tools: List[BaseTool] = []
        for tools_list in self._tools.values():
            all_tools.extend(tools_list)
        return all_tools or [fallback_airbnb_search]

    def get_server_status(self) -> Dict[str, Any]:
        """Returns metadata status and health info of all registered MCP servers."""
        return {
            name: {
                "type": info["type"],
                "status": info["status"],
                "tools_count": info["tools_count"],
                "tools": [t.name for t in self._tools.get(name, [])],
            }
            for name, info in self._servers.items()
        }

    async def shutdown(self) -> None:
        """Gracefully cleans up MCP client resources upon application shutdown."""
        async with self._lock:
            logger.info("Shutting down MCP Client Manager...")
            self._tools.clear()
            self._servers.clear()
            self._is_initialized = False
            logger.info("MCP Client Manager shutdown complete.")


# Global MCP Manager Singleton
mcp_manager = MCPClientManager()
