"""MCP processor registry to avoid circular imports."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global MCP processor instance
_mcp_processor = None

def set_mcp_processor(processor):
    """Set the global MCP processor instance."""
    global _mcp_processor
    _mcp_processor = processor
    if processor:
        logger.info(f"🔧 MCP processor registered globally: {processor}, llm_enabled={getattr(processor, 'llm_enabled', 'unknown')}")
    else:
        logger.warning("⚠️  MCP processor cleared (set to None)")

def get_mcp_processor():
    """Get the global MCP processor instance."""
    processor = _mcp_processor
    logger.debug(f"🔍 Getting MCP processor: {processor}")
    return processor
