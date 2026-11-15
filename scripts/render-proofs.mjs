import fs from 'node:fs';
import assert from 'node:assert/strict';

const p = JSON.parse(fs.readFileSync('PROOFS.json', 'utf8'));
const github = 'https://github.com/ehsandto/range-resume-audit';
const explorer = 'https://explorer-studio.genlayer.com';
const included = p.transactions.filter(t => t.receipt.committed);
const excluded = p.transactions.filter(t => !t.receipt.committed);
assert(p.verified && p.source.source_match && included.length === 4 && excluded.length <= 1);
assert(included.every(t => t.receipt.status === 'FINALIZED'
  && t.receipt.committed && t.receipt.execution === 'SUCCESS'
  && t.receipt.consensus === 'MAJORITY_AGREE' && t.receipt.agree_votes >= 2));
assert.equal(p.cross_publisher_lookup, 'Unknown run');

const address = `[StudioNet deployment](${explorer}/address/${p.address})`;
const source = `[Deployed source](${github}/blob/${p.source_commit}/contracts/RangeResumeAudit.py)`;
const link = t => `[${t.step}](${explorer}/tx/${t.hash})`;
const exclusion = excluded.length
  ? `${link(excluded[0])} finalized with an execution error because the CLI
encoded the all-numeric pin as an integer. The run was absent on readback;
that transaction is excluded from the proof matrix. The wrong SHA-256 check
used a different run ID and a literal hexadecimal string.\n` : '';
const observations = Object.entries(p.records).map(([name, {report: r, id}]) => {
  const c = r.checks;
  const ranges = Object.entries(r.observations)
    .map(([request, item]) => `${request}=${item.http || 'transport error'}`).join(', ');
  return `| ${name} | \`${r.decision}\` | ${ranges} | ${r.assembled_sha256 ? 'Matched' : '—'} | ${c.stale_guard ?? '—'} | \`${id}\` |`;
}).join('\n');

fs.writeFileSync('LIVE_PROOFS.md', `# StudioNet proof matrix

${address} · ${source} · [Machine-readable receipts and state](PROOFS.json)

Normalized deployed source SHA-256: \`${p.source.sha256}\`.
Each transaction below finalized with successful leader execution and majority
agreement. The receipt checks reject leader-only runs and require at least two
recorded agree votes. The three audit states were independently recomputed from
[full and slice hashes](REFERENCE.json), and the contract source was fetched
back from StudioNet and matched against the pinned source.

| Transaction | Status | Agree votes / initial validators |
| --- | --- | --- |
${included.map(t => `| ${link(t)} | ${t.receipt.status} / ${t.receipt.execution} | ${t.receipt.agree_votes} / ${t.receipt.initial_validators} |`).join('\n')}

| Run | Decision | HTTP responses | Assembly SHA-256 | Stale guard | Report digest |
| --- | --- | --- | --- | --- | --- |
${observations}

An independent read with another publisher and the same run ID reverted with
Unknown run. Conditional resume, corrupt partial bodies, malformed or duplicate
range metadata, non-identity encoding, and transport failure are covered by
local tests. Only the observed live outcomes above are claimed onchain.

${exclusion}
`.trimEnd() + '\n');

const reports = Object.values(p.records).map(x => x.report);
assert(reports.length === 3);
const counts = reports.map(x => x.decision).join(', ');
const notes = `RangeResumeAudit decides whether a small HTTP artifact can be resumed. The leader and validators independently fetch the full body and two overlapping ranges, check status, coordinates and exact bytes, and hash the reconstruction against a known SHA-256. They also probe past EOF and test matching and stale If-Range when a strong ETag exists. Exact agreement on the normalized report is required.

The contract recommends conditional resume, hash-checked resume, or a full download. Wrong commitments and unusable baselines cannot authorize resume. Each report is immutable under the caller's run ID. It describes one observed HTTP path and does not promise future delivery.

StudioNet outcomes (GitHub, RFC, wrong hash): ${counts}.`;
assert(notes.length <= 1000);
fs.writeFileSync('SUBMISSION.md', `**Contribution type:** Builder → Intelligent Contracts

**Title:** RangeResumeAudit — Consensus-Checked HTTP Resume

**Notes / Description**

${notes}

**Evidence**

- [Repository](${github})
- ${source}
- ${address}
- [Live proof matrix](${github}/blob/main/LIVE_PROOFS.md)
${included.map(t => '- ' + link(t)).join('\n')}
`);
