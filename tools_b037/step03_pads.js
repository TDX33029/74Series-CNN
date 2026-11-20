const TARGET = '046a237b7518687e';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  const a = c.toAsync();
  const rec = {
    des: c.getState_Designator(),
    x: c.getState_X(), y: c.getState_Y(),
    rot: c.getState_Rotation(), layer: c.getState_Layer(),
    pins: []
  };
  try {
    const pins = await a.getAllPins();
    if (pins && pins.length) {
      for (const p of pins) {
        rec.pins.push({n: p.padNumber, net: p.net, x: p.x, y: p.y, pad: p.pad});
      }
    }
  } catch (e) { rec.err = String(e); }
  out.push(rec);
}
return JSON.stringify(out);
