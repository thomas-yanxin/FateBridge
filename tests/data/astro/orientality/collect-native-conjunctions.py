import hashlib,json,math,sys
from datetime import datetime,timedelta,timezone
from pathlib import Path
import swisseph as swe
b=Path(__file__).parent;ephe=b/'before/ephe';swe.set_ephe_path(str(ephe));flags=swe.FLG_SWIEPH|swe.FLG_SPEED
def positions(jd):
 sun,sf=swe.calc(jd,swe.SUN,flags);mercury,mf=swe.calc(jd,swe.MERCURY,flags);assert sf&swe.FLG_SWIEPH and mf&swe.FLG_SWIEPH
 raw=mercury[0]-sun[0];gap=raw+360 if raw < -180 else raw-360 if raw>180 else raw
 return gap,{'tt_jd':jd,'tt_jd_hex':jd.hex(),'sun':list(sun),'sun_return_flags':sf,'mercury':list(mercury),'mercury_return_flags':mf}
start=swe.julday(2000,1,1,0,swe.GREG_CAL);end=swe.julday(2001,1,1,0,swe.GREG_CAL);scan=[];roots=[];previous,record=positions(start);scan.append(record)
for i in range(1,int(end-start)+1):
 current,record=positions(start+i);scan.append(record)
 if previous*current < 0:
  lo,hi=start+i-1,start+i;fl,_=positions(lo)
  for _ in range(80):
   middle=(lo+hi)/2
   if middle in {lo,hi}:break
   fm,_=positions(middle)
   if fm==0:lo=hi=middle;break
   if fl*fm<0:hi=middle
   else:lo,fl=middle,fm
  jd=(lo+hi)/2;gap,root=positions(jd);root.update(bracket_tt_jd=[lo,hi],residual_longitude_degrees=gap,samples=[])
  for offset in [-30,-10,-1,0,1,10,30]:
   _,sample=positions(jd+offset/86400);sample['offset_seconds']=offset;root['samples'].append(sample)
  y,m,d,h,minute,sec=swe.jdet_to_utc(jd,swe.GREG_CAL);utc=datetime(y,m,d,h,minute,tzinfo=timezone.utc)+timedelta(seconds=sec);floor=utc.replace(microsecond=0);root['native_derived_utc_label']=utc.isoformat();root['public_fixture_utc_labels']=[(floor+timedelta(seconds=offset)).isoformat() for offset in [-1,1]];roots.append(root)
 previous=current
value={'reference_production_imports':False,'time_scale':'TT','year':2000,'whole_predeclared_daily_scan':scan,'conjunctions':roots,'requested_flags':flags,'native_version':swe.version,'binding':str(swe.__version__),'binary':swe.__file__,'binary_sha256':hashlib.sha256(Path(swe.__file__).read_bytes()).hexdigest(),'ephemeris_files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ephe.iterdir()) if p.is_file()},'positions_are_independent_astronomical_truth':False,'actual_rising_or_visibility_solved':False,'real_outcomes':0}
(b/'native-conjunction-probes.json').write_text(json.dumps(value,indent=2)+'\n');print(json.dumps({'daily_scan':len(scan),'conjunctions':len(roots),'public_utc_labels':sum(len(row['public_fixture_utc_labels']) for row in roots)}))
