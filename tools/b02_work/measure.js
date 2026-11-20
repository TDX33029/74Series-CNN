const TARGET = 'a8a7bb9eb952a5f7';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const comps = await eda.pcb_PrimitiveComponent.getAll();
const out = {};
const wanted = comps.filter(c => { const d = c.getState_Designator(); return d && (d.startsWith('U') || d === 'J20101'); });
for (const c of wanted) {
  try {
    const pins = await c.toAsync().getAllPins();
    const arr = pins.map(p => ({x: p.x, y: p.y, pad: p.pad, shape: p.shape}));
    const xs = arr.map(p => p.x), ys = arr.map(p => p.y);
    out[c.getState_Designator()] = {
      n: arr.length,
      xmin: Math.min(...xs), xmax: Math.max(...xs),
      ymin: Math.min(...ys), ymax: Math.max(...ys),
      shapes: [...new Set(arr.map(p => JSON.stringify(p.pad || p.shape)))].slice(0, 4),
      pads: arr.slice(0, 4).map(p => ({x: p.x, y: p.y, pad: p.pad, shape: p.shape}))
    };
  } catch(e) { out[c.getState_Designator()] = {err: String(e)}; }
}
return JSON.stringify(out);
