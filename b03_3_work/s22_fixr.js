const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// move offending R rows (LED_MEM_D0 / LED_MEM_D1 rows y=-884/-762) to empty back band y=-150/-60
const plan = [
 ['Q3008', 3565, -150], ['R4', 3410, -150], ['R3012', 3475, -150],
 ['Q3009', 3565, -60], ['R5', 3410, -60], ['R3013', 3475, -60],
 ['Q3020', 3565, -240], ['R3035', 3410, -240], ['R3034', 3475, -240],
 ['Q3021', 3565, -330], ['R3037', 3410, -330], ['R3036', 3475, -330],
];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y);
  await a.done();
}
return 'moved ' + plan.length;
