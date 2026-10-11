# Curated documentation and source-pin allowlist

Exact allowlist for this source-audit handoff:

- `PRIMARY_SOURCE_AUDIT.md`
- `NEW_OFFLINE_PROTOCOL_PROPOSAL.md`
- `source_pins.json`
- `CURATED_ALLOWLIST.md`
- `CURATED_PACKET_SHA256.txt`

These files are authored documentation/provenance, plus SHA-256 pins of the four content files; the hash list does not hash itself. This is a local content freeze, not a reviewed/pushed implementation freeze. No actual event/data/model/private receipt content is included. The aggregate diagnostic context in the proposal was supplied by the parent and is explicitly not reverified.

Excluded from this curated review/publish handoff: downloaded `.xsl` source text, public-source HTTP headers, every original diagnostic artifact, any raw event pair, any model/data file, and any private receipt. The downloaded sources remain unchanged inert local audit inputs with notices intact. Their source headers declare LGPL version 3; accompanying distribution-license materials have not been assembled in this audit. Link to the immutable official sources using the pin manifest instead of including raw source.

No actual-read authorization, new event request, transform execution, deployment inference, Git mutation, or compatibility-result publication is implied by this allowlist. A later implementation's review must use a newly enumerated exact code/invented-test/protocol allowlist and a separate parent actual-read handoff.
