// place LEDs (front, rot=0) per plan
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['Q3011', 3570.0, -2964.0, 90],
  ['Q3012', 3570.0, -2842.0, 90],
  ['Q3013', 3570.0, -2720.0, 90],
  ['Q3014', 3570.0, -2598.0, 90],
  ['Q3008', 3570.0, -2476.0, 90],
  ['Q3009', 3570.0, -2354.0, 90],
  ['Q3023', 3570.0, -2232.0, 90],
  ['Q3024', 3570.0, -2110.0, 90],
  ['Q3010', 3570.0, -1988.0, 90],
  ['Q3005', 3570.0, -1806.0, 90],
  ['Q3006', 3570.0, -1684.0, 90],
  ['Q3007', 3570.0, -1562.0, 90],
  ['Q3015', 3570.0, -1440.0, 90],
  ['Q3016', 3570.0, -1318.0, 90],
  ['Q3017', 3570.0, -1196.0, 90],
  ['Q3018', 3570.0, -1074.0, 90],
  ['Q3019', 3570.0, -952.0, 90],
  ['Q3020', 3570.0, -830.0, 90],
  ['Q3021', 3570.0, -708.0, 90],
  ['Q3022', 3570.0, -586.0, 90]
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
let placed = 0, missing = [];
for (const [des, x, y, rot] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { missing.push(des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  await a.done();
  placed++;
}
return JSON.stringify({placed, missing});
