#!/usr/bin/env node
/**
 * Headless Puter.js Text-to-Video Multi-Model Runner v2.0
 * Tests 14 Puter AI Video models in cascade until one produces a video.
 */
const fs = require('fs');
const path = require('path');

let puppeteer;
try {
  puppeteer = require('puppeteer');
} catch (e) {
  try {
    puppeteer = require('puppeteer-core');
  } catch (e2) {
    console.error('Puppeteer not installed. Run: npm install puppeteer');
    process.exit(1);
  }
}

const PUTER_MODELS = [
  'wan2.7-t2v',
  'seedance-2-0-mini',
  'seedance-2-0-fast',
  'minimax/video-01-director',
  'togetherai:google/veo-3.1-lite',
  'vidu/vidu-q1',
  'vidu/vidu-q3-turbo',
  'seedance-2-5',
  'seedance-2-0',
  'pixverse/pixverse-v5',
  'minimax/hailuo-02',
  'pixverse/pixverse-v5.6',
  'togetherai:google/veo-3.1',
  'gemini-omni-1.1-flash'
];

async function run() {
  const prompt = process.argv[2] || 'A cinematic video of a dancing cat on Mars';
  const duration = parseInt(process.argv[3] || '5', 10);
  const size = process.argv[4] || '720p';

  console.log(`[PuterRunner] Starting 14-model cascade for prompt: "${prompt}"`);

  // Detect Chrome binary on linux if using puppeteer-core
  const possiblePaths = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium-browser',
    '/usr/bin/chromium'
  ];
  let execPath = undefined;
  for (const p of possiblePaths) {
    if (fs.existsSync(p)) {
      execPath = p;
      break;
    }
  }

  const launchOpts = {
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-accelerated-2d-canvas',
      '--no-first-run',
      '--no-zygote',
      '--single-process',
      '--disable-gpu'
    ]
  };
  if (execPath) {
    launchOpts.executablePath = execPath;
  }

  let browser;
  try {
    browser = await puppeteer.launch(launchOpts);
    const page = await browser.newPage();
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36');

    await page.setContent(`<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://js.puter.com/v2/"></script>
</head>
<body>
  <div id="status">Ready</div>
</body>
</html>`);

    await page.waitForFunction(() => typeof window.puter !== 'undefined' && typeof window.puter.ai !== 'undefined', { timeout: 40000 });
    console.log('[PuterRunner] Puter.js loaded successfully in headless browser.');

    // Execute the cascade
    const result = await page.evaluate(async (promptText, models, dur, sz) => {
      for (let i = 0; i < models.length; i++) {
        const modelId = models[i];
        console.log(`[PuterRunner] [${i+1}/${models.length}] Attempting model: ${modelId}`);
        try {
          const opts = { model: modelId, seconds: dur };
          if (sz) opts.size = sz;
          const video = await window.puter.ai.txt2vid(promptText, opts);
          const src = video?.src || (typeof video === 'string' ? video : video?.getAttribute?.('src'));
          if (src && typeof src === 'string' && src.startsWith('http')) {
            return { success: true, model: modelId, videoUrl: src };
          }
        } catch (err) {
          console.warn(`[PuterRunner] Model ${modelId} failed: ${err?.message || err}`);
        }
      }
      return { success: false, error: 'All models in Puter.js cascade failed' };
    }, prompt, PUTER_MODELS, duration, size);

    if (result.success) {
      console.log(`[PuterRunner] SUCCESS with model: ${result.model}`);
      console.log(`RESULT_VIDEO_URL=${result.videoUrl}`);
      console.log(`RESULT_MODEL=${result.model}`);
      process.exit(0);
    } else {
      console.error(`[PuterRunner] All models failed: ${result.error}`);
      process.exit(1);
    }
  } catch (err) {
    console.error(`[PuterRunner] Execution error: ${err.message}`);
    process.exit(1);
  } finally {
    if (browser) await browser.close().catch(() => {});
  }
}

run();
