# RangeResumeAudit

RangeResumeAudit is a GenLayer primitive for deciding how to resume a small,
content-addressed HTTP download. A release verifier or mirror monitor can query
an immutable observation for an exact URL and independently known SHA-256.

[StudioNet proof matrix](LIVE_PROOFS.md) · [Submission text](SUBMISSION.md)

Call `audit(run, url, expected_sha256)`. There is no owner or approval stage.
The sender's run ID is write-once. Read the exact report and its digest with
`get_audit(publisher, run)`. Results are public; publishers cannot overwrite
another publisher's run. This is a report about a path observed at execution
time, not a grant, certificate, payment, or long-term guarantee.

The leader and validators each fetch the full representation, then fetch two
overlapping ranges in reverse assembly order. They check identity coding, exact
`Content-Range` coordinates and length, exact bytes, overlap, and the SHA-256
of the reconstructed artifact. They also probe a range past EOF, and, where
there is a strong ETag, test matching and mismatching `If-Range` guards.
Every decision and relevant observation is normalized into the same canonical
JSON report. The validator callback independently runs the HTTP experiment and
compares the entire report. A format-correct but different result cannot pass.

| Decision | Evidence and client action |
| --- | --- |
| `CONDITIONAL_RESUME` | Two valid windows reconstruct the pinned artifact, a matching guard returns the expected partial response, and a stale guard falls back to the pinned full body. Use a guard and verify the final pinned SHA-256. |
| `PINNED_RESUME` | Two valid windows reconstruct the pinned artifact, but a safe guard was not established. Verify the final pinned SHA-256 before use. |
| `FULL_DOWNLOAD` | Full body matched the pin, but reconstruction was not verified. Fetch the full body and check the pin. |
| `ARTIFACT_MISMATCH` | A complete response differed from the expected SHA-256. Reject the bytes; this alone does not establish which party published the wrong pin. |
| `INCONCLUSIVE` | No valid bounded full response. Do not use the observation to authorize a resume. |

The special `416` observation is independent of the recommendation. A server
can legally ignore a Range request; a full-only recommendation is not an
accusation of non-compliance. See [RFC 9110: Range Requests](https://www.rfc-editor.org/rfc/rfc9110.html#name-range-requests)
and [If-Range](https://www.rfc-editor.org/rfc/rfc9110.html#field.if-range).

Study limits: GET only; 16–32,768 identity bytes; numeric RFC text URLs and
commit-pinned raw GitHub paths; a single interval per request. The size checks
bound processing after acquisition; they are not a transport-level download
cap. The explicit scope is the observable HTTP path, including intermediaries.
The pin must come from a trusted channel. CDN variance, transport errors and
ETag churn can prevent agreement. An agreed report can become stale. Response
bodies are compared inside GenVM; only bounded observations and digests persist.

```sh
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
genvm-lint check contracts/RangeResumeAudit.py
```

`REFERENCE.json` contains independently downloaded baseline and window hashes.
The StudioNet proof script requires a dedicated, locally configured test account
and the pinned GenLayer JavaScript SDK (`npm ci`). It checks the chain ID,
journals each broadcast before polling, verifies final execution and consensus
metadata, checks deployed source and state, and validates the report with the
reference vectors. Once `PROOFS.json` exists, use
`node scripts/prove.mjs <source-commit> --verify-only` for read-only replay.
