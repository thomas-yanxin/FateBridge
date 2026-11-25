"""PREP: one released independent Arb traversal of frozen T inputs.

No project, native, test or candidate imports. Old root strings are untrusted
bracket proposals. Every accepted target needs independent interval signs.
"""

import argparse
from collections import Counter
from decimal import Decimal, localcontext
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import traceback


HERE = Path(__file__).resolve().parent
BITS = (256, 512, 1024)
RADII_DEGREES = tuple(Fraction(1, 1 << power) for power in (128, 96, 64))
MAX_BISECTIONS = 384
MAX_ENDPOINT_STEPS = 256
PHASE_WIDTH = Fraction(1, 10**35)
SOFT_SECONDS = 15 * 60
SELF_STOP_SECONDS = 43 * 60
EXPECTED = 63282
EXPECTED_DEFINED = 61074


def input_budget(longitude):
    """Resolve exact supplied angular scale with integer comparisons only."""
    magnitude = abs(longitude)
    if magnitude == 0 or magnitude >= 1:
        scale_bits = 0
    else:
        scale_bits = max(0, magnitude.denominator.bit_length() -
                         magnitude.numerator.bit_length())
        if magnitude.numerator << scale_bits < magnitude.denominator:
            scale_bits += 1
    precision = list(BITS)
    needed = scale_bits + 256
    if needed > BITS[-1]:
        precision.append(1 << (needed - 1).bit_length())
    return {
        "input_scale_bits": scale_bits, "precision_bits": precision,
        "bisection_cap": MAX_BISECTIONS + scale_bits,
        "endpoint_step_cap": MAX_ENDPOINT_STEPS + scale_bits,
        "policy": "ceil(-log2(abs(exact_longitude))) plus fixed original guards",
    }


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def verify(bindings):
    return [dict(expected=row, actual=identity(Path(row["path"])))
            for row in bindings if identity(Path(row["path"])) != row]


def origins():
    return {
        name: str(Path(module.__file__).absolute())
        for name, module in sorted(sys.modules.items())
        if getattr(module, "__file__", None)
    }


def unbound(origins_map, bindings):
    expected = {str(Path(row["path"]).resolve()): row for row in bindings}
    missing = []
    for name, path in origins_map.items():
        resolved = str(Path(path).resolve())
        if resolved not in expected:
            missing.append({"module": name, "path": path, "resolved": resolved})
    return missing


def load_rows(path):
    return [json.loads(line) for line in gzip.decompress(path.read_bytes()).splitlines()]


def decimal(value):
    with localcontext() as context:
        context.prec = 100
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def ratio(row, name):
    return Fraction(row[name]["exact_ratio"])


def model_trig(p, t, e):
    key = (int(ctx.prec), p, t, e)
    if key not in MODEL_CACHE:
        sp, cp = P.sincos(p)
        st, ct = P.sincos(t)
        se, ce = P.sincos(e)
        MODEL_CACHE[key] = (sp, cp, st, ct, se, ce)
    return MODEL_CACHE[key]


