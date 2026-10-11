# Verified fourth-review decision

Review v4 exited 1 with one actionable source-only finding. Accepted after reproducing an invented native timeUsed containing a whitespace text node, comment and literal true: default ElementTree merged text into ' true', omitted zero timeWeight and incorrectly accepted a P pick.

Parsing now retains comment and processing-instruction nodes. They are conservatively unsupported inside the root, preserving unknown instead of inferring native literal/whitespace semantics from merged text. XML declarations and outside-root comments remain permitted because they do not affect field text. Six invented regressions cover comment and PI flag boundaries, reference scope, QML scalar comments, conservative root comments and valid outside-root XML metadata.

After fixes, tests_v12.txt records 260 invented tests, all passing. Actual inputs and producer implementation remain unread. Same Codex engine reviews the updated complete snapshot; first clean ends edits/review.
