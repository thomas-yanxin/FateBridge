# Temporal Gregorian and zone reference

The 4,392 inputs were frozen before this calendar refactor. The reference uses
`@js-temporal/polyfill@0.5.1` with Node 22.22.2, ICU 78.2 and timezone data 2025c.
Every case retains its UTC input, zone, epoch microseconds, seven local fields
and UTC offset. Comparison requires exact integer/field/offset equality.
This validates the selected Gregorian and zone models, not observed ancient
clocks, future timezone law, astronomical precision or prediction.

The package lock retains the npm archive integrity values. In a temporary
directory, copy these generator files, run `npm ci`, then `node reference.mjs`.
`reference-output.json` contains the raw reference; the frozen compressed oracle
also includes provenance and a scope statement. Do not regenerate expected
values from FateBridge. The uncompressed plan SHA-256 is retained in the oracle.

Primary references: [Temporal polyfill v0.5.1](https://github.com/js-temporal/temporal-polyfill/tree/v0.5.1)
and [Temporal ZonedDateTime](https://tc39.es/proposal-temporal/docs/zoneddatetime.html).
