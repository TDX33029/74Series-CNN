const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = {};
for (const c of comps) {
  const des = c.getState_Designator();
  if (!des || !(des.startsWith('R') || des.startsWith('Q') || des.startsWith('LED') || des.startsWith('RP'))) continue;
  try {
    const pins = await c.toAsync().getAllPins();
    const arr = pins.map(p => ({x: p.x, y: p.y, pad: p.pad}));
    const xs = arr.map(p => p.x), ys = arr.map(p => p.y);
    out[des] = {n: arr.length, xmin: Math.min(...xs), xmax: Math.max(...xs), ymin: Math.min(...ys), ymax: Math.max(...ys), shapes: [...new Set(arr.map(p => JSON.stringify(p.pad)))], rot: c.getState_Rotation(), layer: c.getState_Layer()};
  } catch(e) { out[des] = {err: String(e)}; }
}
return JSON.stringify(out);
