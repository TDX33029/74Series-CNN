// fix v2: pitch 710, bottom row y=-2530 (12mil outline margin), c4 U4027 y=-2630
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['U4002', 540, -700],
  ['U4001', 540, -2530],
  ['U4004', 1250, -700],
  ['U4003', 1250, -2530],
  ['U4006', 1960, -700],
  ['U4007', 1960, -2530],
  ['U4028', 2670, -750],
  ['U4034', 2670, -1750],
  ['U4027', 2670, -2630],
  ['U4020', 3380, -800]
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
