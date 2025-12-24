#!/usr/bin/env node
import fs from 'fs/promises';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const IN_PATH = path.resolve(__dirname, '..', 'src', 'data', 'awsIconIndex.json');

async function main() {
  const raw = await fs.readFile(IN_PATH, 'utf8');
  const obj = JSON.parse(raw);
  const filtered = Object.fromEntries(
    Object.entries(obj).filter(([k]) => !k.endsWith('_64@5x.png'))
  );
  await fs.writeFile(IN_PATH, JSON.stringify(filtered, null, 2), 'utf8');
  console.log('Filtered awsIconIndex.json entries:', Object.keys(filtered).length);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
