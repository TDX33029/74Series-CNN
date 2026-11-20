const TARGET = '7f08bbdec72478d8';
await eda.dmt_Project.openProject('86c1d8c59be2462ebb49fab075a5c297');
await new Promise(r => setTimeout(r, 1500));
await eda.dmt_EditorControl.openDocument(TARGET);
await new Promise(r => setTimeout(r, 2500));
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = [];
for (const c of comps) {
  let layer = null;
  try { layer = c.getState_Layer(); } catch (e) {}
  out.push({des: c.getState_Designator(), x: c.getState_X(), y: c.getState_Y(),
    rot: c.getState_Rotation(), layer: layer});
}
const polys = await eda.pcb_PrimitivePolyline.getAll();
const plOut = [];
for (const pl of polys) {
  let layer = null;
  try { layer = pl.getState_Layer(); } catch (e) {}
  plOut.push({layer: layer, polygon: pl.polygon});
}
return JSON.stringify({docType: doc.documentType, polys: plOut, comps: out});
