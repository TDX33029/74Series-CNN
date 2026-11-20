// fix placement: corrected geometry (PDIP-28 halfspan 312 halflength 650; pitch 690)
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['U4002', 540, -700],
  ['U4001', 540, -2550],
  ['U4004', 1230, -700],
  ['U4003', 1230, -2550],
  ['U4006', 1920, -700],
  ['U4007', 1920, -2550],
  ['U4028', 2610, -750],
  ['U4034', 2610, -1750],
  ['U4027', 2610, -2610],
  ['U4020', 3300, -800]
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
