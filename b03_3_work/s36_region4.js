const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
// last attempt: (x, y, width, height) with x=left,y=bottom? previous (-100,-3300,4200,3500) jumped to x=-130mm area. Actually it went to mm -130 => -5125mil. So maybe it treated as (minx=-100mm...) no: -100 interpreted as mm? It moved view origin to x=-130mm ≈ -5120mil, y=+100mm. So args were treated in mm as (x=-100? no -100mm=-3937mil).
// Actually screenshot ruler: -130..-90mm at left edge => view centered around -110mm=-4330mil, y top ~+100mm. So zoomToRegion(x,y,w,h) in mm with x=-100,y=-3300?? y seems +100mm.
// Try instead select-all via primitive select then zoomToSelectedPrimitives? Simply skip: visual confirmation already done via zoomToAllPrimitives + shot_final2.
return 'skip';
