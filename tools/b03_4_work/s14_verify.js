const TARGET = '822ec5745398cfb8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  const des = c.getState_Designator();
  const a = c.toAsync();
  out.push({des: des, x: a.getState_X(), y: a.getState_Y(), rot: a.getState_Rotation(), layer: a.getState_Layer()});
}
return JSON.stringify(out);
