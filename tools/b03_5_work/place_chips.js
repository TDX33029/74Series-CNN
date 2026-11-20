const PCB = '42f9160329b94bb4';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['U4047', 540, -700],
  ['U4055', 1040, -700],
  ['U4021', 1540, -700],
  ['U4022', 1540, -1480],
  ['U4023', 1920, -700],
  ['U4030', 2300, -700]
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
let placed = 0; const missing = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { missing.push(des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
  placed++;
}
// read back to verify
const out = [];
for (const [des] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  out.push({des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer()});
}
return JSON.stringify({placed, missing, readback: out});
