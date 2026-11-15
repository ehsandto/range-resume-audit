# StudioNet proof matrix

[StudioNet deployment](https://explorer-studio.genlayer.com/address/0x06fced7250854B788025545C848f75a0705D89C2) · [Deployed source](https://github.com/ehsandto/range-resume-audit/blob/2ed1c791ebdcf7f66298531c851dd825661b52e2/contracts/RangeResumeAudit.py) · [Machine-readable receipts and state](PROOFS.json)

Normalized deployed source SHA-256: `82dda792b3923511145236a0206a97c4424366048c3645214cd4ddc87b4878a5`.
Each transaction below finalized with successful leader execution and majority
agreement. The receipt checks reject leader-only runs and require at least two
recorded agree votes. The three audit states were independently recomputed from
[full and slice hashes](REFERENCE.json), and the contract source was fetched
back from StudioNet and matched against the pinned source.

| Transaction | Status | Agree votes / initial validators |
| --- | --- | --- |
| [deploy](https://explorer-studio.genlayer.com/tx/0x5844612407da3e9289f7341c42d2ac7167536f3610c4405f844a007d357743d0) | FINALIZED / SUCCESS | 3 / 5 |
| [github-artifact](https://explorer-studio.genlayer.com/tx/0x27733903cb35efac71ca2d5ab8ef62e42172e66c34b620f956d41e70aa274696) | FINALIZED / SUCCESS | 3 / 5 |
| [rfc-artifact](https://explorer-studio.genlayer.com/tx/0x66887e7d3a997fa77902a3ebf2e8ad827015863a57588b95e7dc305a44a93527) | FINALIZED / SUCCESS | 3 / 5 |
| [wrong-sha256](https://explorer-studio.genlayer.com/tx/0x07de641ddd2ee7daddc5057f6cc62cdfda743e28c067fcaec82c9196453dd34c) | FINALIZED / SUCCESS | 3 / 5 |

| Run | Decision | HTTP responses | Assembly SHA-256 | Stale guard | Report digest |
| --- | --- | --- | --- | --- | --- |
| github-artifact | `PINNED_RESUME` | fresh=206, front=206, full=200, outside=416, stale=206, tail=206 | Matched | STALE_PARTIAL | `93c941255d75c70a37c6e8c9600c2aefbefc91423ef18370fdc946ed7de3800b` |
| rfc-artifact | `FULL_DOWNLOAD` | front=200, full=200, outside=200, tail=200 | — | UNTESTED | `edf90c295d153bc4db6b0c19350e899e5577db9257009f71aaf7270a7c84e25c` |
| wrong-sha256 | `ARTIFACT_MISMATCH` | full=200 | — | — | `9ea5c11b0565a95927a70344a75d7d526d0aabcbe50bec2487cbca41dd55d7c1` |

An independent read with another publisher and the same run ID reverted with
Unknown run. Conditional resume, corrupt partial bodies, malformed or duplicate
range metadata, non-identity encoding, and transport failure are covered by
local tests. Only the observed live outcomes above are claimed onchain.

[wrong-commitment](https://explorer-studio.genlayer.com/tx/0xb9996ea61f665e4dd62598a1b4771275a5524641f37183a90771365100e6edc8) finalized with an execution error because the CLI
encoded the all-numeric pin as an integer. The run was absent on readback;
that transaction is excluded from the proof matrix. The wrong SHA-256 check
used a different run ID and a literal hexadecimal string.
