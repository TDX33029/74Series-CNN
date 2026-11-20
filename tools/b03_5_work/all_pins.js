const PCB = '42f9160329b94bb4';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  const des = c.getState_Designator();
  if (des === 'J20205') continue;
  let pins = null;
  try { pins = await c.toAsync().getAllPins(); } catch(e) {}
  if (!pins || !pins.length) {
    try { pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId()); } catch(e2) {}
  }
  out.push({des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer(),
    pads: (pins||[]).map(p => ({x: p.x, y: p.y, net: p.net, num: p.padNumber, pad: p.pad}))});
}
return JSON.stringify(out);
