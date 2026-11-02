"""Analytic exhaustive controls for complete monotone pair partitions."""

import copy
from fractions import Fraction as Q

import pytest

from scripts.astrodice_geocentric_partition import partition_pairs
from scripts.verify_astrodice_geocentric_partition import check_partition


@pytest.mark.parametrize("increasing", (True, False))
@pytest.mark.parametrize(
    "target", ((Q(20), Q(21)), (Q(-100), Q(-90)), (Q(100), Q(101)))
)
def test_group_certificates_preserve_the_exhaustive_necessary_set(increasing, target):
    pairs = [(float(t), float(t - d)) for t in range(10, 25) for d in (3, 5)]
    sign = 1 if increasing else -1

    def evaluate(tr, delay):
        value = sign * Q(tr) + 2 * delay
        return value - Q(1, 4), value + Q(1, 4)

    result = partition_pairs(pairs, increasing, target, evaluate)
    exhaustive = [
        i
        for i, (tr, te) in enumerate(pairs)
        if evaluate(tr, Q(tr) - Q(te))[0] <= target[1]
        and target[0] <= evaluate(tr, Q(tr) - Q(te))[1]
    ]
    assert result["retained_pair_indices"] == exhaustive
    assert check_partition(pairs, increasing, target, evaluate, result) == exhaustive
    assert result["excluded_pair_count"] + len(exhaustive) == len(pairs)


@pytest.mark.parametrize(
    "mutation", ("drop_group", "membership", "false_exclusion", "drop_retained")
)
def test_independent_partition_replay_rejects_lost_coverage(mutation):
    pairs = [(float(t), float(t - 2)) for t in range(10)]

    def evaluate(tr, delay):
        return Q(tr), Q(tr)

    result = copy.deepcopy(partition_pairs(pairs, True, (Q(4), Q(6)), evaluate))
    if mutation == "drop_group":
        result["groups"].pop()
    elif mutation == "membership":
        result["groups"][0]["pair_indices"].pop()
    elif mutation == "false_exclusion":
        result["groups"][0]["first_retained"] += 1
        result["groups"][0]["below_witness"]["group_index"] += 1
    else:
        result["retained_pair_indices"].pop()
    with pytest.raises(ValueError):
        check_partition(pairs, True, (Q(4), Q(6)), evaluate, result)
