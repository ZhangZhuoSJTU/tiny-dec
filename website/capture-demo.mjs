import { chromium } from 'playwright';
import { execSync } from 'child_process';

const URL = 'http://165.22.35.184:5173/';
const OUT_DIR = '/home/zhuo/tiny-dec-internal/assets/demo-frames';

execSync(`rm -rf ${OUT_DIR} && mkdir -p ${OUT_DIR}`);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 720 } });
await page.goto(URL, { waitUntil: 'networkidle' });
await page.waitForTimeout(2000);

let frame = 0;
const snap = async () => {
  const path = `${OUT_DIR}/frame_${String(frame).padStart(3, '0')}.png`;
  await page.screenshot({ path });
  console.log(`  [${frame}] captured`);
  frame++;
};

// Steps per stage: [popup(1) + callouts(N)]
// Stage 0 = hero (no popup), Stage 21 = complete (no popup)
// From the walkthrough data:
const stageCallouts = [
  0,  // 0: hero/start - no walkthrough
  2,  // 1: raw bytes
  4,  // 2: loader
  8,  // 3: decode
  5,  // 4: pcode
  6,  // 5: disasm & cfg
  3,  // 6: ir containers
  4,  // 7: simplify
  4,  // 8: dataflow
  4,  // 9: ssa
  4,  // 10: calls
  3,  // 11: stack
  3,  // 12: memory
  3,  // 13: scalar types
  4,  // 14: aggregate types
  3,  // 15: variables
  3,  // 16: range
  3,  // 17: interproc
  4,  // 18: structuring
  3,  // 19: c lowering
  3,  // 20: final c
  0,  // 21: complete - no walkthrough
];

// Frame 0: Hero
await snap();

// For stages 1-20: each has 1 popup + N callouts + free browse
// ArrowRight advances: hero -> popup -> callout1 -> callout2 -> ... -> free browse -> next popup
for (let stage = 1; stage <= 20; stage++) {
  // ArrowRight to enter stage (shows popup)
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(1000);
  await snap(); // popup

  const callouts = stageCallouts[stage];
  for (let c = 0; c < callouts; c++) {
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(800);
    await snap(); // callout
  }

  // ArrowRight to dismiss last callout -> free browse
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(600);
  await snap(); // free browse view
}

// ArrowRight to complete
await page.keyboard.press('ArrowRight');
await page.waitForTimeout(1000);
await snap(); // complete

await browser.close();
console.log(`\nDone! ${frame} frames captured in ${OUT_DIR}`);
