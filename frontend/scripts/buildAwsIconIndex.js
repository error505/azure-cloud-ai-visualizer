#!/usr/bin/env node
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Scans public/aws_icons and builds a JSON index mapping icon title -> preferred file path
// Preference order: 32/svg, 48/svg, 64/svg, 16/svg, then png equivalents

const ROOT = path.resolve(__dirname, '..', 'public', 'aws_icons', 'Architecture-Service-Icons_07312025');
const OUT = path.resolve(__dirname, '..', 'src', 'data', 'awsIconIndex.json');

function walkCategories(root) {
  const categories = fs.readdirSync(root, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name);
  const index = {};
  categories.forEach(cat => {
    const catPath = path.join(root, cat);
    // sizes like 16,32,48,64
    const sizes = fs.readdirSync(catPath, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name);
    sizes.forEach(size => {
      const sizePath = path.join(catPath, size);
      const files = fs.readdirSync(sizePath).filter(f => !f.startsWith('.'));
      files.forEach(file => {
        const ext = path.extname(file).toLowerCase();
        const base = file.replace(/_[0-9]+\.(svg|png)$/i, '');
        const title = base; // keep base as title key
        const rel = path.join('/aws_icons/Architecture-Service-Icons_07312025', cat, size, file).replace(/\\/g, '/');
        if (!index[title]) index[title] = [];
        index[title].push({ path: rel, size: Number(size), ext });
      });
    });
  });
  // pick preferred file for each title
  const preferred = {};
  Object.entries(index).forEach(([title, files]) => {
    // prefer svg and size order
    const orderSizes = [32, 48, 64, 16];
    let chosen = null;
    for (const s of orderSizes) {
      const svg = files.find(f => f.size === s && f.ext === '.svg');
      if (svg) { chosen = svg; break; }
    }
    if (!chosen) {
      // try any svg
      chosen = files.find(f => f.ext === '.svg');
    }
    if (!chosen) {
      // try png preferred sizes
      for (const s of orderSizes) {
        const png = files.find(f => f.size === s && f.ext === '.png');
        if (png) { chosen = png; break; }
      }
    }
    if (!chosen && files.length) chosen = files[0];
    if (chosen) preferred[title] = chosen.path;
  });
  return preferred;
}

function main() {
  if (!fs.existsSync(ROOT)) {
    console.error('AWS icons root not found:', ROOT);
    process.exit(1);
  }
  const idx = walkCategories(ROOT);
  fs.writeFileSync(OUT, JSON.stringify(idx, null, 2), 'utf8');
  console.log('Wrote AWS icon index to', OUT, 'entries:', Object.keys(idx).length);
}

main();
