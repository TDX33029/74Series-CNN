const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const summary = arr.map(c => ({name: c.name, n: (c.list||[]).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)}));
return JSON.stringify(summary);
