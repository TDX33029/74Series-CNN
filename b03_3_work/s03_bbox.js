const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT: wrong document ' + doc.uuid;

const polys = await eda.pcb_PrimitivePolyline.getAll();
const ol = polys[0];
let olBBox = null;
try { olBBox = eda.pcb_Primitive.getPrimitivesBBox([ol]); } catch(e) { olBBox = 'ERR:' + e.message; }

const comps = await eda.pcb_PrimitiveComponent.getAll();
function findDes(d){ return comps.find(c => c.getState_Designator() === d); }
const probe = {};
for (const d of ['J20203','U4005','U4032','LEDP1','Q3004','R3007']) {
  const c = findDes(d);
  if (!c) { probe[d] = 'NOTFOUND'; continue; }
  try { probe[d] = eda.pcb_Primitive.getPrimitivesBBox([c]); } catch(e) { probe[d] = 'ERR:' + e.message; }
}
return JSON.stringify({olBBox, probe});
