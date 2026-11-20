const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const summary = arr.map(c => ({name: c.name, n: (c.list||[]).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)}));
// sample a few clearance errors if any
const clr = arr.find(c => /Clearance/.test(c.name));
let samples = [];
if (clr && clr.list) {
  for (const sub of clr.list.slice(0,8)) {
    samples.push({layer: sub.layer, err: (sub.list||[]).slice(0,3).map(e => ({obj1: e.obj1, obj2: e.obj2, suffix1: e.objSuffix1||e.suffix1, suffix2: e.objSuffix2||e.suffix2, min: e.minDistance, pos: e.position}))});
  }
}
return JSON.stringify({summary, clearanceSamples: samples});
