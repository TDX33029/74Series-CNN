const TARGET = '822ec5745398cfb8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const leds = ['LED5','LED_ADDR_TAG_OK','LED_ADDR_TAG_OK_N','LED_BOTH_IDLE','LED_C1_BUSY_N','LED_DIR_SEL','LED_FC1_BUSY_N','LED_LOAD_NWE','LED_MEM_CE_OK','LED_MSEL0','LED_MSEL1','LED_MSEL2','LED_MSEL3','LED_MSEL4','LED_NOT_LOAD_EN','LED_NOT_MSEL3','LED_NOT_MSEL4','LED_MADDR16','LED_MADDR17','LED_POOL2_MEM_NCE_OUT'];
let n = 0;
for (const des of leds) {
  const c = comps.find(k => k.getState_Designator() === des);
  if (!c) continue;
  const a = c.toAsync();
  a.setState_Layer(1);
  a.setState_X(3822.5);
  a.setState_Rotation(0);
  await a.done();
  n++;
}
// R10 竖放
const r10 = comps.find(k => k.getState_Designator() === 'R10');
const a2 = r10.toAsync();
a2.setState_X(3420); a2.setState_Y(-1124); a2.setState_Rotation(90); a2.setState_Layer(2);
await a2.done();
return 'flipped ' + n + ' LEDs to front; R10 vertical at (3420,-1124)';
