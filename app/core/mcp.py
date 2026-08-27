"""Model Context Protocol (MCP) Client and Lifespan Manager."""

import asyncio
import json
import logging
import os
import shutil
from typing import Any, Dict, List, Optional
from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from app.core.config import settings

logger = logging.getLogger(__name__)


class MCPClientManager:
    """Manages MCP server lifecycles and tool discovery using MultiServerMCPClient."""

    def __init__(self) -> None:
        self._client: Optional[MultiServerMCPClient] = None
        self._tools: List[BaseTool] = []
        self._servers_config: Dict[str, Any] = {}
        self._is_initialized: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()

    @property
    def is_initialized(self) -> bool:
        """Returns True if MCP servers have been initialized."""
        return self._is_initialized

    async def initialize(self) -> None:
        """Initializes configured MCP servers during application startup."""
        async with self._lock:
            if self._is_initialized:
                return

            logger.info("Initializing MCP Client Manager with MultiServerMCPClient...")
            server_configs: Dict[str, Any] = {}

            # 1. Airbnb MCP Server configuration
            if settings.ENABLE_AIRBNB_MCP:
                args = settings.AIRBNB_MCP_ARGS
                if isinstance(args, str):
                    import json
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = [args]

                cmd = shutil.which(settings.AIRBNB_MCP_COMMAND) or settings.AIRBNB_MCP_COMMAND
                server_configs["airbnb"] = {
                    "transport": "stdio",
                    "command": cmd,
                    "args": args,
                }

            self._servers_config = server_configs

            if server_configs:
                try:
                    self._client = MultiServerMCPClient(server_configs)
                    self._tools = await self._client.get_tools()
                    logger.info(
                        f"MCP Client Manager initialized via MultiServerMCPClient. "
                        f"Registered servers: {list(server_configs.keys())} | Tools: {[t.name for t in self._tools]}"
                    )
                except Exception as exc:
                    logger.warning(f"MultiServerMCPClient tool loading encountered issue ({exc}).")
                    self._tools = []

            self._is_initialized = True

    def get_client(self) -> Optional[MultiServerMCPClient]:
        """Returns the MultiServerMCPClient instance."""
        return self._client

    async def get_tools(self) -> List[BaseTool]:
        """Returns all loaded MCP tools."""
        if self._client and not self._tools:
            try:
                self._tools = await self._client.get_tools()
            except Exception as e:
                logger.warning(f"Error fetching tools from MultiServerMCPClient: {e}")
        return self._tools

    def get_server_tools(self, server_name: str) -> List[BaseTool]:
        """Returns tools matching a specific server or domain."""
        return self._tools

    def get_all_tools(self) -> List[BaseTool]:
        """Returns all registered MCP tools across all connected servers."""
        return self._tools

    def get_server_status(self) -> Dict[str, Any]:
        """Returns metadata status and health info of all registered MCP servers."""
        return {
            name: {
                "type": cfg.get("transport", "stdio"),
                "status": "connected" if self._tools else "ready",
                "tools_count": len(self._tools),
                "tools": [t.name for t in self._tools],
            }
            for name, cfg in self._servers_config.items()
        }

    async def shutdown(self) -> None:
        """Gracefully cleans up MCP client resources upon application shutdown."""
        async with self._lock:
            logger.info("Shutting down MCP Client Manager...")
            self._client = None
            self._tools.clear()
            self._servers_config.clear()
            self._is_initialized = False
            logger.info("MCP Client Manager shutdown complete.")


# Global MCP Manager Singleton
mcp_manager = MCPClientManager()
