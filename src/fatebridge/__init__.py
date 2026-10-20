"""
FateBridge - Fortune Telling System

A backend-only Python toolkit bridging Chinese metaphysics, divination and
offline Western astrology. The same domain capabilities are exposed through
three interfaces (FastAPI REST, FastMCP, and the ``fatebridge`` CLI), all
derived from a single central tool catalog
(``fatebridge.services.tool_catalog``).

See the docs/ directory for the full algorithm coverage matrix and the
developer / Agent integration guide.

Public API
----------
FateBridge is consumed through its three transports rather than as a library of
importable functions. The programmatic entry point is the central tool catalog
``fatebridge.services.tool_catalog`` (every REST route, MCP tool and CLI
subcommand is derived from it). This top-level module intentionally exposes only
metadata; deeper capabilities live under ``fatebridge.services`` / ``.core``.
"""

__version__ = "0.1.1"
__author__ = "thomas-yanxin"

__all__ = ["__version__", "__author__"]
