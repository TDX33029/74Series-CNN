const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['R2023', 3167.0, 2257.5, 0],
  ['R2024', 3082.0, 2257.5, 0],
  ['R2025', 3167.0, 2379.5, 0],
  ['R2026', 3082.0, 2379.5, 0],
  ['R2027', 3167.0, 2501.5, 0],
  ['R2028', 3082.0, 2501.5, 0],
  ['R2029', 3167.0, 2623.5, 0],
  ['R2030', 3082.0, 2623.5, 0],
  ['R2031', 3167.0, 2745.5, 0],
  ['R2032', 3082.0, 2745.5, 0],
  ['R2033', 3167.0, 1221.5, 0],
  ['R2034', 3082.0, 1221.5, 0],
  ['R2035', 3167.0, 2867.5, 0],
  ['R2036', 3082.0, 2867.5, 0],
  ['R2037', 3167.0, 1343.5, 0],
  ['R2038', 3082.0, 1343.5, 0],
  ['R2039', 3167.0, 2989.5, 0],
  ['R2040', 3082.0, 2989.5, 0],
  ['R2041', 3167.0, 1465.5, 0],
  ['R2042', 3082.0, 1465.5, 0],
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const [des, x, y, rot] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { out.push(des + ':NOTFOUND'); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  if (2 === 2) { a.setState_Layer(2); }
  await a.done();
  out.push(des + '@' + Math.round(a.getState_X()) + ',' + Math.round(a.getState_Y()) + ',L' + a.getState_Layer());
}
return out.join(' | ');
