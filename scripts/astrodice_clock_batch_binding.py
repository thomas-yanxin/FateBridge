"""Require identical wire time batches before transferring a source clock.

An equal numeric label alone cannot bind different TLIST evaluation contexts.
This is a necessary request-identity guard, not physical clock certification.
"""

TIME_KEYS = (
    "TIME_TYPE",
    "CAL_TYPE",
    "TIME_DIGITS",
    "CAL_FORMAT",
    "TLIST_TYPE",
    "TLIST",
)


def time_batch(query):
    parameters = query["parameters"]
    if any(
        not isinstance(parameters.get(k), str) or not parameters[k].strip()
        for k in TIME_KEYS
    ):
        raise ValueError("Incomplete explicit time-batch contract")
    return {k: parameters[k] for k in TIME_KEYS}


def matching_time_batches(observer_query, vector_query):
    return time_batch(observer_query) == time_batch(vector_query)


def require_matching_time_batches(observer_query, vector_query):
    if not matching_time_batches(observer_query, vector_query):
        raise ValueError("Cross-batch source-clock transfer is unqualified")
