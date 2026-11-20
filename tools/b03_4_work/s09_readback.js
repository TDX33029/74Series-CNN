const TARGET = '822ec5745398cfb8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const want = ['Q1','Q4','Q19','Q16','R1','R4033','R4007','RP1','LEDP1','LED_MADDR17'];
const out = [];
for (const des of want) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { out.push({des: des, missing: true}); continue; }
  const a = c.toAsync();
  const pads = await a.getAllPins();
  out.push({des: des, x: a.getState_X(), y: a.getState_Y(), rot: a.getState_Rotation(), layer: a.getState_Layer(),
    pads: pads.map(p => ({n: p.padNumber, x: p.x, y: p.y, net: p.net}))});
}
return JSON.stringify(out);
