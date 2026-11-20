const PCB = '42f9160329b94bb4';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const chips = comps.filter(c => { const d = c.getState_Designator(); return d.startsWith('U'); });
const out = [];
for (const c of chips) {
  const des = c.getState_Designator();
  let pins = null, method = '';
  try {
    const a = c.toAsync();
    pins = await a.getAllPins();
    method = 'getAllPins';
  } catch(e) { method = 'err:' + e.message; }
  if (!pins || !pins.length) {
    try {
      pins = await eda.pcb_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
      method = 'byPrimId';
    } catch(e2) { method += '|err2:' + e2.message; }
  }
  const pads = (pins||[]).map(p => ({x: p.x, y: p.y, net: p.net, num: p.padNumber, pad: p.pad}));
  out.push({des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), method, npins: pads.length, pads});
}
return JSON.stringify(out);
