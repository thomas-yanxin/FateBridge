"""Independent integer-lattice reference; reads only frozen criteria/inputs.

No FateBridge imports, product output, Fraction implementation, native ephemeris,
mpmath candidate conversion or prospective fix. All finite operands are the
original binary64 integer ratios. Output doubles use explicit integer RN-even.
"""
from pathlib import Path
import hashlib
import itertools
import json
import math
import struct
import sys

HERE = Path(__file__).resolve().parent
CRITERIA_SHA = '47527c4d6438c2b895638fcc74f683ec565088ca3b075f3ee1bc4ccdebceb5b6'
INPUT_SHA = 'c4b1c02f05f95d11764b564a5b6ff43133216d0c6994ab2970bd1658f25f9ccf'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ratio(numerator, denominator):
    g = math.gcd(numerator, denominator)
    return f'{numerator // g}/{denominator // g}'


def round_quotient(numerator, denominator):
    q, r = divmod(numerator, denominator)
    return q + int(2 * r > denominator or (2 * r == denominator and q % 2 == 1))


def nearest_binary64(numerator, denominator):
    """RN-even of an exact signed rational, using no rational->float cast."""
    if denominator <= 0:
        raise ValueError('Positive rational denominator required')
    sign = int(numerator < 0)
    n = abs(numerator)
    if n == 0:
        return 0.0
    exponent = n.bit_length() - denominator.bit_length()
    if (n < denominator << exponent) if exponent >= 0 else (n << -exponent < denominator):
        exponent -= 1
    if exponent < -1022:
        significand = round_quotient(n << 1074, denominator)
        bits = (sign << 63) + significand
    else:
        shift = 52 - exponent
        significand = (
            round_quotient(n << shift, denominator)
            if shift >= 0
            else round_quotient(n, denominator << -shift)
        )
        if significand == (1 << 53):
            significand >>= 1
            exponent += 1
        if exponent > 1023:
            raise ValueError('Reference operand outside finite binary64 range')
        bits = (sign << 63) | ((exponent + 1023) << 52) | (significand - (1 << 52))
    return struct.unpack('>d', struct.pack('>Q', bits))[0]


def numeric(n, unit):
    value = nearest_binary64(n, unit)
    return {'exact': ratio(n, unit), 'nearest': value, 'nearest_hex': value.hex()}


def residue(n, period, unit):
    turn = period * unit
    half = turn // 2
    return (n + half) % turn - half


def contact(equation, delta, unit, identity, **labels):
    return {
        'equation': equation,
        'signed_orb': nearest_binary64(delta, unit),
        'orb': nearest_binary64(abs(delta), unit),
        'signed_orb_exact': ratio(delta, unit),
        'orb_exact': ratio(abs(delta), unit),
        'signed_orb_hex': nearest_binary64(delta, unit).hex(),
        'orb_hex': nearest_binary64(abs(delta), unit).hex(),
        'contains_hypothetical': False,
        'zero_arc_identity': identity,
        **labels,
    }


