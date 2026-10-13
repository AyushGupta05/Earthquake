# Prospective V5: exact metadata-only finder

ROOT's isolated invented-parameter lazy-Adam smoke reached Triton entry-point discovery and imported the positively admitted importlib_metadata backport. Its decorator appends a MetadataPathFinder instance to sys.meta_path. V4 correctly rejected an unexpected changed chain, after its helper and optional-module fixes passed. No actual scientific input or optimizer step occurred in that smoke, according to ROOT; this source agent has not opened the private output.

V5 adds one mandatory runtime field, prospectively approved before real fits:

    metadata_finder = {
      "schema": "importlib-metadata-inert-finder-v1",
      "sources": {"package": <__init__.py file spec>, "compat": <_compat.py file spec>}
    }

Each file spec is exactly {path,pin:{bytes,sha256},mode}; canonical same-package paths end __init__.py and _compat.py. Both must exactly match existing admitted vendor-inventory bindings. Only these two bounded source files are read, with clocks. Unrelated vendor binary payloads are not eagerly hashed; normal per-import verification is unchanged. ROOT's full runtime_subject_pin and independently pinned deployment config cover the new object; no authority-factory or scientific API change.

The owned chain permits [Guard] before registration and [Guard, exact MetadataPathFinder instance] after registration. Once observed, removal or replacement is rejected. The guard must remain first and the same list must remain owned; all other entries, displacement, prepending and extra finders fail. Loaded package and compat module identities, file paths, exact VerifiedSourceLoader objects/bindings are required. The instance must have the exact positively loaded class and no instance attributes. find_spec cannot be overridden in that class: it must be the verified compat.NullFinder static method, with exact function/globals/filename identity. A same-interpreter compiled static-method contract compares bytecode, constants, names, argument layout, flags, free/cell variables and stack size to prove unconditional None without invoking the candidate. Using the static-method class context also preserves Python3.14 method code flags; the target3.9 uses its own compiled contract. Metadata find_distributions and invalidate_caches are the class methods from the verified package source. This authorizes metadata discovery, not loading a module returned by a custom finder. Unknown source paths remain rejected even with the finder installed.

Bootstrap loads metadata_finder after generated_source and before source_binding. Guard cache invalidation, optional absence semantics, source bytecode bypass, generated-helper pins, scientific protocol, cohort, clock caps, optimizer and old comparison-join provenance are unchanged. This is an import-origin boundary for trusted pinned source, not a sandbox against arbitrary already-running Python altering every interpreter object. Native shared-library dynamic loading remains outside a full closure claim.

## Public vendor evidence and attribution

ROOT supplied unmodified public vendor source copies after matching existing inventory bytes/mode/pins. They contain no research values. reference/vendor___init__.py is37734B SHA bbb130e3e524a73358fa46ba93e591903850652d5a9242cc7d6b367849d4986a; reference/vendor__compat.py is1313B SHA542e590cb953f8172c85ab824a174526f30d2e7b4925f67334ad667866be7a7c. Both runtime originals have mode0644. The AST test checks the exact static return-None contract, decorator and inheritance without importing the vendor module or Torch.

Primary upstream: https://github.com/python/importlib_metadata and https://raw.githubusercontent.com/python/importlib_metadata/main/importlib_metadata/_compat.py . The supplied copies, rather than moving main, are authority for this implementation. Upstream Apache2.0 license is retained as reference/IMPORTLIB_METADATA_LICENSE from https://raw.githubusercontent.com/python/importlib_metadata/v8.7.0/LICENSE ; that license link does not infer an installed version from the source. No vendor code or runtime is modified by this adapter.

Tests use an invented package imported through the actual verified loader and guard. They verify metadata discovery; absence returning None; actual missing import failure; unknown source rejection; exact loader/source/instance/class/method/bytecode binding; no execution of a malicious find_spec; removal/replacement/prepend/extra finder rejection; cache invalidation; deadline checks; and no unrelated vendor-payload eager reads. ROOT target tests and isolated lazy-Adam smoke remain necessary before actual fitting. This bundle supplies no scientific or financial admission.
