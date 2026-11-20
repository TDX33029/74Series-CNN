// step3: definitive measurement — outline bbox, chip pads, passive pads+nets
const PCB = 'd760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const out = {outline: [], chips: [], others: []};

const polys = await eda.pcb_PrimitivePolyline.getAll();
for (const pl of polys) {
  let bb = null, bbErr = null;
  try { bb = await eda.pcb_Primitive.getPrimitivesBBox([pl]); } catch(e) { bbErr = String(e && e.message || e); }
  out.outline.push({
    id: pl.getState_PrimitiveId(),
    layer: pl.getState_Layer ? pl.getState_Layer() : null,
    polyX: pl.getState_X ? pl.getState_X() : null,
    polyY: pl.getState_Y ? pl.getState_Y() : null,
    polygon: pl.polygon,
    bbox: bb, bbErr
  });
}

const comps = await eda.pcb_PrimitiveComponent.getAll();
for (const c of comps) {
  const des = c.getState_Designator();
  const a = c.toAsync();
  let pins = null;
  try { pins = await a.getAllPins(); } catch(e) { pins = 'ERR:' + String(e && e.message || e); }
  const rec = {
    des,
    x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(),
    layer: c.getState_Layer ? c.getState_Layer() : null,
    fp: (c.getState_Footprint ? c.getState_Footprint() : null),
    pins
  };
  if (/^u/i.test(des)) out.chips.push(rec); else out.others.push(rec);
}
return JSON.stringify(out);
