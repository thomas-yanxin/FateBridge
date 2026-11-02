"""Independent coverage and monotone boundary certificate replay."""

from fractions import Fraction as Q

from scripts.verify_astrodice_observer_clock import cover


def check_partition(pairs, increasing, target, evaluate, saved):
    ordered = sorted(
        range(len(pairs)),
        key=lambda i: (Q(pairs[i][0]) - Q(pairs[i][1]), Q(pairs[i][0])),
    )
    groups = []
    for i in ordered:
        delay = Q(pairs[i][0]) - Q(pairs[i][1])
        if not groups or groups[-1][0] != delay:
            groups.append((delay, []))
        groups[-1][1].append(i)
    if len(saved["groups"]) != len(groups) or saved["full_pair_population"] != len(
        pairs
    ):
        raise ValueError("Full pair-group population changed")
    retained = []
    lower, upper = target if increasing else (-target[1], -target[0])
    for (delay, indices), record in zip(groups, saved["groups"]):
        if Q(record["elapsed_raw"]) != delay or record["pair_indices"] != indices:
            raise ValueError("Constant-elapsed partition membership changed")
        first, last = record["first_retained"], record["last_retained_exclusive"]
        if (
            type(first) is not int
            or type(last) is not int
            or not 0 <= first <= last <= len(indices)
        ):
            raise ValueError("Invalid retained pair range")
        for name, boundary in (
            ("below_witness", first - 1 if first else None),
            ("above_witness", last if last < len(indices) else None),
        ):
            witness = record[name]
            if boundary is None:
                if witness is not None:
                    raise ValueError("Invented exclusion witness")
                continue
            if witness["group_index"] != boundary:
                raise ValueError("Exclusion witness moved")
            actual = evaluate(pairs[indices[boundary]][0], delay)
            cover(actual, witness["range_squared_bounds"])
            a, b = map(Q, witness["range_squared_bounds"])
            a, b = (a, b) if increasing else (-b, -a)
            if (
                name == "below_witness"
                and not b < lower
                or name == "above_witness"
                and not a > upper
            ):
                raise ValueError("Strict monotone exclusion not proved")
        retained.extend(indices[first:last])
    retained.sort()
    if saved["retained_pair_indices"] != retained or saved[
        "excluded_pair_count"
    ] != len(pairs) - len(retained):
        raise ValueError("Retained or excluded pairs changed")
    return retained
