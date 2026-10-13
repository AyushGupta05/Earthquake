# Separate audit setup V3

V2 remains frozen and its failed operational namespace is terminal. V3 changes only the operational AUDIT_ID/BASE to shared-noise-audit-v3-20261013 and the seven funding money outputs from strings to finite JSON numbers. Decimal calculations remain exact; numeric serialization must round-trip to the same decimal cents or fail. No rounding, relaxed financial rule, new scientific processing, clock extension, or fallback is introduced.

Request schema root-marked-seven-audit-setup-input-v2 and preparation receipt schema root-marked-seven-audit-control-preparation-v2 remain unchanged ABI for the existing reviewed driver/custody. Funding schema remains v1, consumed by unchanged hooks V3.finance. New control/store/evidence directories are under /home/ec2-user/eew-marked-seven-audit-v3-20261013. Whole7200+200, lease7190, source900/manager960, seven units, budget2000/reservation335/uncertainty1500, supplied task upper bound and financial validity14Oct04UTC remain unchanged. ROOT supplies positive raw receipts and the current250USD estimate; fixture values are invented, not authority.

Tests load exact copied PUBLIC hooks V3 and secure_io, write invented raw credit/funding JSON to temporary readonly files, and invoke the actual finance consumer. They include the complete RAW_CREDIT_KEYS (screen included), all seven numeric fields, fractional-cent arithmetic, V2 rejection, binding mutations and loss/overflow rejection. No test invokes prepare(), systemd, cloud, real data or real billing.

Run: python3 -B -m unittest discover -s . -p test_prepare.py -v

The reference files are code-only context, positively pinned in REFERENCE_PINS.json; they are not new production dependencies. Production prepare.py remains standalone stdlib. No __main__ entry point; ROOT alone may positively load and call prepare(request) after independent source/runtime/publication/funding checks. A saved receipt is insufficient after an exception: actual successful return plus absent failure marker is still required.
