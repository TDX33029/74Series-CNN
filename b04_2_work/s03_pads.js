const TARGET = '1595c28f09776867';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + (doc && doc.uuid);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  const des = c.getState_Designator();
  let pins = [];
  try {
    const a = c.toAsync();
    pins = await a.getAllPins();
  } catch (e) {
    out.push({des: des, err: String(e)});
    continue;
  }
  const pads = (pins || []).map(p => ({n: p.padNumber, x: p.x, y: p.y, net: p.net, pad: p.pad}));
  out.push({des: des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer(), npads: pads.length, pads: pads});
}
return JSON.stringify(out);
