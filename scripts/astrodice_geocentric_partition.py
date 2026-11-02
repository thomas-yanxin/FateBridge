"""Certified monotone rejection of complete constant-elapsed pair groups.

The caller must supply a uniform derivative sign on the full time/delay box.
No point is discarded from the population; exclusions retain boundary proofs.
"""

from collections import defaultdict
from fractions import Fraction as Q


def partition_pairs(pairs, increasing, target, evaluate):
    groups = defaultdict(list)
    for i, (tr, te) in enumerate(pairs):
        groups[Q(tr) - Q(te)].append(i)
    records = []
    retained = []
    lower, upper = target if increasing else (-target[1], -target[0])
    for delay, indices in sorted(groups.items()):
        indices.sort(key=lambda i: Q(pairs[i][0]))
        if len({pairs[i][0] for i in indices}) != len(indices):
            raise ValueError("Repeated receiver in a constant-elapsed group")
        cache = {}

        def raw(k):
            if k not in cache:
                cache[k] = evaluate(pairs[indices[k]][0], delay)
            return cache[k]

        def oriented(k):
            a, b = raw(k)
            return (a, b) if increasing else (-b, -a)

        low, high = 0, len(indices)
        while low < high:
            mid = (low + high) // 2
            if oriented(mid)[1] < lower:
                low = mid + 1
            else:
                high = mid
        first = low
        low, high = 0, len(indices)
        while low < high:
            mid = (low + high) // 2
            if oriented(mid)[0] > upper:
                high = mid
            else:
                low = mid + 1
        last = low
        if first > last:
            raise ValueError("Uniform source monotonicity contradicted")
        retained.extend(indices[first:last])
        records.append(
            {
                "elapsed_raw": str(delay),
                "pair_indices": indices,
                "first_retained": first,
                "last_retained_exclusive": last,
                "below_witness": (
                    None
                    if first == 0
                    else {
                        "group_index": first - 1,
                        "range_squared_bounds": list(map(str, raw(first - 1))),
                    }
                ),
                "above_witness": (
                    None
                    if last == len(indices)
                    else {
                        "group_index": last,
                        "range_squared_bounds": list(map(str, raw(last))),
                    }
                ),
            }
        )
    return {
        "groups": records,
        "retained_pair_indices": sorted(retained),
        "excluded_pair_count": len(pairs) - len(retained),
        "full_pair_population": len(pairs),
    }