def solve(row, hint, budget):
    """Certify the physical quadrant and roots, then certify their delivery."""
    p, t, e = (ratio(row, name) for name in ("latitude", "armc", "obliquity"))
    longitude = (Fraction(row["longitude_exact"])
                 if "longitude_exact" in row else ratio(row, "longitude"))
    if abs(p) >= 90:
        raise P.Uncertified("native pole convention is not numerical geometry")
    sp, cp, st, ct, se, ce = model_trig(p, t, e)
    if P.sign(cp) != 1:
        raise P.Uncertified("positive nonpolar latitude cosine not certified")
    sl, cl = P.sincos(longitude)
    ray = [cl, ce * sl, se * sl]
    east_axis = [-st, ct, arb(0)]
    meridian_axis = [ct, st, arb(0)]
    if t % 360 == 90:
        height = P.sincos(p - e)[1] * sl
        height_identity = "cardinal_ARMC90_cos(p-e)*sin(longitude)"
    elif t % 360 == 270:
        height = -P.sincos(p + e)[1] * sl
        height_identity = "cardinal_ARMC270_-cos(p+e)*sin(longitude)"
    else:
        height = P.dot(ray, [cp * ct, cp * st, sp])
        height_identity = "up_axis_dot_ecliptic_ray"
    height_sign = P.sign(height)
    above = height_sign >= 0
    if not above:
        ray = [-value for value in ray]
        height = -height
    east = P.dot(ray, east_axis)
    east_sign = P.sign(east)
    western = east_sign < 0
    if western:
        ray = [value - 2 * east * axis for value, axis in zip(ray, east_axis)]
        east = -east
    a = cp * east
    b = cp * P.dot(ray, meridian_axis)
    c = sp * ray[2]
    a_sign, height_sign = P.sign(a), P.sign(height)
    if a_sign < 0 or height_sign < 0:
        raise P.Uncertified("reflected endpoint prerequisites not certified")
    evaluations = 0
    exact_angle = None
    amplitude = None
    if longitude % 180 == 0:
        exact_angle, amplitude = longitude, arb(1)
    elif p == 0 and longitude % 180 == 90:
        exact_angle, amplitude = longitude, ce
    if exact_angle is not None:
        if P.sign(amplitude) != 1:
            raise P.Uncertified("analytic angle requires certified positive amplitude")
        if not above:
            exact_angle += 180
        if western:
            exact_angle = 2 * t - exact_angle

    def residual(y):
        nonlocal evaluations
        evaluations += 1
        if y == 0:
            return a
        if y == 1:
            return -height
        # These premises prove an equatorial angle that is exactly rational.
        # They are symbolic identities, never an epsilon replacement of zero.
        if exact_angle is not None:
            return cp * amplitude * P.sincos(exact_angle - t - 90 * y)[0]
        sy, cy = P.sincos(t + 90 * y)
        normal = [-cp * sy, cp * cy, -sp * P.ball(y)]
        return P.dot(normal, ray)

    endpoints = []
    if a_sign == 0:
        endpoints.append(Fraction(0))
    if height_sign == 0:
        endpoints.append(Fraction(1))
    seed_attempts = []
    bisections = 0
    if a_sign == 0 and height_sign == 0:
        side = P.sign(c)
        if not side:
            raise P.Uncertified("continuum of position-line roots; no unique limit")
        left = right = Fraction(1 if side > 0 else 0)
        kind = "endpoint_limit"
    elif a_sign == 0 and P.sign(-b * arb.pi() / 2 - c) <= 0:
        left = right = Fraction(0)
        kind = "meridian_endpoint"
    elif height_sign == 0 and P.sign(-a * arb.pi() / 2 - c) <= 0:
        left = right = Fraction(1)
        kind = "horizon_endpoint"
    else:
        left, right = Fraction(0), Fraction(1)
        seeded = False
        if hint is not None:
            proposed_y = Fraction(hint["selected_root_degrees"]) / 90
            for radius in RADII_DEGREES:
                lower = max(Fraction(0), proposed_y - radius / 90)
                upper = min(Fraction(1), proposed_y + radius / 90)
                if not lower < upper:
                    seed_attempts.append({"radius_degrees": P.qtext(radius), "status": "outside_quadrant"})
                    continue
                try:
                    lower_sign, upper_sign = P.sign(residual(lower)), P.sign(residual(upper))
                except P.Uncertified as error:
                    seed_attempts.append({"radius_degrees": P.qtext(radius), "status": "uncertain_sign",
                                          "detail": str(error)})
                    continue
                seed_attempts.append({"radius_degrees": P.qtext(radius),
                                      "left_sign": lower_sign, "right_sign": upper_sign})
                if lower_sign > 0 and upper_sign < 0:
                    left, right, seeded = lower, upper, True
                    break
        if not seeded:
            if a_sign == 0:
                for step in range(1, budget["endpoint_step_cap"] + 1):
                    left = Fraction(1, 1 << step)
                    if P.sign(residual(left)) > 0:
                        break
                else:
                    raise P.Uncertified("positive side after meridian endpoint unresolved")
            if height_sign == 0:
                for step in range(1, budget["endpoint_step_cap"] + 1):
                    right = 1 - Fraction(1, 1 << step)
                    if P.sign(residual(right)) < 0:
                        break
                else:
                    raise P.Uncertified("negative side before horizon endpoint unresolved")
        kind = "positive_to_negative_interior"

    analytic_root = None
    if exact_angle is not None and left != right:
        rational_root = (exact_angle - t) % 180
        if not 0 < rational_root < 90:
            raise P.Uncertified("analytic root contradicts selected interior branch")
        selected_y = rational_root / 90
        if not left <= selected_y <= right or P.sign(residual(selected_y)) != 0:
            raise P.Uncertified("analytic root not certified inside accepted bracket")
        left = right = selected_y
        analytic_root = {
            "identity": "positive cos(phi)*amplitude*sin(alpha-theta-90*y)",
            "transformed_equatorial_angle_degrees": P.qtext(exact_angle),
            "amplitude": P.interval(*P.bounds(amplitude)),
            "root_degrees_exact": P.qtext(rational_root),
            "selected_y_exact": P.qtext(selected_y),
            "uniqueness": "one sine zero in the open physical quadrant",
        }

    def restored(lo, hi):
        lo, hi = (-hi, -lo) if western else (lo, hi)
        if not above:
            lo, hi = lo + 2, hi + 2
        return 90 * lo - 90, 90 * hi - 90

    # All house boundaries correspond to rational y=k/3 in this quadrant.
    # A proven exact zero is an exact root, not a rounded boundary hint.
    if left != right:
        for boundary in (Fraction(1, 3), Fraction(2, 3)):
            if left <= boundary <= right:
                try:
                    exact_sign = P.sign(residual(boundary))
                except P.Uncertified:
                    continue
                if exact_sign == 0:
                    left = right = boundary
                    break
    last_error = None
    while True:
        lower, upper = restored(left, right)
        try:
            if upper - lower > PHASE_WIDTH:
                raise P.Uncertified("reference phase width exceeds1e-35degree")
            profile = P.phase_record(lower, upper)
            root_rne = P.nearest(90 * left, 90 * right)
            break
        except P.Uncertified as error:
            last_error = {"reason": str(error), "detail": error.detail}
            if left == right or bisections >= budget["bisection_cap"]:
                raise P.Uncertified("phase/house/RNE certification exhausted", last_error)
        middle = (left + right) / 2
        side = P.sign(residual(middle))
        bisections += 1
        if side == 0:
            left = right = middle
        elif side > 0:
            left = middle
        else:
            right = middle
    if left != right and not (P.sign(residual(left)) > 0 and P.sign(residual(right)) < 0):
        raise P.Uncertified("final residual sign bracket not certified")
    candidates = [(endpoint, endpoint) for endpoint in endpoints]
    if kind == "positive_to_negative_interior":
        candidates.append((left, right))
    candidates.sort()
    candidate_profiles = [P.phase_record(*restored(lo, hi)) for lo, hi in candidates]
    candidate_rnes = [P.nearest(90 * lo, 90 * hi) for lo, hi in candidates]
    midpoint = (left + right) / 2
    final_residuals = []
    for label, y in (("left", left), ("right", right)):
        enclosure = residual(y)
        final_residuals.append({
            "side": label, "y_exact": P.qtext(y),
            "residual": P.interval(*P.bounds(enclosure)),
            "certified_sign": P.sign(enclosure),
        })
    coefficient_abs = []
    for coefficient in (a, b, c):
        lo, hi = P.bounds(coefficient)
        coefficient_abs.append(max(abs(lo), abs(hi)))
    derivative_upper = P.bounds(
        arb.pi() / 2 * P.ball(coefficient_abs[0] + coefficient_abs[1]) +
        P.ball(coefficient_abs[2])
    )[1]
    if derivative_upper <= 0:
        raise P.Uncertified("positive derivative magnitude bound not certified")
    boundary_separation = []
    for boundary in (Fraction(0), Fraction(1, 3), Fraction(2, 3), Fraction(1)):
        enclosure = residual(boundary)
        lo, hi = P.bounds(enclosure)
        side = 1 if lo > 0 else -1 if hi < 0 else 0 if lo == hi == 0 else None
        minimum = min(abs(lo), abs(hi)) if side in (-1, 1) else Fraction(0)
        distance = minimum / derivative_upper
        separation_bits = None
        if distance > 0:
            separation_bits = max(
                0, distance.denominator.bit_length() - distance.numerator.bit_length())
            if distance.numerator << separation_bits < distance.denominator:
                separation_bits += 1
            separation_bits += 1
        boundary_separation.append({
            "boundary_y_exact": P.qtext(boundary),
            "residual": P.interval(lo, hi), "certified_sign": side,
            "root_distance_y_lower_bound": P.qtext(distance),
            "unit_bracket_bisections_for_width_below_distance": separation_bits,
            "basis": "|F(boundary)|/sup|dF/dy| mean-value theorem; zero means no positive separation certified",
        })
    # Decimal fields remain convenient compatibility views of certified bounds.
    # Strict ownership/rounding derives exclusively from interval/bit records.
    value = dict(
        status="defined",
        phase_degrees=decimal((Fraction(profile["phase_degrees"]["lower"]) +
                               Fraction(profile["phase_degrees"]["upper"])) / 2),
        house_position=profile["half_open_delivery"]["value"], house=profile["house"],
        above_horizon=above, reflected_western=western,
        selected_root_degrees=decimal(90 * midpoint),
        candidate_root_degrees=[decimal(45 * (lo + hi)) for lo, hi in candidates],
        candidate_positions=[target["half_open_delivery"]["value"] for target in candidate_profiles],
        root_selection=kind,
        unshifted_continuous=profile,
        selected_root_rne=root_rne,
        candidate_root_rne=candidate_rnes,
        candidate_profiles=candidate_profiles,
        certificate=dict(
            formulation="independent vector moving-plane normal dot reflected ray",
            conditional_uniqueness="f/cos derivative monotonicity under certified a>=0 and b+c>=0",
            nonnegative_height_sign=height_sign, nonnegative_a_sign=a_sign,
            height_sum_identity="b+c equals reflected up-axis dot ray; east reflection preserves up dot ray",
            height_identity=height_identity, latitude_exact=P.qtext(p), longitude_exact=P.qtext(longitude),
            selected_y=P.interval(left, right), admissible_endpoint_y=[P.qtext(x) for x in endpoints],
            a=P.interval(*P.bounds(a)), b=P.interval(*P.bounds(b)), c=P.interval(*P.bounds(c)),
            height=P.interval(*P.bounds(height)), seed_attempts=seed_attempts,
            seeded=bool(seed_attempts and any(s.get("left_sign") == 1 and s.get("right_sign") == -1 for s in seed_attempts)),
            bisections=bisections, residual_evaluations=evaluations,
            input_derived_budget=budget, analytic_root=analytic_root,
            final_residual_endpoints=final_residuals,
            derivative_magnitude_y_upper=P.qtext(derivative_upper),
            natural_boundary_separation=boundary_separation,
            geometric_phase_unshifted=True, mathematical_half_open_house=True,
            candidate_position_policy="certified RNE followed by ownership-preserving half-open delivery",
        ),
    )
    return value


