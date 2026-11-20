const TARGET = '046a237b7518687e';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const pads = await eda.pcb_PrimitivePad.getAll();
// back-side SMD pad candidates: pad records may carry layer; also collect front TH (J/LED/U)
const rec = [];
for (const p of pads) rec.push({x: p.x, y: p.y, net: p.net, layer: p.layer, pad: p.pad});
return JSON.stringify(rec);
