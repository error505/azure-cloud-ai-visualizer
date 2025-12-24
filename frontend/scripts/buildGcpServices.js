#!/usr/bin/env node
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PUBLIC_DIR = path.resolve(__dirname, '..', 'public', 'gcp_icons');
const OUT_PATH = path.resolve(__dirname, '..', 'src', 'data', 'gcpServices.json');

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
  return name.replace(/\.[^.]+$/, '').replace(/\s+/g, ' ').trim();
}

async function build() {
  try {
    const exists = await fs.stat(PUBLIC_DIR).catch(()=>null);
    if (!exists) {
      console.error('GCP icons directory not found at', PUBLIC_DIR);
      process.exit(1);
    }
    const files = await walk(PUBLIC_DIR);
    const services = [];
    for (const f of files) {
      const rel = path.relative(PUBLIC_DIR, f).replace(/\\/g, '/');
      // rel might be like "Category/Icon.svg" or "Category/Sub/Icon.svg"
      const parts = rel.split('/');
      const fileName = parts[parts.length - 1];
      const title = normalizeTitle(fileName);
      const category = parts.length > 1 ? parts[0] : 'Other';
      const iconPath = `/gcp_icons/${rel}`;
      const id = `gcp:${title.replace(/[^a-z0-9]+/gi, '-')}`;
      services.push({ id, title, description: `${title} service`, iconPath, category });
    }

    // Deduplicate by title, prefer svg 32 if multiple; keep first occurrence for now
    const map = new Map();
    for (const svc of services) {
      const key = svc.title;
      if (!map.has(key)) map.set(key, svc);
    }
    const out = Array.from(map.values());
    await fs.mkdir(path.dirname(OUT_PATH), { recursive: true });
    await fs.writeFile(OUT_PATH, JSON.stringify(out, null, 2), 'utf8');
    console.log('Wrote GCP services to', OUT_PATH, 'entries:', out.length);
  } catch (err) {
    console.error(err);
    process.exit(1);
  }
}

build();
