const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['Q2018', 3522.0, -60.5, 90],
  ['Q2001', 3522.0, 1829.5, 90],
  ['Q2013', 3522.0, 61.5, 90],
  ['Q2014', 3522.0, 183.5, 90],
  ['Q2015', 3522.0, 305.5, 90],
  ['Q2016', 3522.0, 427.5, 90],
  ['Q2019', 3522.0, 1951.5, 90],
  ['Q2020', 3522.0, 549.5, 90],
  ['Q2021', 3522.0, 2073.5, 90],
  ['Q2011', 3522.0, 793.5, 90],
  ['Q2012', 3522.0, 915.5, 90],
  ['Q2003', 3522.0, 1037.5, 90],
  ['Q2004', 3522.0, 1159.5, 90],
  ['Q2005', 3522.0, 1281.5, 90],
  ['Q2006', 3522.0, 1403.5, 90],
  ['Q2007', 3522.0, 1525.5, 90],
  ['Q2008', 3522.0, 1647.5, 90],
  ['Q2009', 3522.0, 2195.5, 90],
  ['Q2002', 3522.0, 2317.5, 90],
  ['Q2010', 3522.0, 2439.5, 90],
  ['Q2017', 3522.0, 2561.5, 90],
  ['RP1', 3522.0, 2987.5, 0],
  ['Q2022', 3522.0, 2865.5, 90],
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
