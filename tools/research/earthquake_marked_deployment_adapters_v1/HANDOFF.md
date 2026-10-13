# Immutable deployment adapter handoff

Source-only first-clean v3,13 October2026. Public package is this directory only. Source hashes exactly match REVIEWED_SOURCE_SNAPSHOT.json; no source edits after default autoreview first clean. FIRST_CLEAN_MANIFEST.json covers all files except itself and ALLOWED_PUBLIC_FILES.txt; the latter enumerates the complete deployment inventory. Every file is0400. Nested reference files are frozen dependency contracts, not alternative implementations.

Target focused command from this directory:

```
PYTHONDONTWRITEBYTECODE=1 <ROOT-positively-bound-target-python> -m unittest -v test_adapters
```

All39 tests are invented fixtures, temporary local files and bounded local subprocesses. The runtime-inventory test creates10112 one-byte invented files plus10 critical fixtures and4 symlinks; it never reads an actual runtime or dataset. A separate ROOT-owned source-only import smoke must confirm compatibility of the actual positively verified NumPy/SciPy/Torch/runtime with the persistent import guard before any real fit. This agent neither ran nor claims that smoke.

ROOT constructs exact API.md deployment config, the independent reviewed authority_source and authority_config file specs, then uses the same make_validator(full_config, io=bound_io, source_binding=bound_source_binding, clock=monotonic, expected_deployment_config_pin=independently_verified_pin) for parent and child. Parent config is separately pinned by ROOT CLI; child receives expected config pin in its immutable pinned launch frame. No self-referential config hash. ROOT must verify current funding/publication/target tests, actual source inventories and original runtime modes, all115/345 native semantics/all87×3 positive support, and old8 independently closed528 forecasts plus join provenance. The reported actual prerequisites were not read by this source-only agent.

No retry, resume or stage skip; fixed14-stage order and all source/manager/whole caps unchanged. Same fresh store/gate/boot monotonic clock throughout. Original strong packet identity may explicitly be canonical original archive+manifest pins, not a fabricated historical logical packet hash; ROOT preserves that semantic tag. Projection preserves numerical values and prior origin; new packet SHA is comparison-population authority only. New S/P/D results need independent audit before scientific claims.

Root next steps: verify this complete manifest/inventory, target39 tests and bounded vendor-import smoke, positively bind separately reviewed ROOT authority source, publish the frozen packet, then execute using the unchanged parent controller. Any target blocker requires reporting and a separately reviewed fix; source first-clean is never silently patched.
