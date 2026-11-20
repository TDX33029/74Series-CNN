const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const cl = arr.find(c => c.name && c.name.includes('Clearance'));
if (!cl) return 'no clearance errors';
const out = [];
for (const sub of (cl.list || [])) {
  for (const e of (sub.list || [])) {
    out.push({type: sub.name, minDist: e.errData ? e.errData.minDistance : null, pos: e.position ? {x: Math.round(e.position.x), y: Math.round(e.position.y)} : null, o1: e.obj1 ? (e.obj1.designator || e.obj1.suffix || e.obj1.type) : null, o2: e.obj2 ? (e.obj2.designator || e.obj2.suffix || e.obj2.type) : null, layer: e.errData ? e.errData.layer : null});
  }
}
return JSON.stringify(out.slice(0, 80));
