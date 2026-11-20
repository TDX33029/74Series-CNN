const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['R2001', 3167.0, 855.5, 0],
  ['R2002', 3082.0, 855.5, 0],
  ['R2003', 3167.0, 733.5, 0],
  ['R2004', 3082.0, 733.5, 0],
  ['R2005', 3167.0, 1769.5, 0],
  ['R2006', 3082.0, 1769.5, 0],
  ['R2007', 3167.0, 1891.5, 0],
  ['R2008', 3082.0, 1891.5, 0],
  ['R2009', 3167.0, 2013.5, 0],
  ['R2010', 3082.0, 2013.5, 0],
  ['R2011', 3167.0, 1403.5, 0],
  ['R2012', 3082.0, 1403.5, 0],
  ['R2013', 3167.0, 1525.5, 0],
  ['R2014', 3082.0, 1525.5, 0],
  ['R2015', 3167.0, 1647.5, 0],
  ['R2016', 3082.0, 1647.5, 0],
  ['R2017', 3167.0, 977.5, 0],
  ['R2018', 3082.0, 977.5, 0],
  ['R2019', 3167.0, 1099.5, 0],
  ['R2020', 3082.0, 1099.5, 0],
  ['R2021', 3167.0, 2135.5, 0],
  ['R2022', 3082.0, 2135.5, 0],
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
