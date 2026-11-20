// DRC full dump: ALL clearance errors with suffixes only (compact)
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const clr = arr.find(c => c.name === 'Clearance Error');
if (!clr) return 'NO CLEARANCE ERROR';
const items = [];
for (const sub of (clr.list || [])) {
  for (const e of (sub.list || [])) {
    const ed = (e.explanation && e.explanation.errData) || e.errData || {};
    items.push({
      sub: sub.name,
      o1: ed.obj1Suffix || (e.obj1 && e.obj1.suffix) || '?',
      o2: ed.obj2Suffix || (e.obj2 && e.obj2.suffix) || '?',
      min: ed.minDistance,
      pos: ed.position ? [ed.position.x, ed.position.y] : (e.pos ? [e.pos.x, e.pos.y] : null)
    });
  }
}
return JSON.stringify({n: items.length, items});
