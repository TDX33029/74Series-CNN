const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['Q2001', 3522.0, 367.5, 90],
  ['Q2002', 3522.0, 245.5, 90],
  ['Q2003', 3522.0, 1525.5, 90],
  ['Q2004', 3522.0, 1647.5, 90],
  ['Q2005', 3522.0, 1769.5, 90],
  ['Q2006', 3522.0, 1159.5, 90],
  ['Q2007', 3522.0, 1281.5, 90],
  ['Q2008', 3522.0, 1403.5, 90],
  ['Q2009', 3522.0, 489.5, 90],
  ['Q2010', 3522.0, 611.5, 90],
  ['Q2011', 3522.0, 1891.5, 90],
  ['Q2012', 3522.0, 2013.5, 90],
  ['Q2013', 3522.0, 2135.5, 90],
  ['Q2014', 3522.0, 2257.5, 90],
  ['Q2015', 3522.0, 2379.5, 90],
  ['Q2016', 3522.0, 2501.5, 90],
  ['Q2017', 3522.0, 733.5, 90],
  ['Q2018', 3522.0, 2623.5, 90],
  ['Q2019', 3522.0, 855.5, 90],
  ['Q2020', 3522.0, 2745.5, 90],
  ['Q2021', 3522.0, 977.5, 90],
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
