# Exact-source Guolao opposite-node reference

This freezes 12,352 explicit longitude/RA/ayanamsha component inputs and four
independent targets per input. There are 12,096 boundary combinations and 256
seeded random controls (`2026111206`). They are mathematical components, not
paired physical vectors, birth samples or a physical uncertainty model. The
28 synthetic RA starts are 0, 10, …, 270 degrees, not the Guolao star catalogue.
The 180-degree, near-360-degree and random shifts are algebraic stress inputs,
not asserted native Lahiri offsets.

The reference uses [python-flint 0.9.0](https://python-flint.readthedocs.io/en/latest/fmpq.html)
with FLINT 3.6.0 `fmpq`. Original binary64 inputs enter as exact integer ratios.
Antipode reduction, zodiac rotation and half-open membership are exact. Scalar
targets use a separately reviewed integer quotient/remainder IEEE binary64
nearest-ties-even encoder, followed only by canonical cyclic 360-to-0 display.
The oracle imports no FateBridge code and uses neither `Fraction.__float__`
nor `fmpq.__float__`. This establishes given-input arithmetic, not native node
theory, ancient mansion boundaries, a complete original text or prediction.

`criteria.json` was frozen before product comparison. `source.json.sha256`
authenticates the **decompressed** `source.json.gz` bytes. The input SHA-256 is
`14d9a8d6c395403d53cde41a55672f19b4e09e593855ae2999bc729e425693c7`;
reference SHA-256 is
`4ff2fb63f1b55f9712a622e4434513fe6704d1030289dac4801d57117ed69d3b`.
The macOS ARM reference wheel SHA-256 is
`025fd4e77f2cbbf40f63b9cd7571aad3803deb57aecd72e7c397480fe84921a0`;
the archived generator SHA-256 is
`8d804ef8bd370e552d410576f4381f58d8f93fedbc4abce283201b79df982ace`.
The wheel's binary build provenance is not independently attested.

The portable regression checks all 24,704 discrete ownership targets, plus
12 selected controls through the actual native `positions` function with only
the mean node components injected. The external development archive additionally
executes the unchanged producer assignment and actual placement for all 49,408
targets, retaining the original 9,350 failures and the corrected results. That
leaf probe is distinct from a full native or public invocation. Full ordinary
requests and installed-package checks are recorded in the
[audit](../../../../docs/guolao-algorithm-audit.md).

```bash
uv run --locked --extra dev python -m pytest -q tests/guolao/test_guolao_opposition.py
```
