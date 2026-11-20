const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['R2024', 3246.0, 360.8499999999999, 0],
  ['R2025', 3328.0, 970.8499999999999, 0],
  ['R2026', 3246.0, 970.8499999999999, 0],
  ['R2027', 3328.0, 848.8499999999999, 0],
  ['R2028', 3246.0, 848.8499999999999, 0],
  ['R2029', 3328.0, 726.8499999999999, 0],
  ['R2030', 3246.0, 726.8499999999999, 0],
  ['R2031', 3328.0, 604.8499999999999, 0],
  ['R2032', 3246.0, 604.8499999999999, 0],
  ['R2033', 3328.0, 1152.85, 0],
  ['R2034', 3246.0, 1152.85, 0],
  ['R2035', 3328.0, 2982.85, 0],
  ['R2036', 3246.0, 2982.85, 0],
  ['R2037', 3328.0, 2738.85, 0],
  ['R2038', 3246.0, 2738.85, 0],
  ['R2039', 3328.0, 2616.85, 0],
  ['R2040', 3246.0, 2616.85, 0],
  ['R2041', 3328.0, 2372.85, 0],
  ['R2042', 3246.0, 2372.85, 0],
  ['R2043', 3328.0, 3164.85, 0],
  ['R2044', 3246.0, 3164.85, 0],
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const [des, x, y, rot] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { out.push(des + ':NOTFOUND'); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  if (true) a.setState_Layer(2);
  await a.done();
  out.push(des + '@' + Math.round(a.getState_X()) + ',' + Math.round(a.getState_Y()) + ',L' + a.getState_Layer());
}
return out.join(' | ');
