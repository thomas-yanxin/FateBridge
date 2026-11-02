"""run_metadata: tool_name is authoritative (from the spec), never guessed.

After the catalog unification every surface stamps run_metadata with the
ToolSpec's name, so the old payload-shape inference is dead. These tests lock
that contract: the renderer must NOT reverse-engineer a name from payload shape.
"""

from fatebridge.services import run_metadata
from fatebridge.services.run_metadata import (
    attach_run_metadata,
    engine_is_approximate,
    resolve_runtime_engine,
)


def test_attach_run_metadata_uses_explicit_name():
    out = attach_run_metadata({"x": 1}, tool_name="bazi_wealth")
    assert out["run_metadata"]["tool_name"] == "bazi_wealth"


def test_run_metadata_flags_approximate_astro_engine():
    # Approximate / mixed astro backends -> degraded precision flag is True.
    approx = attach_run_metadata(
        {"chart_profile": {"engine_backend": "fatebridge_approximate_orbital_model"}},
        tool_name="astro_chart",
    )
    assert approx["run_metadata"]["engine_is_approximate"] is True
    mixed = attach_run_metadata(
        {"chart_profile": {"engine_precision": "mixed_precision_runtime_model"}},
        tool_name="astro_chart",
    )
    assert mixed["run_metadata"]["engine_is_approximate"] is True

    # Swiss-ephemeris precision and non-astro deterministic tools -> False.
    precise = attach_run_metadata(
        {"chart_profile": {"engine_backend": "swisseph_api"}}, tool_name="astro_chart"
    )
    assert precise["run_metadata"]["engine_is_approximate"] is False
    bazi = attach_run_metadata({"x": 1}, tool_name="bazi_wealth")
    assert bazi["run_metadata"]["engine_is_approximate"] is False


def test_run_metadata_flags_silent_moshier_downgrade():
    # swisseph backend reports a constant engine_precision/backend regardless of
    # whether .se1 data files exist; the real model is in ephemeris_model. A
    # silent downgrade to Moshier (or mixed) must still flag approximate=True so
    # an agent never overstates precision to the user.
    for model in ("moshier", "mixed"):
        out = attach_run_metadata(
            {
                "chart_profile": {
                    "engine_backend": "swisseph_api",
                    "engine_precision": "ephemeris_runtime_model",
                    "ephemeris_model": model,
                }
            },
            tool_name="astro_chart",
        )
        assert out["run_metadata"]["engine_is_approximate"] is True, model
    # Full Swiss Ephemeris data files present -> genuine full precision.
    swieph = attach_run_metadata(
        {
            "chart_profile": {
                "engine_backend": "swisseph_api",
                "engine_precision": "ephemeris_runtime_model",
                "ephemeris_model": "swieph",
            }
        },
        tool_name="astro_chart",
    )
    assert swieph["run_metadata"]["engine_is_approximate"] is False


def test_engine_is_approximate_unit():
    assert engine_is_approximate("approximate_orbital_model") is True
    assert engine_is_approximate("mixed_runtime_backends") is True
    assert engine_is_approximate("ephemeris_runtime_model") is False
    assert engine_is_approximate(run_metadata.DEFAULT_ENGINE) is False


def test_attach_run_metadata_is_idempotent():
    seeded = {"run_metadata": {"tool_name": "already"}, "x": 1}
    assert attach_run_metadata(seeded, tool_name="other") is seeded


def test_resolve_runtime_engine_still_detects_engine():
    assert (
        resolve_runtime_engine({"chart_profile": {"engine_backend": "swiss"}})
        == "swiss"
    )
    assert resolve_runtime_engine({"nothing": 1}) == run_metadata.DEFAULT_ENGINE


def test_render_does_not_guess_tool_name_from_payload_shape():
    from fatebridge.mcp_server import _render_protocol_response

    # A payload whose shape the OLD guesser would have mapped to "chart13".
    misleading = {"chart_profile": {"chart_type": "chart13"}}
    rendered = _render_protocol_response(misleading, tool_name=None)
    payload = rendered.structured_content
    # No explicit name supplied -> a neutral marker, NOT a shape-derived guess.
    assert payload["run_metadata"]["tool_name"] == "unknown_tool"
