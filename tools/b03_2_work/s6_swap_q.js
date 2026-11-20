const TARGET = '7f08bbdec72478d8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT:' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const byDes = {};
for (const c of comps) byDes[c.getState_Designator()] = c;
// swap rows: Q3009 belongs to LED_LOAD_DATA0 (y=-2842), Q3010 to LED_LOAD_DATA1 (y=-2720)
const fix = [['Q3009', 3565, -2842], ['Q3010', 3565, -2720]];
for (const [des, x, y] of fix) {
  const a = byDes[des].toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(90); a.setState_Layer(2);
  await a.done();
}
// verification sweep: every LED front L1 at x=3822.5; modules back L2; same-y check
const leds = comps.filter(c => /^LED/.test(c.getState_Designator()));
const verify = [];
for (const c of leds) {
  const a = c.toAsync();
  verify.push({des: c.getState_Designator(), x: a.getState_X(), y: a.getState_Y(), layer: a.getState_Layer()});
}
const qs = comps.filter(c => /^Q30/.test(c.getState_Designator())).map(c => { const a = c.toAsync(); return {des: c.getState_Designator(), x: a.getState_X(), y: a.getState_Y(), layer: a.getState_Layer(), rot: a.getState_Rotation()}; });
const rs = comps.filter(c => /^R/.test(c.getState_Designator())).map(c => { const a = c.toAsync(); return {des: c.getState_Designator(), x: a.getState_X(), y: a.getState_Y(), layer: a.getState_Layer()}; });
const drc = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(drc) ? drc.map(c => ({name: c.name, n: (c.list || []).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)})) : 'noarr';
let clrSample = null;
if (Array.isArray(drc)) {
  const ce = drc.find(c => /Clearance/i.test(c.name));
  if (ce && ce.list) clrSample = ce.list.slice(0, 15).map(e => JSON.stringify({o1: e.obj1 && e.obj1.suffix, o2: e.obj2 && e.obj2.suffix, min: e.errData && e.errData.minDistance}));
}
return JSON.stringify({fix: fix, leds: verify, qs: qs, rs: rs, drc: arr, clrSample: clrSample});
