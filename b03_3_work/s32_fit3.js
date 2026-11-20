const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
await eda.dmt_EditorControl.zoomToAllPrimitives();
const img = await eda.dmt_EditorControl.getCurrentRenderedAreaImage();
return 'zoom ok, img type: ' + (typeof img) + (typeof img === 'string' ? ' len=' + img.length : '');
