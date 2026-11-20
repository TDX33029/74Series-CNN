const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
let zr = null;
try { zr = await eda.pcb_SelectControl.zoomToRegion(-3200, 4400, 600, -3800); } catch(e) { zr = 'e1:'+String(e); }
if (zr === null || typeof zr === 'string') {
  try { zr = await eda.dmt_EditorControl.navigateToRegion(-3200, 4400, 600, -3800); } catch(e) { zr = 'e2:'+String(e); }
}
const pads = await eda.pcb_PrimitivePad.getAll();
const out = pads.map(p => ({x: p.x, y: p.y, net: p.net, pad: p.pad, layer: p.layer, num: p.padNumber}));
return JSON.stringify({zr, n: out.length, pads: out});
