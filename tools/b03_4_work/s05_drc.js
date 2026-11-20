const TARGET = '822ec5745398cfb8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const summary = arr.map(c => ({name: c.name, n: (c.list||[]).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)}));
let clearanceSamples = [];
for (const cat of arr) {
  if (cat.name && cat.name.indexOf('Clearance') >= 0) {
    for (const sub of (cat.list||[])) {
      for (const it of (sub.list||[])) {
        clearanceSamples.push({obj1: it.obj1 ? (it.obj1.suffix || it.obj1.designator || '') : '', obj2: it.obj2 ? (it.obj2.suffix || it.obj2.designator || '') : '', min: it.errData ? it.errData.minDistance : undefined, layer: it.errData ? it.errData.layer : undefined});
        if (clearanceSamples.length >= 40) break;
      }
      if (clearanceSamples.length >= 40) break;
    }
  }
}
return JSON.stringify({summary: summary, clearanceSamples: clearanceSamples});
