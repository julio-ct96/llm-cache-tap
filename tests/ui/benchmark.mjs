import { filterRecords, summarizeRecords } from '../../ui/list.js';

const sizes = [30, 300, 3000];
const samples = 7;
const warmups = 10;

function syntheticRecords(count) {
  return Array.from({ length: count }, (_, index) => ({
    id: index + 1,
    model: index % 2 ? 'claude-sonnet' : 'gpt-fast',
    conv: `conversation-${index % 25}`,
    verdict: ['HIT', 'PARTIAL', 'MISS', 'N/A'][index % 4],
    state: index % 5 ? 'done' : 'pending',
    effort: index % 3 ? 'medium' : 'high',
    effort_changed: index % 7 === 0,
    prev_id: index ? index : null,
    server_side: index % 11 === 0,
    notes: [`synthetic request ${index}`, index % 2 ? 'cache stable' : 'prefix changed'],
    usage: { read: index % 100, input_total: 100 + (index % 100) },
  }));
}

function run(records) {
  const visible = filterRecords(records, { model: '', conv: '', bad: false, effort: false, text: 'cache' });
  return summarizeRecords(visible);
}

function median(values) {
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.floor(sorted.length / 2)];
}

for (const size of sizes) {
  const records = syntheticRecords(size);
  for (let index = 0; index < warmups; index++) run(records);
  const durations = [];
  let quantity = 0;
  for (let index = 0; index < samples; index++) {
    const start = performance.now();
    quantity = run(records).count;
    durations.push(performance.now() - start);
  }
  console.log(`${size} records: median ${median(durations).toFixed(3)} ms, quantity ${quantity}`);
}
