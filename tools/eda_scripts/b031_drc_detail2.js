// DRC detail v2: dump raw error entries with all own properties
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const clr = arr.find(c => c.name === 'Clearance Error');
if (!clr) return 'NO CLEARANCE ERROR';
const raw = [];
for (const sub of (clr.list || [])) {
  for (const e of (sub.list || []).slice(0, 3)) {
    const flat = {};
    for (const k of Object.keys(e)) {
      const v = e[k];
      if (v && typeof v === 'object') flat[k] = JSON.parse(JSON.stringify(v));
      else flat[k] = v;
    }
    raw.push({sub: sub.name, e: flat});
  }
}
// also inspect sub-level properties
const subsInfo = (clr.list||[]).map(s => ({name: s.name, n: (s.list||[]).length, keys: Object.keys(s)}));
return JSON.stringify({subsInfo, raw}, null, 1);
