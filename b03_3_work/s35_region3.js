const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
// positional (minx, miny, width, height)?
await eda.dmt_EditorControl.zoomToRegion(-100, -3300, 4200, 3500);
return 'ok';
