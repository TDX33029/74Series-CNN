// place LEDs (front, rot=0) per plan
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['LEDP1', 3822.5, -3146.0, 0],
  ['LED_DIR_SEL', 3822.5, -2964.0, 0],
  ['LED_LOAD_EN_I', 3822.5, -2842.0, 0],
  ['LED_LOAD_NOE_I', 3822.5, -2720.0, 0],
  ['LED_LOAD_NWE_I', 3822.5, -2598.0, 0],
  ['LED_MEM_NOE_INT', 3822.5, -2476.0, 0],
  ['LED_MEM_NWE_INT', 3822.5, -2354.0, 0],
  ['LED_NCS_SRAM_FC1OUT', 3822.5, -2232.0, 0],
  ['LED_NCS_SRAM_FC2LOG', 3822.5, -2110.0, 0],
  ['LED_READ_DIR', 3822.5, -1988.0, 0],
  ['LED_DATA4', 3822.5, -1806.0, 0],
  ['LED_DATA5', 3822.5, -1684.0, 0],
  ['LED_DATA6', 3822.5, -1562.0, 0],
  ['LED_MEM_D0', 3822.5, -1440.0, 0],
  ['LED_MEM_D1', 3822.5, -1318.0, 0],
  ['LED_MEM_D2', 3822.5, -1196.0, 0],
  ['LED_MEM_D3', 3822.5, -1074.0, 0],
  ['LED_MEM_D4', 3822.5, -952.0, 0],
  ['LED_MEM_D5', 3822.5, -830.0, 0],
  ['LED_MEM_D6', 3822.5, -708.0, 0],
  ['LED_MEM_D7', 3822.5, -586.0, 0]
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
