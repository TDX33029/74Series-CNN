const TARGET='e4b2cb67c3463844';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (!doc || doc.uuid !== TARGET) return 'ABORT: wrong document ' + JSON.stringify(doc);
const r = await eda.pcb_Drc.check(true, false, true);
const arr = Array.isArray(r) ? r : [];
const detail=[];
for(const cat of arr){
  if(String(cat.name).indexOf('Connection')>=0) continue;
  for(const s of (cat.list||[])){
    for(const it of (s.list||[]).slice(0,10)){
      detail.push({sub:s.name, o1:it.obj1Suffix, o2:it.obj2Suffix, d:it.errData&&it.errData.minDistance});
    }
  }
}
return JSON.stringify(arr.map(c=>({name:c.name,n:(c.list||[]).reduce((s,sub)=>s+(sub.list?sub.list.length:0),0)}))) + ' DET:' + JSON.stringify(detail);
