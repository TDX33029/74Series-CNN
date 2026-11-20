const TARGET = '7ce97899ea288f46';
const doc = await eda.dmt_SelectControl.getCurrentDocumentInfo();
if (doc.uuid !== TARGET) return 'ABORT';
// args shape maybe {minx,miny,maxx,maxy} or 4 numbers
try { await eda.dmt_EditorControl.zoomToRegion(-200, 200, 4200, -3700); return 'positional ok'; } catch(e) { let e1 = e.message; }
try { await eda.dmt_EditorControl.zoomToRegion({minx: -200, miny: -3700, maxx: 4200, maxy: 200}); return 'minmax ok'; } catch(e) { return 'ERR ' + e.message; }
