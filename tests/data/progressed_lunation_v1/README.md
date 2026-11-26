# Progressed lunation source fixture v1

This fixture uses one synthetic birth at 2000-01-01T12:00:00+00:00 and a fixed 40-day window of nominal UTC labels. Each independent scan found 11 events covering all eight targets, from 0° through 315° in 45° steps.

Expected values come from original Swiss Ephemeris 2.10.03 C (flags=258, sepl_18.se1, semo_18.se1) and a separate DE440/CALCEPH/SOFA calculation. The reference ran without FateBridge imports or access to product outputs. Both complete root sets were saved before comparison between sources.

inputs.json and criteria.json preserve the oracle inputs and criteria. expected-roots.json retains every C and DE440 root, bracket, exact nominal age, source coordinate, returned flag, file identity and comparison residual. Historical absolute library paths in the provenance are source locators rather than runtime dependencies.

The numerical gates were fixed before execution:

| Comparison | Angle | Event time |
| --- | --- | --- |
| Same-source original C | 1e-8 degree | 1 millisecond |
| Independent DE440/SOFA | 0.01 degree | 60 seconds |

The age display has a separate half-unit bound of 0.0005 symbolic year. Raw nominal age equals the source TT point minus (2451545 + 64.184/86400) because TT−UTC remains 64.184 seconds throughout this window. These inputs cover a constant-offset window; clock discontinuities require separate cases. Traditional phase names are documented separately in western-astrology.md.

The actual-source regression is marked local_data and requires the pinned ephe/sepl_18.se1 and ephe/semo_18.se1 files. It temporarily selects that directory and disables a host JPL override, then restores the environment before restoring native configuration. Cloud CI excludes external-source cases under the existing policy; a full local pytest run includes this case.
