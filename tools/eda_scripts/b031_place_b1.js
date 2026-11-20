// place chips: batch 1 (c1+c2) — 5 PDIP-28 SRAM
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['U4001', 450, -2544.0],
  ['U4002', 450, -580.0],
  ['U4003', 900, -2544.0],
  ['U4004', 900, -580.0],
  ['U4006', 900, -1562.0]
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
let placed = 0, missing = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { missing.push(des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
  placed++;
}
return JSON.stringify({placed, missing});
