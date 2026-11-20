// move isolated pull-up resistors to top free band
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['R4001', 3300, -250],
  ['R4003', 3380, -250],
  ['R4004', 3300, -350],
  ['R4005', 3380, -350],
  ['R4006', 3340, -450]
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
let moved = 0;
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) continue;
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y);
  await a.done();
  moved++;
}
return 'moved ' + moved;
