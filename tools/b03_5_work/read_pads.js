const PCB = '42f9160329b94bb4';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== PCB) return 'ABORT: wrong document ' + doc.uuid;
const pads = await eda.pcb_PrimitivePad.getAll();
const out = pads.map(p => ({x: p.x, y: p.y, net: p.net, num: p.padNumber, pad: p.pad, layer: p.layer}));
return JSON.stringify({n: pads.length, pads: out});
