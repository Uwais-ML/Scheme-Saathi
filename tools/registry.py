"""Registry mapping tool names to execution functions."""

import logging
from typing import Any, Callable
from state.models import UserProfile

logger = logging.getLogger(__name__)

# Registry dictionary storing tool_name -> (callable, description)
_TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def register_tool(name: str, description: str = ""):
    """Decorator to register a tool function."""

    def decorator(fn: Callable[..., Any]):
        _TOOL_REGISTRY[name] = {"fn": fn, "description": description}
        return fn

    return decorator


def get_tool_descriptions() -> str:
    """Return formatted descriptions of all registered tools for system prompt."""
    lines = []
    for name, info in _TOOL_REGISTRY.items():
        desc = info["description"] or info["fn"].__doc__ or "No description."
        lines.append(f"- {name}: {desc.strip()}")
    return "\n".join(lines)


def execute_tool(
    name: str,
    args: dict[str, Any],
    profile: UserProfile,
) -> dict[str, Any]:
    """Execute a tool safely and return a dict result.

    Every tool returns: {"ok": bool, "data": ..., "error": ...}
    """
    if name not in _TOOL_REGISTRY:
        logger.warning("Attempted to call unregistered tool: %s", name)
        return {
            "ok": False,
            "data": None,
            "error": f"Tool '{name}' is not recognized. Please use a valid tool.",
        }

    tool_info = _TOOL_REGISTRY[name]
    tool_fn = tool_info["fn"]

    try:
        import inspect
        sig = inspect.signature(tool_fn)

        # Inject household_id if expected by tool but omitted by caller
        if "household_id" in sig.parameters and "household_id" not in args:
            args["household_id"] = profile.user_id

        # Pass profile as keyword argument if accepted, otherwise just args
        if "profile" in sig.parameters:
            result = tool_fn(args=args, profile=profile)
        elif "args" in sig.parameters:
            result = tool_fn(args=args)
        else:
            result = tool_fn(**args)

        # Standardize return dictionary
        if isinstance(result, dict) and "ok" in result:
            return result
        return {"ok": True, "data": result, "error": None}

    except Exception as exc:
        logger.exception("Error executing tool '%s': %s", name, exc)
        return {
            "ok": False,
            "data": None,
            "error": f"Error executing tool '{name}': {str(exc)}",
        }
