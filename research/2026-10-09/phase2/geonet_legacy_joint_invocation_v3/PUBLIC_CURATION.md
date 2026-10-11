# Public source curation closure

V3's exact safe_to_promote_paths.json is the only publication allowlist. It must
include all120 source-only dependency members pinned by
public_dependency_bundles.json (86 producer,34 auditor), including the three
generic producer companions omitted from V2's top list. V2 remains immutable.
No scientific source is changed and no actual failure cause is inferred.

Root-verifiable final closure algorithm:

1. Load the pinned V3 manifest, safe allowlist and public source-bundle mapping.
2. For each producer/auditor bundle member, prepend public_dependencies/ROLE/
   to its canonical relative name. Require that exact name in manifest.members
   AND its work/geonet_legacy_joint_invocation_v3/NAME path in the safe allowlist.
3. Require the copied public file exists as a regular non-symlink source file.
   Require its exact bytes/SHA256 to equal both bundle and manifest pins.
4. Require exactly86 producer +34 auditor matches and unchanged four literal
   scientific implementation SHA256 pins. No source directory from an actual
   plan or private receipt is consulted.
5. Require every safe allowlist path to exist in the packet, every manifest
   member to have its matching public file/pin, and no review_snapshot/ or
   actual/private/raw-external path in the allowlist.

public_curation_closure.json records these executed source-only checks. It binds
bundle and allowlist hashes plus manifest-member name-set hash; the manifest
pins the closure receipt's bytes. The manifest cannot pin itself. Root obtains
its SHA256 from the handoff and independently repeats this finite check before
publication or any new actual private gate. Presence of these source documents
is neither actual-input authorization nor proof of a completed diagnostic.

review_snapshot/.git, temporary fixtures/process outputs, every actual plan,
authorization, body, raw ID, execution receipt and private result are excluded.
Only our authored code, invented tests, generic contracts/pins and source-only
review/runtime/test/curation evidence are eligible. No raw official source or
source-service HTTP header is included.
