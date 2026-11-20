const PCB = '42f9160329b94bb4';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const summary = arr.map(c => ({name: c.name, n: (c.list||[]).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)}));
let clearanceDetail = [];
const ce = arr.find(c => (c.name||'').includes('Clearance'));
if (ce) {
  for (const sub of (ce.list||[])) {
    for (const e of (sub.list||[])) {
      clearanceDetail.push({type: sub.name || sub.type, obj1: e.obj1Suffix || e.obj1, obj2: e.obj2Suffix || e.obj2, min: e.errData ? (e.errData.minDistance || e.errData.min) : null});
    }
  }
}
return JSON.stringify({summary, clearanceDetail: clearanceDetail.slice(0, 30)});
