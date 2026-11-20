const TARGET = 'e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;
const polys = await eda.pcb_PrimitivePolyline.getAll();
const out = [];
for (const p of polys) {
  const info = {full: null, states: {}};
  try { info.full = JSON.stringify(p).slice(0, 2000); } catch(e) { info.full = 'unserializable'; }
  for (const m of ['X','Y','Layer','Rotation','PrimitiveId']) {
    try { info.states[m] = p['getState_'+m](); } catch(e) { info.states[m] = 'ERR'; }
  }
  let bb1=null, bb2=null;
  try { bb1 = eda.pcb_Primitive.getPrimitivesBBox([p]); } catch(e) { bb1 = String(e); }
  try { bb2 = eda.pcb_Primitive.getPrimitivesBBox(p); } catch(e) { bb2 = String(e); }
  info.bb_arr = bb1; info.bb_obj = bb2;
  out.push(info);
}
return JSON.stringify(out);
