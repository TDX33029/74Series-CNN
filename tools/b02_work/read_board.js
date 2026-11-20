const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const polys = await eda.pcb_PrimitivePolyline.getAll();
const outlines = [];
for (const pl of polys) {
  try {
    const pg = pl.polygon;
    if (pg) outlines.push({id: pl.getState_PrimitiveId ? pl.getState_PrimitiveId() : null, layer: pl.getState_Layer ? pl.getState_Layer() : null, polygon: pg});
  } catch(e) {}
}
const comps = await eda.pcb_PrimitiveComponent.getAll();
const list = [];
for (const c of comps) {
  const des = c.getState_Designator();
  list.push({des, x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer ? c.getState_Layer() : null, name: c.getState_Name()});
}
return JSON.stringify({outlines, comps: list}, null, 1);
