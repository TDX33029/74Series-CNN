const TARGET='c03b63553aa7180b';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc.uuid!==TARGET) return 'ABORT: wrong document '+doc.uuid;
const comps=await eda.pcb_PrimitiveComponent.getAll();
const plan=[["RP1",3565,-3140,90],
["Q3020",3565,-2948,90],
["Q3021",3565,-2826,90],
["Q3008",3565,-2704,90],
["Q3002",3565,-2146,90],
["Q3009",3565,-2582,90],
["Q3017",3565,-2024,90],
["Q3018",3565,-1902,90],
["Q3010",3565,-1780,90],
["Q3011",3565,-1658,90],
["Q3012",3565,-1536,90],
["Q3013",3565,-1414,90],
["Q3014",3565,-1292,90],
["Q3015",3565,-1170,90],
["Q3003",3565,-1048,90],
["Q3004",3565,-926,90],
["Q3005",3565,-804,90],
["Q3006",3565,-682,90],
["Q3007",3565,-560,90],
["Q3016",3565,-2460,90],
["Q3019",3565,-2338,90]];
let placed=0,miss=[];
for(const [des,x,y,rot] of plan){
  const c=comps.find(k=>k.getState_Designator()===des);
  if(!c){miss.push(des);continue;}
  const a=c.toAsync();
  a.setState_X(x); a.setState_Y(y); a.setState_Rotation(rot);
  a.setState_Layer(2);
  await a.done();
  placed++;
}
return JSON.stringify({placed,miss});