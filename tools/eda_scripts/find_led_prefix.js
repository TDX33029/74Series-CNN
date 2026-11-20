const comps = await eda.pcb_PrimitiveComponent.getAll();
const prefixes = {};
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  const m = des.match(/^([A-Za-z]+)\d+/);
  if(m) prefixes[m[1]] = (prefixes[m[1]]||0)+1;
}
return JSON.stringify(prefixes);
