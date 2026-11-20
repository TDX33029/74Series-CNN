const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const plan = [
 ['U4005', 540, -700], ['U4008', 540, -2080],
 ['U4012', 1235, -700], ['U4013', 1235, -2080],
 ['U4015', 1930, -700], ['U4019', 1930, -2080],
 ['U4032', 2625, -700], ['U4048', 2625, -1880],
 ['U4050', 3165, -700],
];
const skipped = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { skipped.push(des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
}
// verify
const check = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  check.push({des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation()});
}
return JSON.stringify({placed: plan.length, skipped, check});
