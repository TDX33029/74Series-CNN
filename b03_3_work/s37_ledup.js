const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// move 4 LEDs to align with their relocated back modules (above LED strip top -762)
const plan = [
 ['LED_MADDR14', 3822.5, -350],
 ['LED_MADDR15', 3822.5, -440],
 ['LED_MEM_D0', 3822.5, -260],
 ['LED_MEM_D1', 3822.5, -170],
];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y);
  await a.done();
}
return 'moved ' + plan.length;
