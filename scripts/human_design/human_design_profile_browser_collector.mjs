// Run only from cua_repl with an already authorized browser tab. No HTTP,
// private application state, direct calculation API, account or email access.
// All UI targets come from fresh accessibility state; all facts from rendered DOM.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';

const PLAN_SHA = 'ea4e0cd15bd228a3002bd055aaeaae28264b5edf0d51505af1828c29e78ce143';
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');

export async function createCollector(tab, planPath, out) {
  const planBytes = await fs.readFile(planPath);
  if (hash(planBytes) !== PLAN_SHA) throw Error('Frozen plan changed');
  const plan = JSON.parse(planBytes);
  await fs.mkdir(out + '/pdfs', {recursive: true});
  const log = async value => fs.appendFile(out + '/attempts.jsonl', JSON.stringify({at: new Date().toISOString(), ...value}) + '\n');
  let saved = [];
  try { saved = (await fs.readFile(out + '/observations.jsonl', 'utf8')).trim().split('\n').filter(Boolean).map(JSON.parse); }
  catch (e) { if (e.code !== 'ENOENT') throw e; }
  if (saved.some((row, i) => row.id !== plan.cases[i].id)) throw Error('Non-prefix collection or duplicate IDs; manual review required');
  let next = saved.length;
  const state = () => tab.getAXState({emit: false, disableDiffing: true});
  async function readChart() {
    const rows = await tab.playwright.locator('#chart-viewer').evaluateAll(es => es.filter(e => e.getBoundingClientRect().width > 0).map(e => {
      const properties = {};
      for (const row of e.querySelectorAll('.property-item')) {
        const key = row.querySelector('.property-item-title'), value = row.querySelector('.property-item-value');
        if (key && value) properties[key.textContent] = value.textContent;
      }
      const columns = {};
      for (const column of e.querySelectorAll('[data-element-type="planet-table"]')) {
        const side = column.getAttribute('data-dom-ref-id') === 'planets.left' ? 'design' : 'personality';
        columns[side] = Array.from(column.querySelectorAll('text.gate')).map(t => t.textContent.replace(/\s/g, ''));
      }
      return {
        properties, columns,
        defined_channel_render_ids: Array.from(e.querySelectorAll('[id].defined')).map(x => x.id).filter(id => /^c\d+$/.test(id)).sort(),
        defined_centers: Array.from(e.querySelectorAll('#centers > g.defined')).map(x => x.id).sort(),
      };
    }));
    if (rows.length !== 1) throw Error('Expected exactly one visible chart');
    return rows[0];
  }
  async function finish(c, s) {
    const facts = await readChart();
    if (facts.properties.Name !== `FateBridge fictional ${c.id}` || facts.columns.design.length !== 13 || facts.columns.personality.length !== 13) throw Error('Rendered identity/column mismatch');
    const download = tab.playwright.waitForEvent('download');
    await tab.click(Number(s.match(/(\d+) button Download PDF/)[1]));
    const downloadPath = await (await download).path({timeoutMs: 20000});
    const bytes = await fs.readFile(downloadPath), filename = c.id + '.pdf';
    await fs.writeFile(out + '/pdfs/' + filename, bytes, {flag: 'wx'});
    const row = {id: c.id, collected_at_utc: new Date().toISOString(), facts, source: {pdf_filename: filename, pdf_sha256: hash(bytes), pdf_bytes: bytes.length}};
    await fs.appendFile(out + '/observations.jsonl', JSON.stringify(row) + '\n');
    next++;
    await log({id: c.id, event: 'saved', pdf_sha256: row.source.pdf_sha256});
    s = await state();
    await tab.click(Number(s.match(/\d+ container chart-viewer\n\s+(\d+) button/)[1]));
    return {status: 'saved', id: c.id, completed: next, planned: plan.cases.length};
  }
  async function step() {
    if (next === plan.cases.length) return {status: 'collection_complete', completed: next};
    const c = plan.cases[next];
    await log({id: c.id, event: 'step_started', plan_sha256: PLAN_SHA});
    let s = await state();
    if (/button Download PDF/.test(s)) return finish(c, s);
    const form = s.split('container mmi-tab-info')[1]?.split('text Recent Charts')[0];
    const fields = Array.from((form || '').matchAll(/(\d+) text field/g)).map(m => Number(m[1]));
    const create = s.match(/(\d+) button Create Chart/);
    if (fields.length !== 5 || !create) return {status: 'pending', id: c.id, completed: next, reason: 'No ready chart or submit control; preserve in-flight request'};
    const b = c.birth_input, pad = n => String(n).padStart(2, '0');
    await tab.setValue(fields[0], `FateBridge fictional ${c.id}`);
    await tab.setValue(fields[2], `${pad(b.birth_day)}/${pad(b.birth_month)}/${b.birth_year}`);
    await tab.setValue(fields[3], `${pad(b.birth_hour)}:${pad(b.birth_minute)}`);
    await tab.setValue(fields[4], 'London');
    await tab.pressKey(fields[4], 'Down');
    s = await state();
    let city = s.match(/(\d+) text London \(England\), United Kingdom/);
    for (let i = 0; !city && i < 6; i++) {
      await tab.getScreenshot({emit: false});
      s = await state();
      city = s.match(/(\d+) text London \(England\), United Kingdom/);
    }
    if (!city) return {status: 'pending', id: c.id, completed: next, reason: 'City list not ready; no chart submitted'};
    await tab.click(Number(city[1]));
    // Read back all visible inputs before submitting this case. No cached index
    // survives a new form; the current submit button is derived again here.
    s = await state();
    if (!s.includes(`text field (settable) FateBridge fictional ${c.id}`) || !s.includes('text field (settable) London (England), United Kingdom')) throw Error('Visible input identity/city mismatch');
    await tab.click(Number(s.match(/(\d+) button Create Chart/)[1]));
    await log({id: c.id, event: 'submitted'});
    s = await state();
    for (let i = 0; !/button Download PDF/.test(s) && i < 6; i++) {
      await tab.getScreenshot({emit: false});
      s = await state();
    }
    if (!/button Download PDF/.test(s)) return {status: 'pending', id: c.id, completed: next, reason: 'Submitted request still running'};
    return finish(c, s);
  }
  return {
    async step() { try { return await step(); } catch (e) { await log({id: plan.cases[next]?.id, event: 'error', error: String(e)}); throw e; } },
    progress: () => ({completed: next, planned: plan.cases.length, next_id: plan.cases[next]?.id}),
  };
}
