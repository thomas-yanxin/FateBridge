# Primary-direction nominal event-clock controls

The 48 controls cover eight explicit zones, three time keys and two directions using the static-axis/Tropic path. Frozen FateBridge NativeSubject operands isolate the event-clock calculation; these are clock controls rather than independent celestial observations.

Expected instants and offsets come from @js-temporal/polyfill 0.5.1 with jsbi 4.3.2. Node 22.22.2, ICU 78.2, tzdata 2025c and package identities are recorded in source.json. Reference ages are decoded with JavaScript BigInt from IEEE inputs, multiplied by the declared 31556952 nominal seconds per year and rounded once to integer microseconds. Temporal performs the instant/timezone conversion and ignores leap seconds. Offsets come from numeric offsetNanoseconds; human ZonedDateTime display text can round historical second offsets to minutes and is not parsed as the oracle.

The fixed tolerance permits one second of text truncation plus ten microseconds for the existing float-duration representation. The fixture is loaded only by tests. TT and UT1 operands use the current NativeSubject carriers, with exact rational day values preserving each original binary64 epoch.

The stored ages record the former calculation, which rounded intermediate angles. The regression independently forms and divides the directed arc over the same binary64 operands before rounding the delivered age. It retains every original event identity, Temporal instant, offset and clock tolerance.

Primary definitions: [Temporal.Instant](https://tc39.es/proposal-temporal/docs/instant.html) and [Python datetime arithmetic](https://docs.python.org/3.12/library/datetime.html).
