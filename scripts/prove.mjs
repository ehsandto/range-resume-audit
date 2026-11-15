import fs from 'node:fs';
import {spawn} from 'node:child_process';
import assert from 'node:assert/strict';
import {rpc, receipt, source, read, digest, sha} from './check.mjs';

const code = 'contracts/RangeResumeAudit.py';
const publisher = {name: 'studio-proof-deployer', address: '0x7a413BB4AB62E31d62d4cD9efC8C8a8Dae37FB42'};
const journal = 'PROOFS.json';
const commit = process.argv[2];
const verifyOnly = process.argv.includes('--verify-only');
assert(/^[a-f0-9]{40}$/.test(commit ?? ''));
const proof = fs.existsSync(journal)
  ? JSON.parse(fs.readFileSync(journal, 'utf8'))
  : {network: 'StudioNet', source_commit: commit, transactions: []};
assert.equal(proof.source_commit, commit);
const save = () => fs.writeFileSync(journal, JSON.stringify(proof, null, 2) + '\n');

function send(args, signer, entry) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['scripts/run-cli.cjs', ...args], {
      windowsHide: true,
      env: {...process.env, RRA_TEST_ACCOUNT: signer.name},
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let pending = '';
    child.stderr.resume();
    child.stdout.on('data', chunk => {
      const lines = (pending + chunk.toString()).split(/\r?\n/);
      pending = lines.pop();
      for (const line of lines) {
        const matched = /^BROADCAST_HASH (0x[0-9a-f]{64})$/i.exec(line);
        if (matched) {
          entry.hash = matched[1];
          save();
          console.log(entry.step, entry.hash);
        }
      }
    });
    child.on('error', reject);
    child.on('close', resolve);
  });
}

async function transaction(step, args, signer) {
  let entry = proof.transactions.find(item => item.step === step);
  if (!entry) {
    assert(!verifyOnly, 'Verification requires an original broadcast journal');
    const nonce = await rpc('eth_getTransactionCount', [signer.address, 'latest']);
    assert.equal(await rpc('eth_getTransactionCount', [signer.address, 'pending']), nonce);
    entry = {step, args, signer: signer.address, nonce};
    proof.transactions.push(entry);
    save();
    await send(args, signer, entry);
  }
  assert.deepEqual(entry.args, args);
  assert.equal(entry.signer, signer.address);
  assert(entry.hash, 'Broadcast status unknown. Inspect account history before any retry.');
  entry.receipt = await receipt(entry.hash);
  save();
  assert(entry.receipt.committed, 'Transaction did not commit');
  const native = await rpc('eth_getTransactionByHash', [entry.hash]);
  assert.equal(native.from_address.toLowerCase(), signer.address.toLowerCase());
  assert.equal(BigInt(native.nonce), BigInt(entry.nonce));
  assert.equal(BigInt(native.value), 0n);
  console.log(step, entry.receipt.status, entry.receipt.execution);
  return entry.receipt.address;
}

const fixtures = JSON.parse(fs.readFileSync('REFERENCE.json', 'utf8'));
const wrongPin = '0'.repeat(64);
const cases = [...Object.entries(fixtures), ['wrong-commitment', fixtures['github-artifact']]];

function checkReport(record, fixture, expected) {
  const r = record.report;
  assert.equal(record.id, digest(r));
  assert.equal(r.schema, 'range-resume/v1');
  assert.equal(r.url, fixture.url);
  assert.equal(r.expected_sha256, expected);
  const full = r.observations.full;
  assert.equal(full.http, 200);
  assert.equal(full.identity, true);
  assert.deepEqual(full.range, []);
  assert.equal(full.size, fixture.length);
  assert.equal(full.sha256, fixture.sha256);
  if (expected === wrongPin) {
    assert.equal(r.decision, 'ARTIFACT_MISMATCH');
    assert.deepEqual(Object.keys(r.observations), ['full']);
    assert.deepEqual(r.windows, []);
    assert.equal(r.assembled_sha256, null);
    return;
  }

  const n = fixture.length;
  const seam = Math.floor(n / 2);
  const front = [0, seam + 3], tail = [seam - 4, n - 1];
  assert.deepEqual(r.windows, [front, tail]);
  const isPart = (p, [start, end], pin) => p.http === 206 && p.identity
    && JSON.stringify(p.range) === JSON.stringify([start, end, n])
    && p.size === end - start + 1 && p.sha256 === pin;
  const isFull = p => p.http === 200 && p.identity && Array.isArray(p.range)
    && p.range.length === 0 && p.size === n && p.sha256 === expected;
  const fo = isPart(r.observations.front, front, fixture.front);
  const ta = isPart(r.observations.tail, tail, fixture.tail);
  const o = r.observations.outside;
  const out = o.http === 416 && JSON.stringify(o.range) === JSON.stringify([n]);
  let fresh = 'UNTESTED', stale = 'UNTESTED';
  if (full.etag) {
    const f = r.observations.fresh, s = r.observations.stale;
    fresh = isPart(f, tail, fixture.tail) && f.etag === full.etag ? 'PARTIAL_MATCH' : 'NOT_PROVEN';
    stale = s.http === 206 ? 'STALE_PARTIAL' :
      isFull(s) && s.etag === full.etag ? 'SAFE_FALLBACK' : 'NOT_PROVEN';
  }
  assert.deepEqual(r.checks, {front_matches: fo, tail_matches: ta, overlap_matches: fo && ta,
    outside_416: out, fresh_guard: fresh, stale_guard: stale});
  assert.equal(r.assembled_sha256, fo && ta ? expected : null);
  assert.equal(r.decision, fo && ta ? fresh === 'PARTIAL_MATCH' && stale === 'SAFE_FALLBACK'
    ? 'CONDITIONAL_RESUME' : 'PINNED_RESUME' : 'FULL_DOWNLOAD');
}

assert.equal(await rpc('eth_chainId', []), '0xf22f');
proof.address = await transaction('deploy', ['deploy', '--contract', code], publisher);
proof.source = await source(proof.address);
proof.records ??= {};
save();

for (const [name, fixture] of cases) {
  const pin = name === 'wrong-commitment' ? wrongPin : fixture.sha256;
  const to = await transaction(name, ['write', proof.address, 'audit', '--args', name, fixture.url, pin], publisher);
  assert.equal(to.toLowerCase(), proof.address.toLowerCase());
  const record = await read(proof.address, 'get_audit', [publisher.address, name]);
  proof.records[name] = record;
  save();
  checkReport(record, fixture, pin);
  console.log(name, record.report.decision, JSON.stringify(record.report.checks));
}
assert(await import('./check.mjs').then(({denied}) => denied(proof.address, 'get_audit',
  ['0x' + 'fe'.repeat(20), 'github-artifact'])));
proof.cross_publisher_lookup = 'Unknown run';
const history = await rpc('sim_getTransactionsForAddress', [proof.address]);
assert.deepEqual(history.map(t => t.hash).sort(), proof.transactions.map(t => t.hash).sort());
proof.verified = true;
save();
