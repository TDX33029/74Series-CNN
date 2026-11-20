const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const out = [];
for (const cat of arr) {
  if (cat.name !== 'Clearance Error') continue;
  for (const sub of (cat.list||[])) {
    if (sub.list) {
      for (const e of sub.list) {
        out.push({rule: sub.name || cat.name, o1: e.obj1Suffix || e.obj1 || (e.data1&&e.data1.primitiveId) || '?', o2: e.obj2Suffix || e.obj2 || '?', d: e.errData ? {min: e.errData.minDistance, act: e.errData.actualDistance} : null});
      }
    } else {
      out.push({rule: sub.name || cat.name, raw: JSON.stringify(sub).slice(0,400)});
    }
  }
}
return JSON.stringify(out);
