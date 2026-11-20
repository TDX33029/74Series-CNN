const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
await eda.dmt_EditorControl.zoomToAllPrimitives();
return 'ok';
