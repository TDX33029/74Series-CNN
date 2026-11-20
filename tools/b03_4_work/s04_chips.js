const TARGET = '822ec5745398cfb8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['U4024', 540, -700, 90],
  ['U4025', 1250, -700, 90],
  ['U4026', 1250, -2100, 90],
  ['U4033', 1960, -700, 90],
  ['U4036', 2625, -700, 90],
  ['U4040', 3175, -700, 90],
  ['U4054', 2625, -2100, 90],
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
let placed = 0, missing = [];
for (const [des, x, y, rot] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { missing.push(des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  await a.done();
  placed++;
}
return JSON.stringify({placed: placed, missing: missing});
