const TARGET = '7f08bbdec72478d8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT:' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const plan = [['U4009',540,-700],['U4010',540,-2080],['U4011',1235,-700],['U4014',1235,-2080],
  ['U4016',1930,-700],['U4017',1930,-2080],['U4018',2625,-700],['U4031',2625,-1880],['U4049',3165,-700]];
const placed = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { placed.push('MISS:' + des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90);
  await a.done();
  placed.push(des + '@' + a.getState_X() + ',' + a.getState_Y());
}
await new Promise(r => setTimeout(r, 1000));
const drc = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(drc) ? drc.map(c => ({name: c.name, n: (c.list || []).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)})) : 'noarr:' + JSON.stringify(drc).slice(0, 200);
let clrSample = null;
if (Array.isArray(drc)) {
  const ce = drc.find(c => /Clearance/i.test(c.name));
  if (ce && ce.list) clrSample = ce.list.slice(0, 10).map(e => JSON.stringify({o1: e.obj1 && e.obj1.suffix, o2: e.obj2 && e.obj2.suffix, min: e.errData && e.errData.minDistance, pos: e.errData && e.errData.position}).slice(0, 400));
}
return JSON.stringify({placed: placed, drc: arr, clrSample: clrSample});
