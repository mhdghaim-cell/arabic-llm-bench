#!/usr/bin/env node
// Validates the data spine. Run: node scripts/validate.mjs
import { readFileSync, existsSync } from 'fs';

let errors = 0, warnings = 0;
const fail = m => { console.error('  ERROR  ' + m); errors++; };
const warn = m => { console.warn('  WARN   ' + m); warnings++; };
const load = f => {
  if (!existsSync(f)) { fail(`missing file: ${f}`); return null; }
  try { return JSON.parse(readFileSync(f, 'utf8')); }
  catch (e) { fail(`invalid JSON in ${f}: ${e.message}`); return null; }
};

console.log('\nValidating data spine...\n');

const rubric   = load('data/rubric.json');
const prompts  = load('data/prompts.json');
const machines = load('data/machines.json');
const models   = load('data/models.json');
const runs     = load('data/runs.json');
const scores   = load('data/scores.json');
const findings = load('data/findings.json');
const tokenizers = load('data/tokenizers.json');

// referential integrity
const promptIds  = new Set((prompts?.prompts  ?? []).map(p => p.id));
const machineIds = new Set((machines?.machines ?? []).map(m => m.id));
const modelIds   = new Set((models?.models    ?? []).map(m => m.id));

for (const r of runs?.runs ?? []) {
  if (!machineIds.has(r.machine)) fail(`run ${r.id}: unknown machine "${r.machine}"`);
  if (!promptIds.has(r.prompt?.id)) fail(`run ${r.id}: unknown prompt "${r.prompt?.id}"`);
  if (!modelIds.has(r.model?.id)) warn(`run ${r.id}: model "${r.model?.id}" not in registry`);
  if (r.metrics?.eval_rate == null) fail(`run ${r.id}: missing eval_rate`);
}

for (const s of scores?.scores ?? []) {
  if (!promptIds.has(s.prompt)) fail(`score for ${s.model}/${s.prompt}: unknown prompt`);
  if (!machineIds.has(s.machine)) fail(`score for ${s.model}/${s.prompt}: unknown machine`);
  const max = s.max ?? rubric?.scale?.max;
  if (s.value > max) fail(`score for ${s.model}/${s.prompt}: ${s.value} exceeds max ${max}`);
}

// rule 5: never invent a number
const nulls = (tokenizers?.tokenizers ?? []).filter(t => t.ratio == null).length;
if (nulls) console.log(`  note   ${nulls} tokenizer ratios are null (unmeasured) — correct per Rule 5`);

// timing prompt discipline
const timing = (runs?.runs ?? []).filter(r => r.run_type === 'timing');
const badTiming = timing.filter(r => r.prompt?.id !== 'P5');
if (badTiming.length) fail(`${badTiming.length} timing runs do not use P5`);

console.log(`\n${errors} errors, ${warnings} warnings\n`);
process.exit(errors ? 1 : 0);
