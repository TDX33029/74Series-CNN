const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// shift the two R10k (vertical) 10mil right: 3410 -> 3420 to clear U4050 pads by >=88 center dist
const plan = [['R3035', 3420, -240], ['R3037', 3420, -330]];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y);
  await a.done();
}
return 'moved';
