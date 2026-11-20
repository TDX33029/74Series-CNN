const TARGET='c03b63553aa7180b';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc.uuid!==TARGET) return 'ABORT: wrong document '+doc.uuid+' type='+doc.documentType;
const out={};
out.docType=doc.documentType;
// all components
const comps=await eda.pcb_PrimitiveComponent.getAll();
out.comps=[];
for(const c of comps){
  const o={des:c.getState_Designator(),x:c.getState_X(),y:c.getState_Y(),rot:c.getState_Rotation(),layer:c.getState_Layer()};
  out.comps.push(o);
}
// board outline polyline
const pls=await eda.pcb_PrimitivePolyline.getAll();
out.polygons=[];
for(const pl of pls){
  out.polygons.push({id:pl.getState_PrimitiveId(),layer:pl.getState_Layer(),polygon:pl.polygon});
}
return JSON.stringify(out);
