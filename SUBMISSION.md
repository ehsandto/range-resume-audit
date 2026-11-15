**Contribution type:** Builder → Intelligent Contracts

**Title:** RangeResumeAudit — Consensus-Checked HTTP Resume

**Notes / Description**

RangeResumeAudit decides whether a small HTTP artifact can be resumed. The leader and validators independently fetch the full body and two overlapping ranges, check status, coordinates and exact bytes, and hash the reconstruction against a known SHA-256. They also probe past EOF and test matching and stale If-Range when a strong ETag exists. Exact agreement on the normalized report is required.

The contract recommends conditional resume, hash-checked resume, or a full download. Wrong commitments and unusable baselines cannot authorize resume. Each report is immutable under the caller's run ID. It describes one observed HTTP path and does not promise future delivery.

StudioNet outcomes (GitHub, RFC, wrong hash): PINNED_RESUME, FULL_DOWNLOAD, ARTIFACT_MISMATCH.

**Evidence**

- [Repository](https://github.com/ehsandto/range-resume-audit)
- [Deployed source](https://github.com/ehsandto/range-resume-audit/blob/2ed1c791ebdcf7f66298531c851dd825661b52e2/contracts/RangeResumeAudit.py)
- [StudioNet deployment](https://explorer-studio.genlayer.com/address/0x06fced7250854B788025545C848f75a0705D89C2)
- [Live proof matrix](https://github.com/ehsandto/range-resume-audit/blob/main/LIVE_PROOFS.md)
- [deploy](https://explorer-studio.genlayer.com/tx/0x5844612407da3e9289f7341c42d2ac7167536f3610c4405f844a007d357743d0)
- [github-artifact](https://explorer-studio.genlayer.com/tx/0x27733903cb35efac71ca2d5ab8ef62e42172e66c34b620f956d41e70aa274696)
- [rfc-artifact](https://explorer-studio.genlayer.com/tx/0x66887e7d3a997fa77902a3ebf2e8ad827015863a57588b95e7dc305a44a93527)
- [wrong-sha256](https://explorer-studio.genlayer.com/tx/0x07de641ddd2ee7daddc5057f6cc62cdfda743e28c067fcaec82c9196453dd34c)
