const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
try { await eda.dmt_ViewControl.fitAll(); return 'fitAll ok'; } catch(e) {}
try { await eda.dmt_ViewControl.zoomFit(); return 'zoomFit ok'; } catch(e) { return 'ERR1:'+e.message; }