def reference(case):
    values = case['factor_longitudes']
    operands = [case['natal_tropical_sun'], case['progressed_tropical_sun'],
                case['orb_degrees'], *values.values()]
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in operands):
        raise ValueError('Frozen inputs must contain finite supplied doubles')
    pairs = [v.as_integer_ratio() for v in operands]
    denominator = max(d for _, d in pairs)
    if any(denominator % d for _, d in pairs):
        raise ValueError('Original binary64 ratios must share a dyadic lattice')
    # Two lattice units per smallest operand tick retain every midpoint exactly.
    unit = 2 * denominator
    def ticks(value):
        n, d = value.as_integer_ratio()
        return n * (unit // d)
    full_turn = 360 * unit
    natal = {name: ticks(value) % full_turn for name, value in values.items()}
    arc = (ticks(case['progressed_tropical_sun']) - ticks(case['natal_tropical_sun'])) % full_turn
    bound = ticks(case['orb_degrees'])
    directed = {name: (value + arc) % full_turn for name, value in natal.items()}
    names = list(values)
    named_pairs = list(itertools.combinations(names, 2))
    # Compute both layers' midpoints directly from layer coordinates, rather than
    # reusing a natal midpoint plus the arc as in the product implementation.
    midpoints = {
        layer: {pair: ((coords[pair[0]] + coords[pair[1]]) // 2) % (180 * unit)
                for pair in named_pairs}
        for layer, coords in [('natal', natal), ('solar_arc', directed)]
    }
    biwheel = {}
    for period in (90, 45):
        two, three, four = [], [], []
        for a in names:
            for b in names:
                delta = residue(directed[a] - natal[b], period, unit)
                if abs(delta) <= bound:
                    two.append(contact(f'{a}.solar_arc={b}.natal', delta, unit,
                                       arc == 0 and a == b,
                                       id_a=a, id_b=b, layer_a='solar_arc', layer_b='natal'))
        for point in names:
            for a, b in named_pairs:
                for pl, al in [('solar_arc', 'natal'), ('natal', 'solar_arc')]:
                    coordinates = directed if pl == 'solar_arc' else natal
                    delta = residue(coordinates[point] - midpoints[al][(a, b)], period, unit)
                    if abs(delta) <= bound:
                        three.append(contact(f'{point}.{pl}={a}.{al}/{b}.{al}', delta, unit,
                                             False, point=point, point_layer=pl,
                                             id_a=a, id_b=b, axis_layer=al))
        for a, b in named_pairs:
            for c, d in named_pairs:
                delta = residue(midpoints['solar_arc'][(a, b)] - midpoints['natal'][(c, d)], period, unit)
                if abs(delta) <= bound:
                    four.append(contact(f'{a}.solar_arc/{b}.solar_arc={c}.natal/{d}.natal', delta,
                                        unit, arc == 0 and (a, b) == (c, d),
                                        id_a=a, id_b=b, id_c=c, id_d=d,
                                        layer_a='solar_arc', layer_b='solar_arc',
                                        layer_c='natal', layer_d='natal'))
        biwheel[str(period)] = {
            'period_degrees': period,
            'two_factor_contacts': two, 'three_factor_contacts': three,
            'four_factor_contacts': four,
            'contact_counts': {'two_factor': len(two), 'three_factor': len(three),
                               'four_factor': len(four),
                               'zero_arc_identities': sum(r['zero_arc_identity'] for r in two + three + four)},
            'candidate_counts': {'two_factor': len(names) ** 2,
                                 'three_factor': 2 * len(names) * len(named_pairs),
                                 'four_factor': len(named_pairs) ** 2},
        }
    mixed = {str(period): {'period_degrees': period,
                          'arc_dependent_contacts': [], 'arc_invariant_contacts': []}
             for period in (90, 45)}
    partition_count = 0
    for a, b, c, d in itertools.combinations(sorted(names), 4):
        for keys in [(a, b, c, d), (a, c, b, d), (a, d, b, c)]:
            partition_count += 1
            grouped = {-1: [], 0: [], 1: []}
            # Directly evaluate all 16 layer assignments. Retain the 12 whose
            # left or right pair mixes layers; group only after evaluation.
            for bits in itertools.product((0, 1), repeat=4):
                if bits[0] == bits[1] and bits[2] == bits[3]:
                    continue
                coords = [(directed if bit else natal)[name] for name, bit in zip(keys, bits)]
                numerator = bits[0] + bits[1] - bits[2] - bits[3]
                direct_difference = (coords[0] + coords[1] - coords[2] - coords[3]) // 2
                grouped[numerator].append((bits, direct_difference))
            for numerator, group in grouped.items():
                if len(group) != 4:
                    raise ValueError('Uniform-arc mixed group must have exactly four layerings')
                for period in (90, 45):
                    all_delta = [residue(v, period, unit) for _, v in group]
                    if len(set(all_delta)) != 1:
                        raise ValueError('Equivalent declared mixed layerings disagree')
                    delta = all_delta[0]
                    if abs(delta) > bound:
                        continue
                    first, second, third, fourth = keys
                    assignments = [{name: 'solar_arc' if bit else 'natal'
                                    for name, bit in zip(keys, bits)} for bits, _ in group]
                    row = {
                        'id_a': first, 'id_b': second, 'id_c': third, 'id_d': fourth,
                        'equation': f'({first}+{second})/2=({third}+{fourth})/2; apply each factor_layers assignment',
                        'coefficient_numerator': numerator,
                        'midpoint_arc_coefficient': nearest_binary64(numerator, 2),
                        'arc_invariant': numerator == 0,
                        'signed_orb': nearest_binary64(delta, unit), 'orb': nearest_binary64(abs(delta), unit),
                        'signed_orb_exact': ratio(delta, unit), 'orb_exact': ratio(abs(delta), unit),
                        'signed_orb_hex': nearest_binary64(delta, unit).hex(),
                        'orb_hex': nearest_binary64(abs(delta), unit).hex(),
                        'factor_layer_assignments': assignments,
                        'represented_layer_assignment_count': 4,
                        'contains_hypothetical': False,
                        'zero_arc_groups_coincide': arc == 0,
                    }
                    field = 'arc_invariant_contacts' if numerator == 0 else 'arc_dependent_contacts'
                    mixed[str(period)][field].append(row)
    for dial in mixed.values():
        dependent, invariant = dial['arc_dependent_contacts'], dial['arc_invariant_contacts']
        dial['contact_counts'] = {'arc_dependent_relation_groups': len(dependent),
                                  'arc_invariant_relation_groups': len(invariant),
                                  'represented_layer_assignments': 4 * (len(dependent) + len(invariant))}
        dial['candidate_counts'] = {'pair_partitions': partition_count,
                                   'coefficient_groups': 3 * partition_count,
                                   'represented_layerings': 12 * partition_count}
    return {
        'id': case['id'], 'source_pair_index': case['source_pair_index'], 'mc_neighbor': case['mc_neighbor'],
        'source_input_hex': {'natal_tropical_sun': float(case['natal_tropical_sun']).hex(),
                             'progressed_tropical_sun': float(case['progressed_tropical_sun']).hex(),
                             'factor_longitudes': {k: float(v).hex() for k, v in values.items()}},
        'source_input_ratios': {'natal_tropical_sun': ratio(*case['natal_tropical_sun'].as_integer_ratio()),
                               'progressed_tropical_sun': ratio(*case['progressed_tropical_sun'].as_integer_ratio())},
        'arc': numeric(arc, unit),
        'rotated_factors': {name: numeric(value, unit) for name, value in directed.items()},
        'biwheel': biwheel, 'mixed_pairs': mixed,
        'arithmetic_unit_denominator': str(unit),
        'source_scope': 'Synthetic supplied binary64 operands; no ephemeris or historical/empirical sample',
    }


def main():
    if (HERE / 'reference.json').exists():
        raise ValueError('Refusing to overwrite an existing independent reference')
    if sha(HERE / 'criteria.json') != CRITERIA_SHA or sha(HERE / 'inputs.json') != INPUT_SHA:
        raise ValueError('Preregistered input/criterion identity changed')
    criteria = json.loads((HERE / 'criteria.json').read_text())
    inputs = json.loads((HERE / 'inputs.json').read_text())
    if criteria['cases'] != 18 or len(inputs['cases']) != 18 or len(inputs['source_sun_pairs']) != 6:
        raise ValueError('Original frozen population changed')
    rows = [reference(case) for case in inputs['cases']]
    imported_product_modules = sorted(name for name in sys.modules if name == 'fatebridge' or name.startswith('fatebridge.'))
    if imported_product_modules:
        raise ValueError('Reference imported product modules')
    result = {
        'reference_version': 'independent_integer_source_arc_catalogue_v1',
        'criteria_sha256': CRITERIA_SHA, 'inputs_sha256': INPUT_SHA,
        'script_sha256': sha(Path(__file__)),
        'arithmetic': 'Exact integers on dyadic source coordinates; independent quotient/remainder round-nearest-even binary64 encoder',
        'declared_dials': [90, 45], 'orb_policy': 'exact absolute residual <= original 1 degree inclusive',
        'cases': len(rows), 'source_pairs': 6, 'rows': rows,
        'read_allowlist': ['criteria.json', 'inputs.json', 'independent-reference.py'],
        'runtime': {'python': sys.version, 'product_imports': imported_product_modules,
                    'mpmath_or_product_reference_imported': False, 'external_dependencies': []},
        'qualification': 'Finite arithmetic criterion on frozen operands/catalogue, not source physics, complete historical Witte, original method interpretation or real-world predictive efficacy',
    }
    (HERE / 'reference.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'cases': len(rows), 'source_pairs': 6, 'reference_sha256': sha(HERE / 'reference.json'),
                      'reference_bytes': (HERE / 'reference.json').stat().st_size,
                      'product_imports': imported_product_modules, 'candidate_output_reads': 0}, ensure_ascii=False))


if __name__ == '__main__':
    main()
