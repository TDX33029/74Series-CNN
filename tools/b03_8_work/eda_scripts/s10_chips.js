const TARGET='c03b63553aa7180b';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc.uuid!==TARGET) return 'ABORT: wrong document '+doc.uuid;
const comps=await eda.pcb_PrimitiveComponent.getAll();
const plan=[["U4029",560,-700,90],
["U4035",1100,-700,90],
["U4039",1640,-700,90],
["U4053",2180,-700,90]];
let placed=0,miss=[];
for(const [des,x,y,rot] of plan){
  const c=comps.find(k=>k.getState_Designator()===des);
  if(!c){miss.push(des);continue;}
  const a=c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  
  await a.done();
  placed++;
}
return JSON.stringify({placed,miss});