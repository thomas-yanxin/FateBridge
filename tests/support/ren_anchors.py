"""Execute current Ren anchor requests without importing any test module."""

from tests.fixtures.ren_anchors import ANCHOR_PAYLOADS
from tests.support.transports import SPECS


def anchor_output(key="liureng_gods", **extra):
    spec = SPECS[key]
    payload = {**ANCHOR_PAYLOADS[key], **extra}
    fn, args, kwargs = spec.bind(spec.request_model.model_validate(payload))
    return fn(*args, **kwargs)
