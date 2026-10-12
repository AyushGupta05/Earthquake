# Accepted review 1 findings

P1 accepted: broad native `obspy.read` conversion downgraded unexpected RuntimeError to ordinary decode_unknown. Verified pinned ObsPy1.5.1 declares ObsPyMSEEDError separately; adapter now converts only that class and ValueError, and RuntimeError/MemoryError reach whole incomplete. Invented native failure after a fully decoded first batch resets all scientific promotion; declared InternalMSEEDError remains ordinary batch unknown.

P2 accepted: fixed producer schema/study/reason and top-level list/dict shape lacked predecode validation. They now reject before reader/native decode. Invented wrong/null/object/empty-list cases verify no reader invocation.

Focused affected native/bounds/replay lane passed20 tests. Final full invented suite passed45 tests; exact output and runtime limitations are pinned in TEST_RECEIPT. Public producer SCHEMA/addendum and root proposal remain byte-identical. Review1 was not clean, so its source is retained separately. Default helper will be rerun; first clean ends source work.
