"""Inject a supplied current output to probe adapter validation."""

from copy import deepcopy
from dataclasses import replace

import fatebridge.application.execution as execution


def inject_canping_output(monkeypatch, output):
    original = execution.execute_spec

    def bound_output(spec, request):
        if spec.key == "canping":
            spec = replace(spec, bind=lambda _: (lambda: deepcopy(output), (), {}))
        return original(spec, request)

    monkeypatch.setattr(execution, "execute_spec", bound_output)
