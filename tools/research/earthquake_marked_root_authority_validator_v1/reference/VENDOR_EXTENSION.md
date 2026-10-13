# Prospective supplemental vendor binding

13 October2026. This NEW adapter source packet preserves the frozen v1/first_clean31 unchanged. ROOT reported its39 target fixture tests passed, but its source-only import smoke stopped at an out-of-inventory runtime dependency before any fit. The prior prefix10112 regular files and10 critical files were not a complete installed Torch dependency inventory. This extension adds explicit metadata authority for that external installed tree; no installation, permission normalization, data/weight read or scientific-method change.

## Exact runtime ABI

The prior runtime object gains one mandatory `vendor_inventory` readonly file spec `{path,pin:{bytes,sha256},mode}`. Inventory bytes are capped at16MiB. Exact parsed keys:

```
{
  "schema": "marked-supplemental-vendor-inventory-v1",
  "roots": ["<ROOT canonical absolute site-packages>"],
  "records": {"<distribution-version.dist-info>": {"path":"<root>/<id>/RECORD", "pin":{"bytes":0,"sha256":"..."}, "mode":436}},
  "files": {"<canonical absolute admitted file>": {"bytes":0,"sha256":"...","mode":436,"record_id":"<id>","record_path":"<exact original CSV literal>"}}
}
```

The zeros/ellipsis above are syntax placeholders, not valid deployment evidence. Mode436 denotes0664; actual original integer modes are authoritative and never normalized. Records must lie directly under one of the declared roots as `<id>/RECORD`; IDs are exact *.dist-info directory basenames. Records are individually positively pinned, read without symlink components and verified for exact mode/size/hash. CSV literal paths are normalized only for matching: `normpath(record_root/record_path)` must equal the admitted canonical key and stay under a bound root. An admitted file must match an explicit canonical URL-safe SHA256 and decimal byte-size row. Blank/unhashed/non-SHA256/outside-root rows provide no permission. Missing or ambiguous admitted proof fails closed. Repeated rows with the exact same parsed literal/hash/size tuple are idempotent metadata and are folded once. Any conflicting duplicate **admitted** literal fails closed; no hash/size choice is made. Unadmitted rows, including conflicting cache rows, confer no execution permission and do not invalidate unrelated explicitly admitted entries; their full original RECORD bytes remain pinned and unchanged. Supplemental files that overlap original runtime members must have identical pins/modes.

ROOT derives these prospective facts from installed RECORD documents and actual stat size/mode, pins the inventory and documents, and preserves all exclusions as unadmitted. RECORD hashes are integrity metadata, **not cryptographic publisher signatures**. This source does not certify installation provenance; ROOT's independent authority binds those metadata facts. Resource proof must bind `runtime_subject_pin = pin(canonical(config.runtime))`, so approval covers this supplemental inventory in addition to the gate's unchanged original prefix-manifest pin. Full deployment config also remains independently pinned by ROOT and the immutable stage frame. No cyclic self-hash is introduced.

Caps:1–8 canonical roots,1–4096 RECORD documents, <=200000 admitted file entries, <=400000 total CSV rows, each document<=16MiB and aggregate RECORD bytes<=64MiB. Inventory JSON's existing structural cap still applies. No broad directory whitelist authorizes executable code; roots only constrain explicit admitted paths.

## Execution-byte binding

`source_binding.runtime` validates original prefix10112/critical10/four links unchanged, then validates all supplemental metadata documents and admitted-row correspondences. It deliberately does not eagerly hash every multi-gigabyte installed vendor file on every stage. The import guard maps only explicit positive entries. At import, Python source/extension origins are independently checked against those entries using actual regular-file mode, size and SHA256, with deadline checks during streaming. External origins and preloaded non-stdlib dependencies remain forbidden, even when their current source path is admitted: the current path/hash cannot prove which cached bytes already executed. Positively loaded bootstrap/authority source modules are a separate source role, and Python stdlib remains interpreter authority. A site-startup dependency can therefore block a target import smoke; that must be reported, not whitelisted by filename. Actual target-package compatibility and timing require ROOT's separately bounded source-only smoke before any data/fit.

`-B` prevents bytecode writes but does not prevent existing cached bytecode reads. Therefore admitted Python source modules use `VerifiedSourceLoader`, whose `get_code` positively reads and compiles the exact pinned source bytes. It never executes an adjacent cached .pyc, even one with a matching timestamp/size header. A sourceless .pyc is allowed only when independently admitted/pinned; its loader verifies the actual bytes before interpreting them. An invented malicious-cache test first demonstrates the ordinary loader consuming a same-timestamp/same-size malicious cache, then verifies this loader executes the safe pinned source instead. Package metadata, filenames and relative-import semantics are retained.

## Limits of the claim

This establishes Python import-origin/source-byte and directly imported extension-file integrity, plus metadata custody. It does not prove a complete dynamic-linker dependency closure, audit arbitrary dynamically generated code, or rehash every library already mapped into process memory. Libraries opened internally through CDLL/dlopen and extension DT_NEEDED chains are not fully observed by Python's import machinery. Their operating-system/provider/runtime provenance remains separate ROOT authority; no claim of complete native-binary execution closure is made. Source-only imported-module smoke and actual frozen numerical target tests are necessary practical checks, but are not a cryptographic proof of every mapped library.

The frozen parent/trainer/Gaussian/native mathematical sources,115/345 roster,65/22 common cohort, seeds, optimizer, source300/900 caps, manager360/960 and whole7200+200 remain unchanged. No actual values or fit results informed this source extension. Independent old-comparator origins and new-output audits remain mandatory.
