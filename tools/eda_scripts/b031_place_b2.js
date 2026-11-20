// place chips: batch 2 (c3 + verify batch1 positions)
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['U4007', 1350, -580.0],
  ['U4028', 1350, -1562.0],
  ['U4034', 1350, -2544.0],
  ['U4027', 1750, -580.0],
  ['U4020', 1750, -1487.0]
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
let placed = 0, missing = [];
const verify = {};
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { missing.push(des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
  placed++;
}
// verify all 10
const names = ['U4001','U4002','U4003','U4004','U4006','U4007','U4020','U4027','U4028','U4034'];
for (const n of names) {
  const c = comps.find(k => k.getState_Designator() === n);
  verify[n] = {x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation()};
}
return JSON.stringify({placed, missing, verify});
