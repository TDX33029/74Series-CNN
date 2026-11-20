const TARGET = '046a237b7518687e';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
return JSON.stringify(arr.map(c => ({
  name: c.name,
  n: (c.list || []).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)
})));
