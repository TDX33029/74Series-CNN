const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// MADDR14/MADDR15 rows: shift x from 3410 to 3260 (R10k slot shifted left, away from U4050 col at 3175)
// U4050 pads left col x = 3175-150.03 = 3024.97, right col 3325.03
// R at 3260: dist to right col pads (y offset ±50) => sqrt(65^2+...)  center y diff 0..100
const plan = [
 ['Q3020', 3565, -240], ['R3035', 3260, -240], ['R3034', 3315, -240],
 ['Q3021', 3565, -330], ['R3037', 3260, -330], ['R3036', 3315, -330],
];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y);
  await a.done();
}
return 'moved ' + plan.length;
