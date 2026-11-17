# Varga exact source-table and floating-coordinate reference

Inputs, criteria and expected values were frozen before the production
arithmetic change on 2026-11-12. `source.json.gz` packages those complete
13,498-angle development and 1,280-angle validation sets,
each evaluated for D1, D2, D3, D7, D9, D10, D12 and D30: 118,224 pairs and
472,896 overlapping field checks. These are component controls, not birth or
prediction samples. No cases were selected after observing a passing result.

The generator ran in a new isolated python-flint0.9.0 / FLINT3.6.0 environment,
with no FateBridge imports. Independent exact `fmpq` arithmetic and integer
IEEE binary64 encoding retain the supplied rational/binary input until final
rounding. The existing half-open display clamp is applied separately. D30
has only a source sign, no invented degree or longitude.

`source-tables.json` records the selected Santhanam BPHS volume1 chapter6
tables. The complete scan SHA256 is
`13609f1af89541e070c798b8c70c6bfd74a8b9a71a71388913bf898e9f9ddf3f`.
The same source PDF was fetched again and its seven pages re-viewed; this is
same-agent source collation, not a second independent expert. The displayed
linear coordinate convention is not a physical sky coordinate or a precision
claim made by the book. See `criteria.json` for the frozen scope and seeds.

The old producer failed 251 final-coordinate values and overflowed for16
valid rational-input/division pairs; all315 failed fields and original data
are retained outside the repository in
`/Users/thomas/.codex/artifacts/fatebridge-jyotish-varga-and-role-census-20261112/`.
Ordinary tests read this frozen reference and never regenerate expectations.
The source, generator, original failures and native-library receipts remain
in that evidence directory. This does not certify the whole original book,
every astronomical model, all source variants, empirical prediction or SOTA.

Primary references:

- https://elibraryofyoga.com/items/13b2600f-95fd-4bb5-86b4-a18396c68993/full
- https://python-flint.readthedocs.io/en/latest/fmpq.html
- https://flintlib.org/doc/fmpq/index.html
