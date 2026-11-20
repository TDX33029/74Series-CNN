const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const res = [];
for (const c of comps) {
  const d = c.getState_Designator();
  if (!d) continue;
  const a = c.toAsync();
  res.push({des: d, x: Math.round(a.getState_X()*10)/10, y: Math.round(a.getState_Y()*10)/10, rot: a.getState_Rotation(), layer: a.getState_Layer()});
}
const polys = await eda.pcb_PrimitivePolyline.getAll();
const outline = polys.map(p => p.polygon ? p.polygon.polygon : null).filter(Boolean);
return JSON.stringify({outline, comps: res});
