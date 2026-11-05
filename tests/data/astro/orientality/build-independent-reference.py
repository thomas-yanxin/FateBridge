import hashlib,json,math
from decimal import Decimal,localcontext,ROUND_FLOOR
from fractions import Fraction
from pathlib import Path
b=Path(__file__).parent
def encode(value):return {'kind':'rational','value':str(value)} if isinstance(value,Fraction) else {'kind':'float','hex':float(value).hex()}
def decimal_value(value):
 n,d=value.as_integer_ratio() if isinstance(value,float) else (value.numerator,value.denominator) if isinstance(value,Fraction) else (value,1)
 return Decimal(n)/Decimal(d)
def reference(planet,sun):
 with localcontext() as c:
  c.prec=1200;raw=decimal_value(planet)-decimal_value(sun);turns=(raw/Decimal(360)).to_integral_value(rounding=ROUND_FLOOR);phase=raw-Decimal(360)*turns
  return None if phase==0 else 'occidental' if phase<180 else 'oriental'
rows=[]
def add(name,planet,sun,expected):
 assert reference(planet,sun)==expected,(name,planet,sun,reference(planet,sun),expected)
 rows.append({'id':name,'planet':encode(planet),'sun':encode(sun),'expected':expected})
for anchor in [-720.0,-360.0,0.0,30.0,90.0,180.0,270.0,360.0,720.0]:
 key=anchor.hex();add(key+'-equal',anchor,anchor,None)
 for direction,label in [(-math.inf,'oriental'),(math.inf,'occidental')]:add(key+'-conjunction-neighbour-'+label,math.nextafter(anchor,direction),anchor,label)
 opposite=anchor+180
 add(key+'-antipodal-legacy-tie',opposite,anchor,'oriental')
 for direction,label in [(-math.inf,'occidental'),(math.inf,'oriental')]:add(key+'-opposition-neighbour-'+label,math.nextafter(opposite,direction),anchor,label)
 for gap in [Fraction(1,1000),Fraction(1,10000),Fraction(1,100000),Fraction(1,2**90)]:
  add(key+'-rational-before-'+str(gap),Fraction(anchor)-gap,Fraction(anchor),'oriental');add(key+'-rational-after-'+str(gap),Fraction(anchor)+gap,Fraction(anchor),'occidental')
for turns in [-1000,-2,-1,0,1,2,1000]:
 for gap,label in [(Fraction(-1,2**90),'oriental'),(Fraction(1,2**90),'occidental')]:add(f'wrapped-{turns}-{label}',Fraction(360*turns)+gap,Fraction(0),label)
result={'production_imports':False,'reference_arithmetic':'Decimal1200digits, floor quotient, checked against predeclared literal neighbour-side labels; binary values and rational intentions retained separately','opposition_tie':'Existing shared-helper oriental tie retained for compatibility; not source-specific endpoint acceptance','source_pages':[114],'cases':rows}
(b/'independent-angle-reference.json').write_text(json.dumps(result,indent=2)+'\n');(b/'reference-seal.json').write_text(json.dumps({'independent-angle-reference.json':hashlib.sha256((b/'independent-angle-reference.json').read_bytes()).hexdigest()},indent=2)+'\n');print('frozen independent literal cases',len(rows))
