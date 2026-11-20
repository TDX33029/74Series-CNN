const PCB = '42f9160329b94bb4';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
// outline polylines
const pls = await eda.pcb_PrimitivePolyline.getAll();
const plInfo = [];
for (const pl of pls) {
  let poly = null;
  try { poly = pl.polygon; } catch(e) {}
  let layer = null;
  try { layer = pl.getState_Layer(); } catch(e) {}
  plInfo.push({layer, poly});
}
// all components
const comps = await eda.pcb_PrimitiveComponent.getAll();
const compInfo = [];
for (const c of comps) {
  compInfo.push({des: c.getState_Designator(), x: c.getState_X(), y: c.getState_Y(),
    rot: c.getState_Rotation(), layer: c.getState_Layer(), id: c.getState_PrimitiveId()});
}
return JSON.stringify({plInfo, comps: compInfo});
