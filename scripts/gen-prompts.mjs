#!/usr/bin/env node
// Regenerates prompts/*.txt from data/prompts.json. Run: node scripts/gen-prompts.mjs
import { readFileSync, writeFileSync } from 'fs';
const d = JSON.parse(readFileSync('data/prompts.json', 'utf8'));
for (const p of d.prompts) {
  const f = `prompts/${p.id.toLowerCase()}.txt`;
  writeFileSync(f, p.prompt.trim() + '\n', 'utf8');
  console.log('wrote', f);
}
