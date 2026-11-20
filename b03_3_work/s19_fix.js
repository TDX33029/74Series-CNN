const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
// shift PWR group (bottom 12 LEDs y<=-2048) and their module rows up-free: actually shift LEDP1-row boundary.
// Simplest compliant: move LEDs with y >= -1744 (LEDP1 row and above) up by 6 => pitch 128 between READ_OE and LEDP1
const shift = [['LEDP1',-1744],['LED_DATA3',-1622],['LED_FC2_ADDR10',-1500],['LED_FC2_ADDR11',-1378],['LED_MADDR13',-1256],['LED_MADDR14',-1134],['LED_MADDR15',-1012],['LED_MEM_D0',-890],['LED_MEM_D1',-768]];
for (const [des, y] of shift) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_Y(y + 6);
  await a.done();
}
// move their back modules too (Q/R on same rows)
const backshift = [['RP1',-1744],['Q3004',-1622],['R3008',-1622],['R3007',-1622],['Q3022',-1500],['R3039',-1500],['R3038',-1500],['Q3023',-1378],['R3041',-1378],['R3040',-1378],['Q3019',-1256],['R3033',-1256],['R3032',-1256],['Q3020',-1134],['R3035',-1134],['R3034',-1134],['Q3021',-1012],['R3037',-1012],['R3036',-1012],['Q3008',-890],['R4',-890],['R3012',-890],['Q3009',-768],['R5',-768],['R3013',-768]];
for (const [des, y] of backshift) {
  const c = comps.find(k => k.getState_Designator() === des);
  const a = c.toAsync();
  a.setState_Y(y + 6);
  await a.done();
}
return 'shifted ' + (shift.length + backshift.length);
