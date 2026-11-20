
const PCB = '42f9160329b94bb4';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const plan = [["LEDP1", 3822.5, -3146.0], ["LED_IMAGE_DONE_N", 3822.5, -2954.0], ["LED_IMAGE_READY", 3822.5, -2832.0], ["LED_MODEL_DONE_N", 3822.5, -2710.0], ["LED_MODEL_READY", 3822.5, -2588.0], ["LED_NCS_LUT0_HI", 3822.5, -2466.0], ["LED_NCS_LUT0_LO", 3822.5, -2344.0], ["LED_NCS_LUT1_HI", 3822.5, -2222.0], ["LED_NCS_LUT1_LO", 3822.5, -2100.0], ["LED_NCS_LUT2_HI", 3822.5, -1978.0], ["LED_NCS_LUT2_LO", 3822.5, -1856.0], ["LED_NCS_LUT3_HI", 3822.5, -1734.0], ["LED_NCS_LUT3_LO", 3822.5, -1612.0], ["LED_NCS_W_CONV1", 3822.5, -1490.0], ["LED_NCS_W_CONV2", 3822.5, -1368.0], ["LED_NCS_W_FC1", 3822.5, -1246.0], ["LED_NCS_W_FC2", 3822.5, -1124.0], ["LED_NOT_MSEL3", 3822.5, -1002.0], ["LED_NOT_MSEL4", 3822.5, -880.0], ["LED_DATA0", 3822.5, -688.0], ["LED_DATA2", 3822.5, -566.0]];
const comps = await eda.pcb_PrimitiveComponent.getAll();
let placed = 0; const missing = [];
for (const [des, x, y] of plan) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) { missing.push(des); continue; }
  const a = c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(0); a.setState_Layer(1);
  await a.done();
  placed++;
}
const rb = plan.map(([des]) => { const c = comps.find(k => k.getState_Designator() === des);
  return {des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer()}; });
return JSON.stringify({placed, missing, rb});
