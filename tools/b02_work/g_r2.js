const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['R2024', 3246.0, 915.5, 0],
  ['R2025', 3328.0, 61.5, 0],
  ['R2026', 3246.0, 61.5, 0],
  ['R2027', 3328.0, 183.5, 0],
  ['R2028', 3246.0, 183.5, 0],
  ['R2029', 3328.0, 305.5, 0],
  ['R2030', 3246.0, 305.5, 0],
  ['R2031', 3328.0, 427.5, 0],
  ['R2032', 3246.0, 427.5, 0],
  ['R2033', 3328.0, 2561.5, 0],
  ['R2034', 3246.0, 2561.5, 0],
  ['R2035', 3328.0, -60.5, 0],
  ['R2036', 3246.0, -60.5, 0],
  ['R2037', 3328.0, 1951.5, 0],
  ['R2038', 3246.0, 1951.5, 0],
  ['R2039', 3328.0, 549.5, 0],
  ['R2040', 3246.0, 549.5, 0],
  ['R2041', 3328.0, 2073.5, 0],
  ['R2042', 3246.0, 2073.5, 0],
  ['R2043', 3328.0, 2865.5, 0],
  ['R2044', 3246.0, 2865.5, 0],
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
