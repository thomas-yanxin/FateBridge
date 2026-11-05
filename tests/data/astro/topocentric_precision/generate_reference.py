"""Independent vector reference for the declared T physical-quadrant policy.

No native/application imports. Unclipped geographic latitude is used in the
position-line normal. A false-position solver is followed by a strict sign
bracket check. All roots admissible in the selected physical quadrant are
retained; a meridian endpoint can coexist with an interior root.
"""

from __future__ import annotations

import gzip
import json
import math
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

from mpmath import mp

HERE = Path(__file__).resolve().parent


def geometry(case, digits):
    ctx = mp.clone()
    ctx.dps = digits
    p, t, e = [ctx.mpf(case[k]) for k in ("latitude", "armc", "obliquity")]
    cp, sp = ctx.cospi(p/180), ctx.sinpi(p/180)
    ct, st = ctx.cospi(t/180), ctx.sinpi(t/180)
    ce, se = ctx.cospi(e/180), ctx.sinpi(e/180)
    up = [cp*ct, cp*st, sp]
    east = [-st, ct, ctx.mpf(0)]
    ecliptic = [ctx.mpf(0), -se, ce]

    def dot(a, b):
        return ctx.fsum(x*y for x,y in zip(a,b))

    def cross(a, b):
        return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]

    def body(longitude):
        lam = ctx.mpf(longitude)
        return [ctx.cospi(lam/180),ctx.sinpi(lam/180)*ce,ctx.sinpi(lam/180)*se]

    def altitude(v, longitude):
        # Exact cardinal identities avoid manufacturing a side of the horizon
        # from rounding of an exactly zero trigonometric expression.
        lam = ctx.mpf(longitude)
        if t % 360 == 90:
            b = ctx.cospi((p-e)/180)
        elif t % 360 == 270:
            b = -ctx.cospi((p+e)/180)
        else:
            b = cp*st*ce+sp*se
        return cp*ct*ctx.cospi(lam/180)+b*ctx.sinpi(lam/180)

    def formal_cusps():
        horizon = cross(ecliptic,up)
        orientation = ctx.sign(dot(horizon,east))
        if not orientation:
            raise ArithmeticError("Formal T cusp orientation is unresolved")
        result = []
        for house in range(1,13):
            psi = ctx.mpf((house-10) % 12)*30
            factor = (psi/90 if psi<=90 else (180-psi)/90 if psi<=270 else (psi-360)/90)
            normal = [-cp*ctx.sinpi((t+psi)/180),cp*ctx.cospi((t+psi)/180),-sp*factor]
            ray = [orientation*x for x in cross(normal,ecliptic)]
            result.append(float(ctx.atan2(ray[1]*ce+ray[2]*se,ray[0])*180/ctx.pi)%360)
        return result

    def solve(longitude):
        v = body(longitude)
        height = altitude(v,longitude)
        above = height >= 0
        if not above:
            v = [-x for x in v]
        east_component = dot(v,east)
        western = east_component < 0
        if western:
            v = [x-2*east_component*y for x,y in zip(v,east)]
        half = ctx.pi/2
        first = cp*abs(east_component)
        last = -abs(height)

        def residual(x):
            if x == 0:
                return first
            if x == half:
                return last
            angle = t/180*ctx.pi+x
            normal = [-cp*ctx.sin(angle),cp*ctx.cos(angle),-sp*x/half]
            return dot(normal,v)

        def derivative(x):
            angle = t/180*ctx.pi+x
            normal = [-cp*ctx.cos(angle),-cp*ctx.sin(angle),-sp/half]
            return dot(normal,v)

        alternatives = []
        if first == 0:
            alternatives.append(ctx.mpf(0))
        if last == 0:
            alternatives.append(half)
        if first == 0 and last == 0:
            selected = half if residual(half/2)>0 else ctx.mpf(0)
            kind = "endpoint_limit"
        elif first == 0 and derivative(0)<=0:
            selected,kind = ctx.mpf(0),"meridian_endpoint"
        elif last == 0 and derivative(half)<=0:
            selected,kind = half,"horizon_endpoint"
        else:
            left,right = ctx.mpf(0),half
            if first == 0:
                left = half/2
                for _ in range(1000):
                    if residual(left)>0:
                        break
                    left /= 2
                else:
                    raise ArithmeticError("No positive interior side after meridian endpoint")
            if last == 0:
                delta = half/2
                for _ in range(1000):
                    right = half-delta
                    if residual(right)<0:
                        break
                    delta /= 2
                else:
                    raise ArithmeticError("No negative interior side before horizon endpoint")
            assert residual(left)>0 and residual(right)<0
            selected = ctx.findroot(residual,(left,right),solver="illinois",tol=ctx.mpf("1e-70"),maxsteps=500,verify=False)
            radius = ctx.mpf("1e-45")
            lower,upper = max(left,selected-radius),min(right,selected+radius)
            certified = (left<=selected<=right and residual(lower)>=0 and residual(upper)<=0
                         and (residual(lower)!=0 or residual(upper)!=0))
            if not certified:
                # A library proposal is not a root certificate. Retain the
                # original sign bracket and bisect this SAME query instead.
                for _ in range(1000):
                    middle=(left+right)/2
                    value=residual(middle)
                    if value>=0:
                        left=middle
                    else:
                        right=middle
                    if right-left<ctx.mpf("1e-50"):
                        break
                else:
                    raise ArithmeticError("Vector bisection did not converge")
                selected=(left+right)/2
                assert residual(left)>=0 and residual(right)<=0,(case["id"],longitude)
            alternatives.append(selected)
            kind = "positive_to_negative_interior"

        def phase(value):
            if western:
                value = -value
            if not above:
                value += ctx.pi
            return (value*180/ctx.pi-90+ctx.mpf(1)/3600000)%360

        value = phase(selected)
        house = int(ctx.floor(value/30))+1
        position = float(value/30+1)
        if math.floor(position)>house:
            position = math.nextafter(position,-math.inf)
        return dict(status="defined",phase_degrees=ctx.nstr(value,75),house_position=position,house=house,
                    above_horizon=above,reflected_western=western,selected_root_degrees=ctx.nstr(selected*180/ctx.pi,75),
                    candidate_root_degrees=[ctx.nstr(x*180/ctx.pi,75) for x in sorted(alternatives)],
                    candidate_positions=[float(phase(x)/30+1) for x in sorted(alternatives)],root_selection=kind)

    return formal_cusps,solve


