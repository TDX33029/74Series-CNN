const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const plan = [
 ['U4012', 1250, -700], ['U4013', 1250, -2080],
 ['U4015', 1945, -700], ['U4019', 1945, -2080],
 ['U4032', 2640, -700], ['U4048', 2640, -1880],
 ['U4050', 3175, -700],
];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
}
return 'moved ' + plan.length;
