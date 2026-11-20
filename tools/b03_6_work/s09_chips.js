const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const plan = [
  ['U4037', 540, -700], ['U4041', 1040, -700], ['U4038', 1540, -700],
  ['U4042', 2040, -700], ['U4044', 2540, -700], ['U4056', 3040, -700]
];
const placed = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { placed.push([des, 'MISSING']); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
  placed.push([des, x, y]);
}
// verify by re-read
const out = [];
for (const [des] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  out.push({des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer()});
}
return JSON.stringify({placed, verify: out});
