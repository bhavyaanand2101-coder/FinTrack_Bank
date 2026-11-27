/**
 * FinTrack DBMS Capstone Project Report PDF Generator
 * Uses 'marked' to compile Markdown to HTML, inlines high-res screenshots as base64,
 * and renders a publication-grade PDF via headless Google Chrome / Puppeteer.
 */

import puppeteer from 'puppeteer-core';
import { marked } from 'marked';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const ROOT_DIR = path.resolve(__dirname, '../../');
const REPORT_MD_PATH = path.join(ROOT_DIR, 'PROJECT_REPORT.md');
const SCREENSHOTS_DIR = path.join(ROOT_DIR, 'docs/screenshots');
const OUTPUT_PDF_ROOT = path.join(ROOT_DIR, 'FinTrack_DBMS_Capstone_Project_Report.pdf');
const OUTPUT_PDF_DOCS = path.join(ROOT_DIR, 'docs/FinTrack_DBMS_Capstone_Project_Report.pdf');
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

async function generate() {
  console.log('📄 Reading PROJECT_REPORT.md...');
  let mdContent = fs.readFileSync(REPORT_MD_PATH, 'utf-8');

  // Convert image references to base64 Data URIs for guaranteed rendering
  console.log('🖼️  Inlining screenshot images as Base64 Data URIs...');
  const imgRegex = /!\[([^\]]*)\]\(([^)]+)\)/g;
  mdContent = mdContent.replace(imgRegex, (match, alt, imgPath) => {
    // Extract filename
    const filename = path.basename(imgPath);
    const localImagePath = path.join(SCREENSHOTS_DIR, filename);
    if (fs.existsSync(localImagePath)) {
      const base64Data = fs.readFileSync(localImagePath).toString('base64');
      const dataUri = `data:image/png;base64,${base64Data}`;
      return `\n<div class="figure-container">\n  <img src="${dataUri}" alt="${alt}" class="report-screenshot" />\n  <p class="figure-caption">${alt}</p>\n</div>\n`;
    }
    return match;
  });

  console.log('⚙️  Parsing Markdown to HTML with marked...');
  const bodyHtml = marked.parse(mdContent);

  const fullHtml = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>FinTrack - DBMS Capstone Project Report</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    @page {
      size: A4;
      margin: 18mm 16mm 20mm 16mm;
      @bottom-right {
        content: counter(page) " / " counter(pages);
        font-family: 'Inter', sans-serif;
        font-size: 8pt;
        color: #64748b;
      }
    }

    * {
      box-sizing: border-box;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      font-size: 10pt;
      line-height: 1.6;
      color: #1e293b;
      background: #ffffff;
      margin: 0;
      padding: 0;
    }

    h1, h2, h3, h4, h5, h6 {
      color: #0f172a;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin-top: 1.4em;
      margin-bottom: 0.5em;
    }

    h1 {
      font-size: 20pt;
      border-bottom: 2px solid #2563eb;
      padding-bottom: 6px;
      margin-top: 0;
      color: #1e3a8a;
    }

    h2 {
      font-size: 14pt;
      border-bottom: 1px solid #cbd5e1;
      padding-bottom: 4px;
      margin-top: 1.8em;
      page-break-after: avoid;
    }

    h3 {
      font-size: 11.5pt;
      color: #1e40af;
      margin-top: 1.2em;
      page-break-after: avoid;
    }

    h4 {
      font-size: 10.5pt;
      page-break-after: avoid;
    }

    p {
      margin-top: 0;
      margin-bottom: 0.8em;
      text-align: justify;
    }

    /* Cover / Academic Header */
    .report-header {
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
      color: #ffffff;
      padding: 24px;
      border-radius: 8px;
      margin-bottom: 24px;
    }

    .report-header h1 {
      color: #ffffff;
      border: none;
      padding: 0;
      margin: 0 0 8px 0;
      font-size: 22pt;
    }

    .report-header p {
      color: #e0e7ff;
      margin: 4px 0;
      font-size: 9.5pt;
    }

    /* Tables */
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 12px 0 16px 0;
      font-size: 8.5pt;
      page-break-inside: avoid;
    }

    th, td {
      border: 1px solid #cbd5e1;
      padding: 6px 10px;
      text-align: left;
      vertical-align: top;
    }

    th {
      background-color: #f1f5f9;
      color: #0f172a;
      font-weight: 600;
    }

    tr:nth-child(even) td {
      background-color: #f8fafc;
    }

    /* Code & Syntax */
    code {
      font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
      font-size: 8.5pt;
      background: #f1f5f9;
      color: #0f172a;
      padding: 1px 4px;
      border-radius: 3px;
    }

    pre {
      background: #0f172a;
      color: #f8fafc;
      padding: 12px 14px;
      border-radius: 6px;
      overflow-x: auto;
      font-size: 8pt;
      line-height: 1.45;
      margin: 10px 0 14px 0;
      page-break-inside: avoid;
    }

    pre code {
      background: transparent;
      color: inherit;
      padding: 0;
    }

    /* Callout & Alerts */
    blockquote {
      border-left: 4px solid #2563eb;
      background: #eff6ff;
      margin: 12px 0;
      padding: 10px 14px;
      border-radius: 0 6px 6px 0;
      font-size: 9pt;
      color: #1e3a8a;
    }

    blockquote p {
      margin: 0;
    }

    /* Screenshot Figures */
    .figure-container {
      margin: 14px 0 18px 0;
      text-align: center;
      page-break-inside: avoid;
    }

    .report-screenshot {
      max-width: 96%;
      height: auto;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
    }

    .figure-caption {
      font-size: 8pt;
      color: #64748b;
      margin-top: 6px;
      font-weight: 500;
      font-style: italic;
      text-align: center;
    }

    ul, ol {
      margin: 0 0 12px 0;
      padding-left: 22px;
    }

    li {
      margin-bottom: 4px;
    }

    hr {
      border: 0;
      height: 1px;
      background: #e2e8f0;
      margin: 20px 0;
    }

    .page-break {
      page-break-before: always;
    }
  </style>
