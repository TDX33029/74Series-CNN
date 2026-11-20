const TARGET = '046a237b7518687e';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// columns left->right: ADDR0-7 side near header; then ADDR8-15 side; LED strip >=360mil right end
const plan = [
  ['U4043', 540, -700, 90],
  ['U4051', 540, -1680, 90],
  ['U4045', 1040, -700, 90],
  ['U4046', 1040, -1680, 90],
  ['U4052', 1540, -700, 90],
];
for (const [des, x, y, rot] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) return 'MISSING ' + des;
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  await a.done();
}
// verify
const res = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  res.push({des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer()});
}
return JSON.stringify(res);
