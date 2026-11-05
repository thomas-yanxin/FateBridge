"""Fixed relationship inputs and request shapes, without reference-file I/O."""

A = dict(
    name="甲",
    birth_year=1990,
    birth_month=4,
    birth_day=6,
    birth_hour=9,
    birth_minute=33,
    birth_timezone="UTC",
    birth_longitude=179,
    birth_latitude=10,
)

B = dict(
    name="乙",
    birth_year=1992,
    birth_month=3,
    birth_day=2,
    birth_hour=8,
    birth_minute=18,
    birth_timezone="UTC",
    birth_longitude=-179,
    birth_latitude=20,
)


def payloads(mode, variant):
    nested = {
        "inner": A,
        "outer": B,
        "relative_mode": mode,
        "davison_variant": variant,
        "hsys": 0,
        "zodiacal": 1,
    }
    flat = {
        **{f"inner_{key}": value for key, value in A.items()},
        **{f"outer_{key}": value for key, value in B.items()},
        **{
            key: value for key, value in nested.items() if key not in {"inner", "outer"}
        },
    }
    return nested, flat
