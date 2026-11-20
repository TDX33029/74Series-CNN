const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const plan = [
  ['LEDP1', 3823.0, 3164.85, 0],
  ['LED_CLK', 3823.0, 2982.85, 0],
  ['LED_CNT_CLR_N', 3823.0, 2860.85, 0],
  ['LED_IDLE_N', 3823.0, 2738.85, 0],
  ['LED_REQ', 3823.0, 2616.85, 0],
  ['LED_RESET_N', 3823.0, 2494.85, 0],
  ['LED_WE', 3823.0, 2372.85, 0],
  ['LED_WE_S', 3823.0, 2250.85, 0],
  ['LED_ACK_I', 3823.0, 2068.85, 0],
  ['LED_CNT0', 3823.0, 1946.85, 0],
  ['LED_CNT1', 3823.0, 1824.85, 0],
  ['LED_CNT2', 3823.0, 1702.85, 0],
  ['LED_CNT3', 3823.0, 1580.85, 0],
  ['LED_DONE_I', 3823.0, 1458.85, 0],
  ['LED_DONE_ST_N', 3823.0, 1336.85, 0],
  ['LED_MC1', 3823.0, 1214.85, 0],
  ['LED_MC2', 3823.0, 1092.85, 0],
  ['LED_MEM_ACK', 3823.0, 970.8499999999999, 0],
  ['LED_MEM_BUSY', 3823.0, 848.8499999999999, 0],
  ['LED_MEM_DONE', 3823.0, 726.8499999999999, 0],
  ['LED_MEM_NCE', 3823.0, 604.8499999999999, 0],
  ['LED_MEM_NOE', 3823.0, 482.8499999999999, 0],
  ['LED_MEM_NWE', 3823.0, 360.8499999999999, 0],
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
