# Exact secular solar antipode and Nathonnatha complements

Inputs, criteria and expected values were frozen before the production change
on2026-11-12. The portable archive packages12067development and2000validation
mean-epoch cases, plus10716development and2000validation meridian/right-ascension
pairs.26783cases yield187481overlapping scalar checks; repeated graha group
values are not independent samples or algorithms.

A fresh python-flint0.9.0/FLINT3.6.0 environment computed exact rational direct
power sums and source complementary formulas, then an independent integer IEEE
binary64 nearest/ties-even encoder rendered final expected scalars. The producer
did not import FateBridge, use its Horner routine, or call Fraction/fmpq float
conversion for expected outputs. The encoder is explicitly reused from the
preceding fixed varga benchmark, not counted as a second independent reference.

`simon-coefficients.json` is a fresh same-agent visual re-transcription of the
six primary longitude polynomials on printed673–676/PDF11–14. The actual archived
paper SHA256 is1730fe5bb60e03d5e3a70f76b82f97dfd07bccc67a077da636a5428343e3a503;
new direct downloads returned405 and are not reported as successful. The declared
profile's exact Earth-plus180 solar antipode and TT-for-TDB numerical substitution
are separate implementation policies, not new solar ephemeris or clock claims.

`nathonnatha-source.json` identifies the selected Santhanam BPHS volumeI
27.8–9, printed268/PDF267. For supplied apparent solar meridian angle with shortest
arcA, the night group receivesA/3, day group60-A/3 and Mercury60. Both final source
formulas are independently rounded; no intermediate displayed complement is used.

The original5608solar cases and4664Nathonnatha cases/19600failed scalar fields are
retained, with all inputs and outputs, outside the repository at
`/Users/thomas/.codex/artifacts/fatebridge-jyotish-complement-precision-20261112/`.
After the arithmetic fix all four fixed batches match. Ordinary tests read
frozen expectations; they do not regenerate them from production.

Mean inputs include fixed100-day spacing, separately seeded batches and binary
neighbours of independently selected exact Earth half-turn roots. Natha inputs
include source cardinal controls, neighbouring/subnormal values, periodic finite
angles and separately seeded physical-range pairs. These are mathematical
controls, not observed birth samples or a real-world failure-rate estimate.

This is finite arithmetic acceptance for the declared models. Primary review is
by the same agent, not a second expert. Physical TT/TDB/apparent-time accuracy,
complete Shadbala, author unanimity, predictions and universal SOTA remain unproven.

Primary sources and arithmetic reference:

- [Simon et al.(1994)](https://articles.adsabs.harvard.edu/pdf/1994A%26A...282..663S)
- [Selected Santhanam volumeI scan](https://elibraryofyoga.com/bitstreams/0a9652fc-4c10-4904-82bd-7e0c331f1961/download)
- [python-flint rational arithmetic](https://python-flint.readthedocs.io/en/latest/fmpq.html)
