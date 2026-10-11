# Request and scope ledger

Task date: 11 October 2026. This audit used public primary article/source documents only. No earthquake catalog/waveform, TSMIP/GDMS request, dataset archive, weight, actual input, account endpoint, author contact, fit, install, source execution or Git mutation occurred. Prior collector freezes and the shared mirror were untouched.

Five web-tool calls were used for discovery and cached document inspection. The tool does not expose underlying network-attempt counts, response byte hashes, redirects or exact retrieval times; none is invented here. Seventeen command items comprise two focused search queries, six open operations, eight find operations and one click. Repeated article line/find operations reused the same returned document; they are not counted as independently delivered HTTP GETs.

| Call | Requested operations | Outcome / use |
|---|---|---|
| 1 | Search exact article DOI; search TT-SAM author code | Located official publisher page and author repository. Search-returned third-party pages and the older different repository were not opened or relied on. |
| 2 | Open official [article](https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2025JH001005) and [author repository](https://github.com/YuHengChen54/TT-SAM) | Article HTML text and repository README/tree view accessible. Exact wire bytes unavailable. |
| 3 | Five article/repository find operations; two cached line opens | Located relevant clock/availability sections and the source-folder link. |
| 4 | Three article find operations; click author repository `src` | Article reference identifies the software DOI. `src` click returned an internal error. Supplement search had no matches in this accessible HTML; absence elsewhere is not established. |
| 5 | Open [software record](https://zenodo.org/records/18923222) and GitHub `contents/src` endpoint | Both unavailable through the web tool. Preserved as access limitations; no data record opened. |

Six separate bounded native HTTPS GETs then retrieved one source-tree metadata response, one software-record metadata response and four exact immutable code blobs. `/usr/bin/curl -q` disabled user curl configuration; calls used a 20 s transfer deadline, 10 s connection limit, no retry, no redirect following and response byte caps. No credential/auth header was supplied. The two metadata caps were 262,144 bytes each; code-blob caps were 65,536 bytes each. Delivered HTTP bodies total **84,674 bytes**, including the 229-byte HTTP 302 response. Exact per-response status/bytes/SHA-256/time and decoded-source SHA-256/Git blob SHA-1 are in `native_request_ledger.json`.

Native sequence: source tree 200; Zenodo software-record API metadata 302; preprocessor blob 200; dataset blob 200; training blob 200; directly called integration-helper blob 200. The 302 was not followed. The source-tree metadata provides membership pins only; no payload under `data`, `result` or `saved_models` was requested. Source blob decoding and Git-object hashing inspect text bytes; they do not execute the downloaded source.

The exact record cited by the paper is [Zenodo software DOI 10.5281/zenodo.18923222](https://doi.org/10.5281/zenodo.18923222). Its downloaded matching source/configuration and any standalone supplement remain unverified. The separate dataset DOI was intentionally not opened. No automated retry, broader repository clone, archive download or account/API fallback followed these probes.

Raw public responses, decoded source and response headers are retained locally in `inert_public_sources/` solely for provenance and are excluded from the curated review/public packet. Only the six authored/receipt members listed in `CURATED_ALLOWLIST.md` may be published. Article-derived prose in the report is deliberately below 150 words; no article body or source excerpt is redistributed. Source-only report validation consists of byte/object-pin checks and authored packet hashes; this documentation task does not require a producer or code review.
