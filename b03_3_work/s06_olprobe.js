const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const polys = await eda.pcb_PrimitivePolyline.getAll();
const ol = polys[0];
const dump = {};
const keys = Object.keys(ol);
dump.keys = keys;
const getters = {};
for (const k of keys) {
  if (typeof k === 'string' && k.startsWith('getState_')) {
    try { getters[k] = ol[k](); } catch(e) { getters[k] = 'ERR'; }
  }
}
dump.getters = getters;
dump.polygonRaw = JSON.stringify(ol.polygon);
// also try async state
try { const a = ol.toAsync(); dump.asyncXY = {x: a.getState_X(), y: a.getState_Y()}; } catch(e) { dump.asyncXY = 'ERR:'+e.message; }
return JSON.stringify(dump);
