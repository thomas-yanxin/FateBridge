# Given-argument house-coordinate rounding: independent Arb reference

`inputs.json` contains 72 supplied argument vectors in the original order, with 24 rows each for R, C and T. Source files are identified by basename. `reference.jsonl.gz` preserves the independent reference for both the unshifted and shifted profiles. The reference uses vector-plane geometry and outward Arb intervals to bracket the root in the physical quadrant. `provenance.json` records the source and the files consumed by the test.

`native-diagnostic-inputs.json` supplies the native position used as an input to the correction. The expected coordinate, phase, house, round-to-nearest-even result and delivery value come from the independent reference. The working-phase tolerance is 1e-50 degrees.

The test uses the declared 1/3600000-degree shift for R and C and the unshifted profile for T. The T vectors cover interior roots. Separate fixture suites cover the endpoint and native-pole cases.

Run the reference comparison with `uv run --locked --extra dev python -m pytest -q tests/western/test_western_house_coordinate_rounding.py`.
