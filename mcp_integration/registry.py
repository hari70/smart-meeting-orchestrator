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
        logger.info("🔧 MCP processor registered globally")
    else:
        logger.warning("⚠️  MCP processor cleared")

def get_mcp_processor():
    """Get the global MCP processor instance."""
    return _mcp_processor
