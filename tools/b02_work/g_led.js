const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['LEDP1', 3823.0, 2743.5, 0],
  ['LED_CLK', 3823.0, 1829.5, 0],
  ['LED_CNT_CLR_N', 3823.0, 1951.5, 0],
  ['LED_IDLE_N', 3823.0, 2073.5, 0],
  ['LED_REQ', 3823.0, 2195.5, 0],
  ['LED_RESET_N', 3823.0, 2317.5, 0],
  ['LED_WE', 3823.0, 2439.5, 0],
  ['LED_WE_S', 3823.0, 2561.5, 0],
  ['LED_ACK_I', 3823.0, -60.5, 0],
  ['LED_CNT0', 3823.0, 61.5, 0],
  ['LED_CNT1', 3823.0, 183.5, 0],
  ['LED_CNT2', 3823.0, 305.5, 0],
  ['LED_CNT3', 3823.0, 427.5, 0],
  ['LED_DONE_I', 3823.0, 549.5, 0],
  ['LED_DONE_ST_N', 3823.0, 671.5, 0],
  ['LED_MC1', 3823.0, 793.5, 0],
  ['LED_MC2', 3823.0, 915.5, 0],
  ['LED_MEM_ACK', 3823.0, 1037.5, 0],
  ['LED_MEM_BUSY', 3823.0, 1159.5, 0],
  ['LED_MEM_DONE', 3823.0, 1281.5, 0],
  ['LED_MEM_NCE', 3823.0, 1403.5, 0],
  ['LED_MEM_NOE', 3823.0, 1525.5, 0],
  ['LED_MEM_NWE', 3823.0, 1647.5, 0],
];
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const [des, x, y, rot] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { out.push(des + ':NOTFOUND'); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  if (false) a.setState_Layer(2);
  await a.done();
  out.push(des + '@' + Math.round(a.getState_X()) + ',' + Math.round(a.getState_Y()) + ',L' + a.getState_Layer());
}
return out.join(' | ');
