const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['R2001', 3328.0, 2860.85, 0],
  ['R2002', 3246.0, 2860.85, 0],
  ['R2003', 3328.0, 1396.85, 0],
  ['R2004', 3246.0, 1396.85, 0],
  ['R2005', 3328.0, 2250.85, 0],
  ['R2006', 3246.0, 2250.85, 0],
  ['R2007', 3328.0, 2128.85, 0],
  ['R2008', 3246.0, 2128.85, 0],
  ['R2009', 3328.0, 2006.85, 0],
  ['R2010', 3246.0, 2006.85, 0],
  ['R2011', 3328.0, 1884.85, 0],
  ['R2012', 3246.0, 1884.85, 0],
  ['R2013', 3328.0, 1762.85, 0],
  ['R2014', 3246.0, 1762.85, 0],
  ['R2015', 3328.0, 1640.85, 0],
  ['R2016', 3246.0, 1640.85, 0],
  ['R2017', 3328.0, 1518.85, 0],
  ['R2018', 3246.0, 1518.85, 0],
  ['R2019', 3328.0, 1274.85, 0],
  ['R2020', 3246.0, 1274.85, 0],
  ['R2021', 3328.0, 482.8499999999999, 0],
  ['R2022', 3246.0, 482.8499999999999, 0],
  ['R2023', 3328.0, 360.8499999999999, 0],
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
