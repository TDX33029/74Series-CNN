const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// Q3009 row at y=-60 too close to bottom outline (y=-3228): Q vertical rot90 pads dy=±39.4 => -60-39.4-? ~ -99 + pad halfheight 12.8 => edge at -3228+... too close. Move whole row up: y=-150 is taken by MEM_D0 row; move MEM_D0 row to -260, MEM_D1 row to -170; MADDR14 -350, MADDR15 -440
const plan = [
 ['Q3008', 3565, -260], ['R4', 3410, -260], ['R3012', 3475, -260],
 ['Q3009', 3565, -170], ['R5', 3410, -170], ['R3013', 3475, -170],
 ['Q3020', 3565, -350], ['R3035', 3420, -350], ['R3034', 3475, -350],
 ['Q3021', 3565, -440], ['R3037', 3420, -440], ['R3036', 3475, -440],
];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y);
  await a.done();
}
return 'moved ' + plan.length;
