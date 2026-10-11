autoreview findings: 1
[P2] [P2] Ignore declaration-like text in outside-root comments and PIs
projection.py:172
The whole-body substring check rejects declaration-like text inside otherwise valid outside-root comments or processing instructions. For example, prefixing a clean invented fixture with `<!-- <!DOCTYPE invented> -->` changes its result from `ok` to `unknown_representation` with `unsafe_XML`, although no DOCTYPE is declared. This contradicts the frozen v2 policy that outside-root comments/PIs are ignored; on native input it also unnecessarily withholds the paired QML profile. Detect actual forbidden declarations without treating ignored comment/PI content as markup, and cover this case with an invented fixture.

overall: patch is incorrect (0.94)
The inside-root comment/PI handling fails closed, but the preliminary substring scan lets harmless outside-root comment/PI content change projection availability, violating the explicit v2 contract. Review used read-only source inspection; tests were not executed.
