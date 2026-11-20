const TARGET='a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const plan = [
  ['Q2022', 3522, 2494.85],
  ['R2043', 3328, 2494.85],
  ['R2044', 3246, 2494.85],
];
const done=[];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { done.push(des+':MISSING'); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y);
  await a.done();
  done.push(des+':ok');
}
return JSON.stringify(done);
