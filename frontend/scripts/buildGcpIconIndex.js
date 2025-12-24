#!/usr/bin/env node
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PUBLIC_DIR = path.resolve(__dirname, '..', 'public', 'gcp_icons');
const OUT_PATH = path.resolve(__dirname, '..', 'src', 'data', 'gcpIconIndex.json');

// Preference order for sizes / types
const PREFERRED_ORDER = [
  {size: '32', ext: '.svg'},
  {size: '48', ext: '.svg'},
  {size: '64', ext: '.svg'},
  {size: '16', ext: '.svg'},
  {size: '32', ext: '.png'},
  {size: '48', ext: '.png'},
  {size: '64', ext: '.png'},
];

async function walk(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true });
  const files = [];
  for (const ent of entries) {
    const res = path.join(dir, ent.name);
    if (ent.isDirectory()) files.push(...await walk(res));
    else files.push(res);
  }
  return files;
}

function normalizeTitle(name) {
  // strip extension and common prefixes/suffixes
  return name.replace(/\.[^.]+$/, '').replace(/\s+/g, ' ').trim();
}

async function buildIndex() {
  try {
    const exists = await fs.stat(PUBLIC_DIR).catch(()=>null);
    if (!exists) {
      console.error('GCP icons directory not found at', PUBLIC_DIR);
      process.exit(1);
    }
    const files = await walk(PUBLIC_DIR);
    // Map from title -> available files
    const map = new Map();
    for (const f of files) {
      const rel = path.relative(PUBLIC_DIR, f).replace(/\\/g, '/');
      const base = path.basename(f);
      const title = normalizeTitle(base);
      const entry = map.get(title) || [];
      entry.push({ path: rel, full: f });
      map.set(title, entry);
    }

    const out = {};
    for (const [title, variants] of map.entries()) {
      // sort by preference
      let chosen = null;
      for (const pref of PREFERRED_ORDER) {
        const match = variants.find(v => v.path.includes(`_${pref.size}`) && v.path.endsWith(pref.ext));
        if (match) {
          chosen = match;
          break;
        }
      }
      // fallback: any svg -> any png -> first
      if (!chosen) {
        chosen = variants.find(v => v.path.endsWith('.svg')) || variants.find(v => v.path.endsWith('.png')) || variants[0];
      }
      if (chosen) out[title] = `/gcp_icons/${chosen.path}`;
    }

    await fs.mkdir(path.dirname(OUT_PATH), { recursive: true });
    await fs.writeFile(OUT_PATH, JSON.stringify(out, null, 2), 'utf8');
    console.log('Wrote GCP icon index to', OUT_PATH, 'entries:', Object.keys(out).length);
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
}

buildIndex();
