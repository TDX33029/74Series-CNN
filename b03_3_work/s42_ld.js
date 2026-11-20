const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
// switch to bottom layer view? Just zoom to LED strip region for visual check using zoomToRegion(x,y,w,h) in mm observed behavior: earlier -200,200,4400,3700 gave similar wide view. Try (x=-100,y=-3300,w=100,h=100)mm? Behavior unclear; instead leave view.
return 'skip';
