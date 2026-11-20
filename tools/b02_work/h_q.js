const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['Q2018', 3522.0, 2068.85, 90],
  ['Q2001', 3522.0, 2982.85, 90],
  ['Q2013', 3522.0, 1946.85, 90],
  ['Q2014', 3522.0, 1824.85, 90],
  ['Q2015', 3522.0, 1702.85, 90],
  ['Q2016', 3522.0, 1580.85, 90],
  ['Q2019', 3522.0, 2860.85, 90],
  ['Q2020', 3522.0, 1458.85, 90],
  ['Q2021', 3522.0, 2738.85, 90],
  ['Q2011', 3522.0, 1214.85, 90],
  ['Q2012', 3522.0, 1092.85, 90],
  ['Q2003', 3522.0, 970.8499999999999, 90],
  ['Q2004', 3522.0, 848.8499999999999, 90],
  ['Q2005', 3522.0, 726.8499999999999, 90],
  ['Q2006', 3522.0, 604.8499999999999, 90],
  ['Q2007', 3522.0, 482.8499999999999, 90],
  ['Q2008', 3522.0, 360.8499999999999, 90],
  ['Q2009', 3522.0, 2616.85, 90],
  ['Q2002', 3522.0, 2494.85, 90],
  ['Q2010', 3522.0, 2372.85, 90],
  ['Q2017', 3522.0, 2250.85, 90],
  ['RP1', 3522.0, 3164.85, 0],
  ['Q2022', 3522.0, 238.8499999999999, 90],
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
