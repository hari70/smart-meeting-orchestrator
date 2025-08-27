from __future__ import annotations
from typing import Protocol, Any, Dict, List, Optional

class ToolExecutable(Protocol):
    async def __call__(self, **kwargs) -> Any: ...  # pragma: no cover

class ToolDefinition:
    def __init__(self, name: str, description: str, schema: Dict, executor: ToolExecutable):
        self.name = name
        self.description = description
        self.schema = schema
        self.executor = executor

    async def invoke(self, **kwargs):
        return await self.executor(**kwargs)

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        self._tools[tool.name] = tool

    def list(self) -> List[Dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "input_schema": t.schema}
            for t in self._tools.values()
        ]

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    async def call(self, name: str, **kwargs):
        import logging, time
        logger = logging.getLogger("tool.invoke")
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found")
        start = time.time()
        try:
            result = await tool.invoke(**kwargs)
            logger.info("tool=%s status=success elapsed_ms=%.1f args_keys=%s", name, (time.time()-start)*1000, list(kwargs.keys()))
            return result
        except Exception:
            logger.exception("tool=%s status=error elapsed_ms=%.1f", name, (time.time()-start)*1000)
            raise

# Global singleton
tool_registry = ToolRegistry()
