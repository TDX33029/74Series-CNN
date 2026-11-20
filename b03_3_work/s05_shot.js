const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
// fit view: zoom to fit all
try { await eda.dmt_EditorControl.zoomFit(); } catch(e) {}
return 'zoomFit done';
