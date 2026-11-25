"""One private native process for every outer Human Design calculation."""

from functools import wraps
from typing import Any, Callable, cast

from fatebridge.core.astro import native_execution
from fatebridge.core.astro.source_session import source_session


def isolated_human_design(
    function: Callable[..., dict[str, Any]],
) -> Callable[..., dict[str, Any]]:
    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if not native_execution.in_native_worker():
            with source_session(restore_native_path=False):
                return cast(
                    dict[str, Any],
                    native_execution.calculate(
                        "fatebridge.services.human_design.calculate_human_design",
                        args,
                        kwargs,
                    ),
                )
        result = function(*args, **kwargs)
        result["native_execution_context"] = native_execution.context_evidence()
        return result

    return wrapped
