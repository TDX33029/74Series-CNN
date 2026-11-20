const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = {board: [], comps: [], pads: null};
// board outline
const polys = await eda.pcb_PrimitivePolyline.getAll();
for (const p of polys) {
  out.board.push({id: p.getState_PrimitiveId ? p.getState_PrimitiveId() : '?', layer: p.getState_Layer ? p.getState_Layer() : '?', polygon: p.polygon});
}
// all components: designator, footprint, x, y, rotation, layer
for (const c of comps) {
  out.comps.push({des: c.getState_Designator(), name: c.getState_Name(), x: c.getState_X(), y: c.getState_Y(), rot: c.getState_Rotation(), layer: c.getState_Layer(), id: c.getState_PrimitiveId ? c.getState_PrimitiveId() : null});
}
return JSON.stringify(out);
