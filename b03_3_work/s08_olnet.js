const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const polys = await eda.pcb_PrimitivePolyline.getAll();
const out = polys.map(p => ({id: p.primitiveId, layer: p.layer, net: p.net, polygon: p.polygon && p.polygon.polygon}));
// Also check keepout layer polylines? getAll only returns layer 11? print count by layer
const byLayer = {};
for (const p of polys) { byLayer[p.layer] = (byLayer[p.layer]||0)+1; }
return JSON.stringify({count: polys.length, byLayer, out});
