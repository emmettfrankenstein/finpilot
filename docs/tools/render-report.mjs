// Renders docs/architecture.md (with Mermaid diagrams) to PDF.
// Usage (from a directory with marked, mermaid and playwright installed):
//   node render-report.mjs ../architecture.md ../FinPilot_Architecture_Report.pdf

import { readFileSync } from 'node:fs';
import { marked } from 'marked';
import { chromium } from 'playwright';

const [src, out] = process.argv.slice(2);
const md = readFileSync(src, 'utf8');
const renderer = new marked.Renderer();
const baseCode = renderer.code.bind(renderer);
renderer.code = (token) => token.lang === 'mermaid' ? `<div class="diagram"><pre class="mermaid">${token.text}</pre></div>` : baseCode(token);
const body = marked.parse(md, { renderer });
const mermaid = readFileSync('node_modules/mermaid/dist/mermaid.min.js', 'utf8');
const html = `<!doctype html><html><head><meta charset="utf-8"><style>
@page { size: A4; margin: 16mm 15mm 18mm; }
body { font-family: 'Segoe UI', 'DejaVu Sans', Arial, sans-serif; font-size: 10pt; line-height: 1.45; color: #17212b; }
h1 { font-size: 22pt; color: #1f4e8c; margin: 0 0 4pt; }
h1 + p { color: #5d6b7a; margin-top: 0; }
h2 { font-size: 14pt; color: #1f4e8c; border-bottom: 1.5px solid #1f4e8c; padding-bottom: 3pt; margin-top: 18pt; break-after: avoid; }

h3 { font-size: 11.5pt; margin-top: 12pt; break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 8.8pt; break-inside: auto; }
tr { break-inside: avoid; }
th, td { border: 1px solid #cfd8e3; padding: 3pt 5pt; text-align: left; vertical-align: top; }
th { background: #eef3fa; }
code { font-family: 'DejaVu Sans Mono', monospace; font-size: 8.5pt; background: #f2f4f7; padding: 0 2pt; border-radius: 2px; }
pre code { display: block; padding: 6pt; white-space: pre-wrap; }
.diagram { break-inside: avoid; text-align: center; margin: 8pt 0 12pt; }
.diagram svg { max-width: 100%; height: auto; max-height: 165mm; }
ul { padding-left: 16pt; }
</style></head><body>${body}<script>${mermaid}</script>
<script>mermaid.initialize({ startOnLoad: false, theme: 'neutral', securityLevel: 'strict', flowchart: { htmlLabels: true, useMaxWidth: true }, er: { useMaxWidth: true }, sequence: { useMaxWidth: true } });
mermaid.run({ querySelector: '.mermaid' }).then(() => { document.body.dataset.done = '1'; }).catch((e) => { document.body.dataset.done = 'err:' + e.message; });</script></body></html>`;
const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent(html, { waitUntil: 'load' });
await page.waitForFunction(() => document.body.dataset.done, null, { timeout: 30000 });
const status = await page.evaluate(() => document.body.dataset.done);
const errors = await page.$$eval('.mermaid', (els) => els.filter((e) => !e.querySelector('svg')).length);
console.log('mermaid', status, 'unrendered', errors);
await page.pdf({ path: out, format: 'A4', printBackground: true, displayHeaderFooter: true,
  headerTemplate: '<span></span>',
  footerTemplate: '<div style="font-size:7pt;color:#777;width:100%;text-align:center">FinPilot architecture report · page <span class="pageNumber"></span> of <span class="totalPages"></span></div>',
  margin: { top: '16mm', bottom: '18mm', left: '15mm', right: '15mm' } });
await browser.close();
