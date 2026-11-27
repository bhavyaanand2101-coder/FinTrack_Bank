/**
 * FinTrack Automated UI Screenshot Capture Utility
 * Captures high-resolution production screenshots for the DBMS Capstone Project Report
 */

import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
// Root docs/screenshots directory
const SCREENSHOT_DIR = path.resolve(__dirname, '../../docs/screenshots');

const FRONTEND_URL = 'http://localhost:5174';
const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function capture() {
  console.log('🚀 Starting FinTrack Automated Screenshot Engine...');
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--window-size=1440,900']
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  // 1. Landing Page
  console.log('📸 1. Capturing Landing Page...');
  await page.goto(`${FRONTEND_URL}/`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '01_landing_page.png') });

  // 2. Login Page
  console.log('📸 2. Capturing Login Page...');
  await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '02_login_page.png') });

  // 3. Customer Session (Arun Kumar)
  console.log('🔑 Authenticating as Customer: Arun Kumar via UI...');
  await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 800));
  await page.type('input[type="text"]', 'arun_kumar');
  await page.type('input[type="password"]', 'Customer123!');
  await page.click('button[type="submit"]');
  await new Promise(r => setTimeout(r, 2000));
  console.log('   Logged in URL:', page.url());

  // 3.1 Customer Dashboard
  console.log('📸 3. Capturing Customer Dashboard...');
  await page.goto(`${FRONTEND_URL}/dashboard`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '03_customer_dashboard.png') });

  // 3.2 My Accounts
  console.log('📸 4. Capturing Customer Accounts...');
  await page.goto(`${FRONTEND_URL}/accounts`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '04_customer_accounts.png') });

  // 3.3 Transfer Money
  console.log('📸 5. Capturing Transfer Money Form...');
  await page.goto(`${FRONTEND_URL}/transfers`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '05_transfer_money.png') });

  // 3.4 Live Excel Sheet (Customer View)
  console.log('📸 6. Capturing Customer Live Excel Sheet...');
  await page.goto(`${FRONTEND_URL}/live-sheet`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '06_customer_live_sheet.png') });

  // 3.5 Loans & Eligibility
  console.log('📸 7. Capturing Loan Application & Eligibility...');
  await page.goto(`${FRONTEND_URL}/loans`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '07_customer_loans.png') });

  // 4. Admin Session
  console.log('🔑 Authenticating as Administrator: admin via UI...');
  await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.evaluate(() => {
    localStorage.clear();
  });
  await page.goto(`${FRONTEND_URL}/login`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 800));
  await page.type('input[type="text"]', 'admin');
  await page.type('input[type="password"]', 'AdminPassword123!');
  await page.click('button[type="submit"]');
  await new Promise(r => setTimeout(r, 2000));
  console.log('   Admin Logged in URL:', page.url());

  // 4.1 Admin KPI Dashboard
  console.log('📸 8. Capturing Admin KPI Dashboard...');
  await page.goto(`${FRONTEND_URL}/admin`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '08_admin_dashboard.png') });

  // 4.2 Admin Fraud & Compliance Queue
  console.log('📸 9. Capturing Fraud & Compliance Review Queue...');
  await page.goto(`${FRONTEND_URL}/admin/fraud`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '09_admin_fraud_review.png') });

  // 4.3 Admin Advanced SQL Reports
  console.log('📸 10. Capturing Advanced DBMS SQL Analytics Reports...');
  await page.goto(`${FRONTEND_URL}/admin/reports`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '10_admin_sql_reports.png') });

  // 4.4 Admin Audit Logs
  console.log('📸 11. Capturing Transactional Outbox & Security Audit Logs...');
  await page.goto(`${FRONTEND_URL}/admin/audit`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1500));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '11_admin_audit_logs.png') });

  // 4.5 Admin Live Excel Sheet
  console.log('📸 12. Capturing Admin Live Excel Spreadsheet (All 8 Tables)...');
  await page.goto(`${FRONTEND_URL}/admin/live-sheet`, { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2000));
  await page.screenshot({ path: path.join(SCREENSHOT_DIR, '12_admin_live_sheet.png') });

  await browser.close();
  console.log('🎉 All 12 high-resolution UI screenshots captured successfully in docs/screenshots/!');
}

capture().catch(err => {
  console.error('❌ Screenshot capture error:', err);
  process.exit(1);
});
