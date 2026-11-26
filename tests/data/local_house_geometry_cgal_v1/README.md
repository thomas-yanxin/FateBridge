# Local house working geometry

Original finite binary64 phases and exact rational intermediate phases are compared with actual CGAL 6.2.1 `Direction_2` ordering using its exact Boost rational kernel. An explicitly declared monotone rational diamond mapping embeds the phase circle without trigonometric rounding. The mapping is our glue, not an independently supplied CGAL angular conversion. A separate exact-rational interval formula cross-checks every qualified CGAL answer.

The fixed scalar set has 240 analytic rings, 159 source-sign inputs and 31,784 circular membership/qualification cases. 2,256 nonpartition native cusp controls are excluded from numerical successes: their declared native projection is required. The remaining overlapping checks total 35,447. Original binary64 point cases and newly supported exact intermediate cases are recorded separately. These counts do not count independent algorithms or establish all continuous inputs.

62 complete synthetic public inputs preserve missing-clock, missing-coordinate and unsupported-mode behavior. Their downstream point decisions use actual CGAL predicates over original source coordinates or explicitly recorded native working phases. The 36 supplemental constructed phase controls are separate from the original 35,447 checks.

Source astronomy and native nonlinear projection phases are inputs to the circular tests, not new independent acceptance of ephemeris, geometric uniqueness at the poles, source doctrine, predictions or SOTA. Original physical/astronomical/source limits remain in the result. Source/model labels distinguish MC-anchored equal houses, original-cusp layouts, explicit whole-sign overrides and reversed projection phases.

The portable application regression explicitly injects these frozen original core inputs, including the original working-phase ratios, through in-process REST, CLI and MCP. Different native astronomy builds can return different last bits, so their outputs are different numerical inputs and cannot share a bit-for-bit physical-output golden. Live-source and installed-wheel protocols require their own exact CGAL input bindings; no tolerance replaces the exact-predicate criterion.

Primary numerical semantics: [CGAL Direction_2](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Direction__2.html), [Swiss house positions, section 16](https://www.astro.com/swisseph/swephprg.htm). Working mpmath values use the pinned 1.3.0 backend's exact `to_rational` conversion; 100-digit presentation text does not select a house.

The bundled reference and its SHA-256 sidecar preserve the portable numerical oracle. Historical before/after runs and installed-wheel protocol evidence are external research records, not repository test dependencies.
