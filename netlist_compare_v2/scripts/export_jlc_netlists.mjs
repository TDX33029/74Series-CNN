// Export schematic netlist (Protel2) for every page of every board in 74CNN-BRD
// via the easyeda-bridge HTTP API. Writes one .net file per page.
import fs from 'node:fs';
import path from 'node:path';

const BRIDGE = 'http://localhost:49620';
const OUT = String.raw`D:\Document\tempPrj\74Series-CNN\netlist_compare_v2\jlc_netlists`;
const BOARDS_JSON = String.raw`D:\Document\tempPrj\74Series-CNN\netlist_compare_v2\boards_pages.json`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function exec(code, tries = 2) {
  for (let a = 0; a < tries; a++) {
    try {
      const res = await fetch(`${BRIDGE}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      const j = await res.json();
      if (j.success) return j.result;
      if (a === tries - 1) throw new Error(typeof j.error === 'string' ? j.error : JSON.stringify(j.error));
      await sleep(1500);
    } catch (e) {
      if (a === tries - 1) throw e;
      await sleep(1500);
    }
  }
}

async function main() {
  const boards = JSON.parse(fs.readFileSync(BOARDS_JSON, 'utf8')).result;
  const only = process.argv[2] ? process.argv[2].split(',') : null;
  const manifest = [];
  let done = 0;
  const total = boards.reduce((s, b) => s + b.pages.length, 0);
  for (const b of boards) {
    if (only && !only.includes(b.board)) continue;
    for (const p of b.pages) {
      const fname = `${b.board}__${p.name}.net`;
      const fpath = path.join(OUT, fname);
      done++;
      if (fs.existsSync(fpath) && fs.statSync(fpath).size > 10) {
        manifest.push({ board: b.board, page: p.name, file: fname, skipped: true });
        continue;
      }
      const label = `[${done}/${total}] ${b.board} / ${p.name}`;
      try {
        const act = await exec(`return await eda.dmt_EditorControl.openDocument(${JSON.stringify(p.uuid)});`);
        await sleep(600);
        const code = `
const f = await eda.sch_ManufactureData.getNetlistFile(${JSON.stringify(fname)}, 'Protel2');
if (!f) return { error: 'no file returned' };
const t = await f.text();
return { size: t.length, text: t };`;
        const r = await exec(code);
        if (r && r.text && r.size > 10) {
          fs.writeFileSync(fpath, r.text, 'utf8');
          manifest.push({ board: b.board, page: p.name, file: fname, chars: r.size, activated: act });
          console.log(`${label} OK ${r.size} chars`);
        } else {
          manifest.push({ board: b.board, page: p.name, file: fname, error: 'empty netlist', detail: r });
          console.log(`${label} EMPTY`);
        }
      } catch (e) {
        manifest.push({ board: b.board, page: p.name, file: fname, error: String(e.message || e) });
        console.log(`${label} ERROR ${e.message || e}`);
      }
      await sleep(150);
    }
  }
  fs.writeFileSync(path.join(OUT, '..', 'export_manifest.json'), JSON.stringify(manifest, null, 1), 'utf8');
  const errs = manifest.filter((m) => m.error);
  console.log(`DONE. pages=${manifest.length} errors=${errs.length}`);
}

main().catch((e) => { console.error('FATAL', e); process.exit(1); });
