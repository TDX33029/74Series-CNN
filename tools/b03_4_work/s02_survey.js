const TARGET = '822ec5745398cfb8';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
// 板框
let outlines = [];
try {
  const pols = await eda.pcb_PrimitivePolyline.getAll();
  for (const p of pols) {
    let layer = -1;
    try { layer = p.getState_Layer(); } catch(e) {}
    let poly = null;
    try { poly = p.polygon; } catch(e) {}
    outlines.push({layer: layer, polygon: poly});
  }
} catch(e) { outlines = 'err: ' + e; }
// 全部器件
const comps = await eda.pcb_PrimitiveComponent.getAll();
const list = [];
for (const c of comps) {
  const des = c.getState_Designator();
  const a = c.toAsync();
  const x = a.getState_X(), y = a.getState_Y();
  let rot = 0, layer = 1, name = '';
  try { rot = a.getState_Rotation(); } catch(e) {}
  try { layer = a.getState_Layer(); } catch(e) {}
  try { name = a.getState_Name(); } catch(e) {}
  list.push({des: des, x: x, y: y, rot: rot, layer: layer});
}
return JSON.stringify({outlines: outlines, comps: list});
