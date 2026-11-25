# Progressed lunation source fixture v1

This fixture uses one synthetic birth at `2000-01-01T12:00:00+00:00` and a fixed 40-day window of nominal UTC labels. Each independent scan found 11 events covering all eight targets, from 0° through 315° in 45° steps. These are 11 events in one engineering case, not 11 independent observations of real-world outcomes.

Expected values come from original Swiss Ephemeris 2.10.03 C (`flags=258`, `sepl_18.se1`, `semo_18.se1`) and a separate DE440/CALCEPH/SOFA calculation. The reference ran once, with no FateBridge imports and no access to product outputs. Both complete root sets were saved before comparison between sources. No product output supplied expected values.

`inputs.json` and `criteria.json` preserve the frozen oracle inputs and criteria byte for byte. `expected-roots.json` retains every C and DE440 root, bracket, exact nominal age, source coordinate, returned flag, file identity, comparison residual and provenance qualification. Its sidecar binds the exact bytes. Full sampling histories and temporary observers remain in the external audit archive. Historical absolute library paths are provenance locators, not fixture runtime dependencies.

The numerical gates were fixed before execution:

| Comparison | Angle | Event time |
| --- | --- | --- |
| Same-source original C | 1e-8 degree | 1 millisecond |
| Independent DE440/SOFA | 0.01 degree | 60 seconds |

The age display has a separate half-unit bound of 0.0005 symbolic year. Raw nominal age equals the source TT point minus `2451545 + 64.184/86400` only because TT−UTC remains 64.184 seconds throughout this particular window. This does not establish uniform SI UTC, a unique inverse of a quantized clock, physical accuracy below the native time grid, all historical or future clock policies, or predictive validity. Traditional phase names are reviewed separately in the western-astrology documentation; the numerical oracle itself does not adjudicate them.

The original full `reference.json` contains 8,144,705 bytes, SHA-256 `b481bb457c2cdb673e1e6d1dcab7a4688dd0e6a0c29359f91d858e6bf94e5f56`. Its script, full result, input freeze and seal are archived under `~/.codex/artifacts/fatebridge-audit-20261117-round22/lunation-actual-motion/independent-reference/` and identified by the fixture metadata. Packaging did not rerun the reference or grant further root-cause or acceptance credit. Earlier January 2026 quarter-phase evidence, Horosa controls, retrieval qualifications and failures retain their original scope.

The actual-source regression is marked `local_data`. Local runs require the pinned `ephe/sepl_18.se1` and `ephe/semo_18.se1` files. The test temporarily selects that directory and disables a host JPL override, then restores the environment before restoring native configuration. Cloud CI excludes external-source cases under the existing policy; default full local pytest includes this case. Packaging and this audit round did not execute project tests.
