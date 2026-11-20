const TARGET='7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const comps = await eda.pcb_PrimitiveComponent.getAll();
const g=(a,k)=>{try{return a['getState_'+k]();}catch(e){return null;}};
const out=[];
for(const c of comps){
  const des=String(c.getState_Designator()||'');
  const a=c.toAsync();
  out.push({des, x:g(a,'X'), y:g(a,'Y'), rot:g(a,'Rotation'), layer:g(a,'Layer')});
}
return JSON.stringify(out);
