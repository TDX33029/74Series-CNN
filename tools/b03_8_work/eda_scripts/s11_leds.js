const TARGET='c03b63553aa7180b';
const doc=await eda.dmt_SelectControl.getCurrentDocumentInfo();
if(doc.uuid!==TARGET) return 'ABORT: wrong document '+doc.uuid;
const comps=await eda.pcb_PrimitiveComponent.getAll();
const plan=[["LEDP1",3822.5,-3140,0],
["LED_C1_ADDR0",3822.5,-2948,0],
["LED_C1_ADDR1",3822.5,-2826,0],
["LED_C1_BUSY_N",3822.5,-2704,0],
["LED_FC1_BUSY_N",3822.5,-2582,0],
["LED_NOT_LOAD_EN",3822.5,-2460,0],
["LED_POOL2_MEM_NCE_OUT",3822.5,-2338,0],
["LED_DATA1",3822.5,-2146,0],
["LED_LOAD_DATA0",3822.5,-2024,0],
["LED_LOAD_DATA1",3822.5,-1902,0],
["LED_LOAD_DATA2",3822.5,-1780,0],
["LED_LOAD_DATA3",3822.5,-1658,0],
["LED_LOAD_DATA4",3822.5,-1536,0],
["LED_LOAD_DATA5",3822.5,-1414,0],
["LED_LOAD_DATA6",3822.5,-1292,0],
["LED_LOAD_DATA7",3822.5,-1170,0],
["LED_MEM_D0",3822.5,-1048,0],
["LED_MEM_D1",3822.5,-926,0],
["LED_MEM_D2",3822.5,-804,0],
["LED_MEM_D3",3822.5,-682,0],
["LED_MEM_D4",3822.5,-560,0]];
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