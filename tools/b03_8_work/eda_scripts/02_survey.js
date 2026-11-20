const TARGET='c03b63553aa7180b';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc.uuid!==TARGET) return 'ABORT: wrong document '+doc.uuid;
const comps=await eda.pcb_PrimitiveComponent.getAll();
const out={comps:[]};
for(const c of comps){
  out.comps.push({des:c.getState_Designator(),x:c.getState_X(),y:c.getState_Y(),rot:c.getState_Rotation(),layer:c.getState_Layer(),foot:c.getState_Footprint?c.getState_Footprint():''});
}
const pls=await eda.pcb_PrimitivePolyline.getAll();
out.polygons=pls.map(pl=>({id:pl.getState_PrimitiveId(),layer:pl.getState_Layer(),polygon:pl.polygon}));
return JSON.stringify(out);