def generate(item):
    case,extras = item
    if abs(case["latitude"]) == 90:
        probes = [("pole-fixed-"+str(i),float(i*7.5)) for i in range(48)]
        probes += [(p["id"],p["longitude"]) for p in extras]
        return [dict(id=case["id"]+"-"+label,model_id=case["id"],probe=label,longitude=longitude,status="native_geographic_pole_convention_not_requalified") for label,longitude in probes]
    _,low = geometry(case,80)
    formal,high = geometry(case,100)
    probes = [("fixed-"+str(i),float(i*30)) for i in range(12)]
    for index,cusp in enumerate(formal()):
        probes += [("cusp-"+str(index+1)+"-"+label,x) for label,x in (
            ("below",math.nextafter(cusp,-math.inf)),("on",cusp),("above",math.nextafter(cusp,math.inf)))]
    probes += [(p["id"],p["longitude"]) for p in extras]
    result = []
    for label,longitude in probes:
        first,second = low(longitude),high(longitude)
        ctx=mp.clone();ctx.dps=100
        assert abs((ctx.mpf(first["phase_degrees"])-ctx.mpf(second["phase_degrees"])+180)%360-180)<ctx.mpf("1e-35"),(case["id"],label)
        assert (first["above_horizon"],first["reflected_western"],len(first["candidate_root_degrees"])) == (second["above_horizon"],second["reflected_western"],len(second["candidate_root_degrees"]))
        result.append(dict(id=case["id"]+"-"+label,model_id=case["id"],probe=label,longitude=longitude,working_digits=[80,100],**second))
    return result


if __name__ == "__main__":
    cases = json.loads((HERE/"inputs.json").read_text())["cases"]
    extra = json.loads((HERE/"legacy-input-probes.json").read_text())["probes"]
    by_model = {}
    for probe in extra:
        by_model.setdefault(probe["model_id"],[]).append(probe)
    counts = Counter()
    with gzip.open(HERE/"reference.jsonl.gz","wt") as stream, Pool(2) as pool:
        for index,values in enumerate(pool.imap(generate,[(case,by_model.get(case["id"],[])) for case in cases]),1):
            for row in values:
                counts[row["status"]]+=1
                if len(row.get("candidate_root_degrees",[]))>1:
                    counts["multiple_admissible_endpoint_or_interior_candidates"]+=1
                stream.write(json.dumps(row)+"\n")
            if index%64 == 0:
                print(json.dumps(dict(completed_models=index,counts=counts)),flush=True)
    (HERE/"generation-summary.json").write_text(json.dumps(dict(models=len(cases),counts=counts,production_or_native_imports=False),indent=2)+"\n")
    print(json.dumps(dict(models=len(cases),counts=counts)),flush=True)