</head>
<body>
  ${bodyHtml}
</body>
</html>`;

  console.log('🌐 Launching headless Chrome engine via Puppeteer...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--font-render-hinting=medium']
  });

  const page = await browser.newPage();
  await page.setContent(fullHtml, { waitUntil: 'load' });
  await new Promise(r => setTimeout(r, 1000));

  console.log('🖨️  Rendering print-grade vectorized A4 PDF...');
  const pdfBuffer = await page.pdf({
    path: OUTPUT_PDF_ROOT,
    format: 'A4',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: `
      <div style="width: 100%; font-size: 8pt; font-family: 'Inter', sans-serif; color: #64748b; padding: 0 16mm; display: flex; justify-content: space-between;">
        <span>FinTrack DBMS Capstone Project Report</span>
        <span>Page <span class="pageNumber"></span> of <span class="totalPages"></span></span>
      </div>
    `,
    margin: {
      top: '16mm',
      bottom: '18mm',
      left: '14mm',
      right: '14mm'
    }
  });

  // Also copy to docs/ directory
  fs.copyFileSync(OUTPUT_PDF_ROOT, OUTPUT_PDF_DOCS);

  await browser.close();

  const stats = fs.statSync(OUTPUT_PDF_ROOT);
  const sizeMb = (stats.size / (1024 * 1024)).toFixed(2);
  console.log(`✅ Success! Generated PDF Report: ${OUTPUT_PDF_ROOT} (${sizeMb} MB)`);
  console.log(`📁 Duplicate saved to docs: ${OUTPUT_PDF_DOCS}`);
}

generate().catch(err => {
  console.error('❌ Failed to generate PDF report:', err);
  process.exit(1);
});
