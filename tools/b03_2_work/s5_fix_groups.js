const TARGET = '7f08bbdec72478d8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT:' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const byDes = {};
for (const c of comps) byDes[c.getState_Designator()] = c;
// bottom -> top: power -> control(12) -> data(8); pitch 122, group gap 182
const rows = [
  ['LEDP1',           -3146],
  ['LED_FC2_BUSY_N',  -2964], ['LED_LOAD_DATA0', -2842], ['LED_LOAD_DATA1', -2720],
  ['LED_MEM_NOE_INT', -2598], ['LED_MEM_NWE_INT', -2476],
  ['LED_NCS_LUT1_LO', -2354], ['LED_NCS_LUT2_HI', -2232], ['LED_NCS_LUT2_LO', -2110],
  ['LED_NCS_LUT3_LO', -1988],
  ['LED_NCS_W_CONV2', -1866], ['LED_NCS_W_FC1',  -1744], ['LED_NCS_W_FC2',   -1622],
  ['LED_MEM_D0',      -1440], ['LED_MEM_D1', -1318], ['LED_MEM_D2', -1196], ['LED_MEM_D3', -1074],
  ['LED_MEM_D4',       -952], ['LED_MEM_D5',  -830], ['LED_MEM_D6',  -708], ['LED_MEM_D7',  -586]
];
const mod = {
  'LEDP1':           ['RP1',   null,   null],
  'LED_LOAD_DATA0':  ['Q3010', 'R3018', 'R3017'],
  'LED_LOAD_DATA1':  ['Q3009', 'R3020', 'R3019'],
  'LED_FC2_BUSY_N':  ['Q3027', 'R3050', 'R3049'],
  'LED_MEM_NWE_INT': ['Q3012', 'R2',    'R3022'],
  'LED_MEM_NOE_INT': ['Q3011', 'R1',    'R3021'],
  'LED_NCS_W_CONV2': ['Q3024', 'R3044', 'R3043'],
  'LED_NCS_W_FC1':   ['Q3025', 'R3046', 'R3045'],
  'LED_NCS_W_FC2':   ['Q3026', 'R3048', 'R3047'],
  'LED_NCS_LUT1_LO': ['Q3021', 'R3038', 'R3037'],
  'LED_NCS_LUT2_LO': ['Q3028', 'R3052', 'R3051'],
  'LED_NCS_LUT2_HI': ['Q3022', 'R3040', 'R3039'],
  'LED_NCS_LUT3_LO': ['Q3023', 'R3042', 'R3041'],
  'LED_MEM_D0':      ['Q3013', 'R3',    'R3023'],
  'LED_MEM_D1':      ['Q3014', 'R4',    'R3024'],
  'LED_MEM_D2':      ['Q3015', 'R3026', 'R3025'],
  'LED_MEM_D3':      ['Q3016', 'R3028', 'R3027'],
  'LED_MEM_D4':      ['Q3017', 'R3030', 'R3029'],
  'LED_MEM_D5':      ['Q3018', 'R3032', 'R3031'],
  'LED_MEM_D6':      ['Q3019', 'R3034', 'R3033'],
  'LED_MEM_D7':      ['Q3020', 'R3036', 'R3035']
};
const QX = 3565, R10KX = 3410, R1KX = 3475, LEDX = 3822.5;
const plan = [];
for (const [des, y] of rows) {
  plan.push([des, LEDX, y, 0, 1]);
  const [q, r10, r1] = mod[des];
  if (q) plan.push([q, QX, y, 90, 2]);
  if (r10) plan.push([r10, R10KX, y, 90, 2]);
  if (r1) plan.push([r1, R1KX, y, 90, 2]);
}
const placed = [];
for (const [des, x, y, rot, layer] of plan) {
  const c = byDes[des];
  if (!c) { placed.push('MISS:' + des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  a.setState_Layer(layer);
  await a.done();
  placed.push(des + '@' + a.getState_X() + ',' + a.getState_Y() + ',L' + a.getState_Layer());
}
await new Promise(r => setTimeout(r, 1200));
const drc = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(drc) ? drc.map(c => ({name: c.name, n: (c.list || []).reduce((s, sub) => s + (sub.list ? sub.list.length : 0), 0)})) : 'noarr:' + JSON.stringify(drc).slice(0, 300);
let clrSample = null;
if (Array.isArray(drc)) {
  const ce = drc.find(c => /Clearance/i.test(c.name));
  if (ce && ce.list) clrSample = ce.list.slice(0, 15).map(e => JSON.stringify({o1: e.obj1 && e.obj1.suffix, o2: e.obj2 && e.obj2.suffix, min: e.errData && e.errData.minDistance}));
}
return JSON.stringify({n: plan.length, miss: placed.filter(s => s.startsWith('MISS')), drc: arr, clrSample: clrSample});
