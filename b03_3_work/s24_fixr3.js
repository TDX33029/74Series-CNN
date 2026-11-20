const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// MADDR14/MADDR15 module rows: rotate 90 (vertical orientation) at x=3410/3475 same as others.
// vertical R (rot90): pads at dy=±17 -> y=-240±17 => distance to U4050_10 (3175? no pads at x=3325.03,y=-250) large in x: 3410-3325=85 plus dy => >=85 OK
const plan = [
 ['Q3020', 3565, -240], ['R3035', 3410, -240], ['R3034', 3475, -240],
 ['Q3021', 3565, -330], ['R3037', 3410, -330], ['R3036', 3475, -330],
];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
}
return 'done';
