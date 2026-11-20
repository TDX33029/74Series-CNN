// place LEDs (front, rot=0) per plan
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = /*LED_PLAN*/[];
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
