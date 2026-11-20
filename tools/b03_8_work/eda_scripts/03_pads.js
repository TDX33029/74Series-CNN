const TARGET='c03b63553aa7180b';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc.uuid!==TARGET) return 'ABORT: wrong document '+doc.uuid;
const comps=await eda.pcb_PrimitiveComponent.getAll();
const out=[];
for(const c of comps){
  const des=c.getState_Designator();
  const a=c.toAsync();
  const pins=await a.getAllPins();
  const pads=(pins||[]).map(p=>({n:p.padNumber,net:p.net,x:Math.round(p.x*100)/100,y:Math.round(p.y*100)/100,pad:p.pad}));
  out.push({des,x:c.getState_X(),y:c.getState_Y(),layer:c.getState_Layer(),pads});
}
return JSON.stringify(out);
