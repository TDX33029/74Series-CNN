const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['U2005', 260, 500], ['U2009', 260, 1395.5],
  ['U2001', 960, 700],
  ['U2002', 1670, 500], ['U2003', 1670, 1551.4], ['U2004', 1670, 2503.3],
  ['U2006', 2320, 500], ['U2007', 2320, 1345],
  ['U2008', 2990, 500], ['U2010', 2990, 1396], ['U2011', 2990, 2139]
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { out.push(des + ':NOTFOUND'); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
  out.push(des + '@' + a.getState_X() + ',' + a.getState_Y() + ',r' + a.getState_Rotation());
}
return out.join(' | ');
