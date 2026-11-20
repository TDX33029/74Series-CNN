const comps = await eda.pcb_PrimitiveComponent.getAll();
const out=[];
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  if(!des.startsWith('U')) continue;
  const a=c.toAsync();
  out.push({des, x:a.getState_X(), y:a.getState_Y(), rot:a.getState_Rotation(), layer:a.getState_Layer()});
}
out.sort((p,q)=>p.x-q.x || p.y-q.y);
return JSON.stringify(out);
