const TARGET = '046a237b7518687e';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const summary = arr.map(c => ({name: c.name, n: (c.list || []).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)}));
// detail clearance errors if any
let clearance = arr.find(c => c.name === 'Clearance Error');
let detail = [];
if (clearance && clearance.list) {
  for (const sub of clearance.list) {
    if (sub.list) for (const e of sub.list) {
      detail.push({sub: sub.name, obj1: e.obj1 ? (e.obj1.suffix || e.obj1.designator || e.obj1.suffixText) : null,
                   obj2: e.obj2 ? (e.obj2.suffix || e.obj2.designator || e.obj2.suffixText) : null,
                   minDistance: e.errData ? e.errData.minDistance : null});
    }
  }
}
return JSON.stringify({summary, detailCount: detail.length, detail: detail.slice(0, 20)});
