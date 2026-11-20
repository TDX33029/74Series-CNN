const comps = await eda.pcb_PrimitiveComponent.getAll();
const out=[];
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  if(/^(U|Q|R|J|RP)/.test(des)) continue;
  const a=c.toAsync();
  out.push({des, x:a.getState_X(), y:a.getState_Y(), rot:a.getState_Rotation(), layer:a.getState_Layer(), uid:String(c.getState_UniqueId()||'').slice(0,12)});
}
return JSON.stringify({total:comps.length, others:out});
