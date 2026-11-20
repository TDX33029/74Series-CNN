const TARGET='d760df1fa8af5bfc';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const pls = await eda.pcb_PrimitivePolyline.getAll();
const out=[];
for(const p of pls){
  if(p.polygon) out.push({id:p.getState_PrimitiveId?String(p.getState_PrimitiveId()):'', poly:p.polygon, layer:(()=>{try{return p.getState_Layer();}catch(e){return null;}})()});
}
return JSON.stringify(out);
