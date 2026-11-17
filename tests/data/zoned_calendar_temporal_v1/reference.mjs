import { Temporal } from '@js-temporal/polyfill';
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { gunzipSync } from 'node:zlib';

const planBytes=gunzipSync(readFileSync(new URL('./plan.json.gz',import.meta.url)));
const plan=JSON.parse(planBytes);
const rows=plan.cases.map(input=>{
  const instant=Temporal.Instant.from(input.utc);
  const z=instant.toZonedDateTimeISO(input.zone);
  return {input,epoch_microseconds:String(instant.epochNanoseconds/1000n),local_parts:[z.year,z.month,z.day,z.hour,z.minute,z.second,z.millisecond*1000+z.microsecond],offset_seconds:z.offsetNanoseconds/1e9};
});
const result={plan_sha256:createHash('sha256').update(planBytes).digest('hex'),versions:process.versions,reference:'@js-temporal/polyfill@0.5.1',count:rows.length,rows};
writeFileSync(new URL('./reference-output.json',import.meta.url),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({count:rows.length,node:process.versions.node,icu:process.versions.icu,tz:process.versions.tz,plan_sha256:result.plan_sha256}));
