# One deterministic PyTorch helper: prospective adapter v3

13 October2026. This NEW source packet preserves v2first_clean31 and its49 target-test/import-smoke proofs unchanged. ROOT's later lazy Adam smoke failed before an optimizer step because PyTorch generated a temporary Python helper outside the static import inventory. That was a correct rejection under v2; this extension admits exactly one independently pinned helper. It does not patch Torch, the model, optimizer or runtime packages and does not change any scientific setting or deadline.

## Primary-source contract

PyTorch2.8's [instantiator](https://github.com/pytorch/pytorch/blob/v2.8.0/torch/distributed/nn/jit/instantiator.py) creates a private temporary directory and imports a source module generated there. Its fixed non-scriptable branch formats constants from the [remote-module template](https://github.com/pytorch/pytorch/blob/v2.8.0/torch/distributed/nn/jit/templates/remote_module_template.py). The [remote-module API](https://github.com/pytorch/pytorch/blob/v2.8.0/torch/distributed/nn/api/remote_module.py) invokes that branch at import. No RPC call is made merely by defining the generated methods. This implementation authorizes no scriptable/user-defined template branch.

The reviewed reference files are public vendor source copies supplied by ROOT, plus its statically derived expected helper. The test independently parses only literal template strings and applies the fixed non-scriptable substitutions without importing Torch. Expected body:2355bytes, SHA2568205b16956fb264841ecd8644784a0d157f87df79b17c16825dc1163433ce5d8. Source pins: instantiator5510bytes SHA567d1314ee27ff0b3bd22e7c4d1157246469de25e7a3183d96debe167b193615; template3463bytes SHA0ff1856bbd031b5298d46c06c0502abc20bd804f42c1949ed4127e8c773660cc. Copies retain the upstream [PyTorch license](https://github.com/pytorch/pytorch/blob/v2.8.0/LICENSE) in reference/PYTORCH_LICENSE. This is dependency compatibility evidence, not earthquake data or an experiment outcome.

## Exact added runtime field

`runtime.generated_source` is an inline object with exactly:

- schema=`torch-nonscriptable-remote-helper-v1`
- module=`_remote_module_non_scriptable`
- basename=`_remote_module_non_scriptable.py`
- body_pin=`{bytes,sha256}`: ROOT's independently frozen expected body, positive and<=65536bytes.
- generator_sources=`{instantiator:file_spec,template:file_spec}`: exact original mode/size/hash/path specifications, also positively admitted in the supplemental vendor inventory.
- temp_parent=`{path,uid,mode}`: canonical absolute root, exact observed owner and mode.
- owner_uid: exact runtime effective UID; directory_mode=0700; file_mode: exact observed mode; max_depth=1.

ROOT's matching source-only unit observed parent `/tmp`, uid0/mode01777, private child uid1000/mode0700 and helper mode0644 under UMask0022. These deployment facts are ROOT inputs, not inferred defaults or authorizations. A direct-shell preparation with another umask is not substituted. Full resource runtime_subject_pin and independently verified deployment-config pin bind every field. Existing prefix10112/critical10/four links and supplemental RECORD contract remain unchanged.

## Admission and execution

Before imports, generator source specs must match explicitly admitted vendor entries and actual bytes. At the helper import, both instantiator and template must already be loaded through the reviewed verified-source loader, with exact module/spec/loader/source-pin identity. The candidate directory must equal BOTH the loaded instantiator's INSTANTIATED_TEMPLATE_DIR_PATH and its actual TemporaryDirectory.name. Merely matching a temporary-root prefix is insufficient.

The only allowed ancestry is one `tmp` plus8 lowercase/digit/underscore characters directly beneath the pinned temp parent. Every path component is traversed without following symlinks. The parent must have its exact declared owner/mode; the private directory must belong to effective UID and be0700; the helper must be a regular file with one link, exact UID/mode/size and exact expected SHA256. File and directory metadata are rechecked around the bounded read. Different names, packages, sourceless helpers, alternate private directories, symlinks, hardlinks, mode mismatches and mismatched bodies reject.

The generated loader obtains those exact verified bytes again at get_code and compiles them directly, ignoring adjacent cached bytecode. A fixture demonstrates an ordinary loader executing a matching-timestamp malicious cache while this loader executes only the pinned body. The helper retains normal source-module package semantics. Every other unknown generated/dynamic module remains outside the allowed inventory and is rejected.

All115/345 feature statuses,65/22 common cohort, featureV1/fittingV2 distinction, source300/900 budgets, manager360/960 and whole7200+200 caps remain unchanged. No real feature value, target, model weight or forecast was read here. ROOT must run exact target tests and a bounded source-only lazy-Adam smoke before any scientific stage; this source packet alone does not certify execution success. The prior documented native CDLL/DT_NEEDED limitation remains explicit.