def evaluate(row, hint):
    base = {key: row[key] for key in ("ordinal", "id", "model_id", "probe") if key in row}
    base["population"] = row["population"]
    if "longitude" in row:
        base["longitude"] = float.fromhex(row["longitude"]["hex"])
    if abs(ratio(row, "latitude")) == 90:
        return dict(base, status="native_geographic_pole_convention_not_requalified",
                    numerical_pass=False, working_bits=[], input=row)
    attempts = []
    longitude = (Fraction(row["longitude_exact"])
                 if "longitude_exact" in row else ratio(row, "longitude"))
    budget = input_budget(longitude)
    for bits in budget["precision_bits"]:
        with ctx.workprec(bits):
            try:
                answer = solve(row, hint, budget)
            except P.Uncertified as error:
                attempts.append({"bits": bits, "reason": str(error), "detail": error.detail})
                continue
        return dict(base, **answer, working_bits=[bits], prior_precision_attempts=attempts)
    return dict(base, status="uncertified", input=row, precision_attempts=attempts,
                input_derived_budget=budget, numerical_pass=False)


def main(release, output):
    output.mkdir(exist_ok=False)
    bindings = release["bindings"]
    pre = {"drift": verify(bindings), "runtime_origins": origins(),
           "unbound_runtime_origins": unbound(origins(), bindings),
           "executable": sys.executable, "flags": repr(sys.flags),
           "flint_version": flint.__version__, "FLINT_version": flint.__FLINT_VERSION__}
    write(output / "preflight.json", pre)
    if pre["drift"] or pre["unbound_runtime_origins"]:
        raise RuntimeError("preflight bindings or module origins are not frozen")
    inputs = HERE / "inputs"
    large = load_rows(inputs / "expanded-63264.jsonl.gz")
    endpoint_rows = load_rows(inputs / "endpoint-16.jsonl.gz")
    antipodes = load_rows(inputs / "antipode-old-pair-2.jsonl.gz")
    hints = {row["id"]: row for row in load_rows(inputs / "untrusted-root-hints-61056.jsonl.gz")}
    assert len(large) == 63264 and len(hints) == 61056
    assert Counter(row["old_status"] for row in large) == {
        "defined": 61056, "native_geographic_pole_convention_not_requalified": 2208}
    assert len(endpoint_rows) == 16 and len(antipodes) == 2
    all_rows = []
    for label, population in (("large", large), ("endpoint", endpoint_rows), ("antipode", antipodes)):
        all_rows.extend(dict(row, population=label) for row in population)
    assert len(all_rows) == EXPECTED
    assert len({(row["population"], row["id"]) for row in all_rows}) == EXPECTED
    assert {row["id"] for row in large if row["old_status"] == "defined"} == set(hints)
    started = time.monotonic()
    counts, populations, completed = Counter(), Counter(), 0
    first_error = None
    budget_exhausted = False
    try:
        with (output / "reference.jsonl").open("x") as stream:
            for row in all_rows:
                elapsed = time.monotonic() - started
                if elapsed >= SELF_STOP_SECONDS:
                    budget_exhausted = True
                if budget_exhausted:
                    result = {"id": row["id"], "ordinal": row["ordinal"],
                              "population": row["population"], "status": "not_evaluated_wall_budget",
                              "input": row, "numerical_pass": False}
                else:
                    result = evaluate(row, hints.get(row["id"]))
                stream.write(json.dumps(result, ensure_ascii=False) + "\n")
                counts[result["status"]] += 1
                populations[row["population"]] += 1
                completed += 1
                if completed % 256 == 0:
                    stream.flush()
                    write(output / "progress.json", {
                        "completed": completed, "expected": EXPECTED,
                        "elapsed_seconds": time.monotonic() - started,
                        "soft_budget_exceeded": elapsed >= SOFT_SECONDS,
                        "counts": dict(counts), "budget_exhausted": budget_exhausted})
    except Exception as error:
        first_error = {"type": type(error).__name__, "message": str(error),
                       "traceback": traceback.format_exc(), "completed": completed}
        write(output / "first-error.json", first_error)
        raise
    finally:
        runtime = origins()
        drift = verify(bindings)
        write(output / "runtime-origins.json", runtime)
        write(output / "postflight.json", {
            "drift": drift, "unbound_runtime_origins": unbound(runtime, bindings)})
        write(output / "summary.json", {
            "expected_outer": EXPECTED, "expected_numeric": EXPECTED_DEFINED,
            "completed": completed, "counts": dict(counts), "populations": dict(populations),
            "elapsed_seconds": time.monotonic() - started, "budget_exhausted": budget_exhausted,
            "first_error": first_error, "drift": drift,
            "candidate_native_product_test_calls": 0,
            "scope": "fixed supplied-argument continuous T geometry and delivery only; not whole-book/physical/SOTA"})
        write(output / "result-seal.json", {
            "outputs": [identity(path) for path in sorted(output.iterdir()) if path.is_file()]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    release = json.loads(args.release.read_text())
    if not args.execute or release["state"] != "ROOT_RELEASED":
        parser.error("PREP only; one explicit root release is required")
    if verify(release["bindings"]):
        raise RuntimeError("pre-import release binding drift")
    import flint
    from flint import arb, ctx, fmpq
    spec = importlib.util.spec_from_file_location("fatebridge_independent_interval_primitives", HERE / "interval_primitives.py")
    P = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = P
    spec.loader.exec_module(P)
    P.arb, P.fmpq = arb, fmpq
    MODEL_CACHE = {}
    main(release, args.output)
