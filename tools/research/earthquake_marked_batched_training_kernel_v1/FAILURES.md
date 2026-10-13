# Preserved invented-source failures

Initial local15-test run:14PASS/1FAIL, test_ulp_exact. np.frexp(0) exponent0 made the initial vector formula return2^-53 instead of math.ulp(0)=2^-1074. Positive/negative zero now explicitly select exponent-1074; the edge fixture retains zero, subnormal, signed powers, maxdouble and minimum normal. No actual data or numerical authority was involved.

Second local17-test run:16PASS/1ERROR in invented original-backward fixture. The fixture stacked all scalar losses then separately backwarded through the shared stack node without retention. Fixed by constructing and backwarding each scalar forecast separately, exactly like the original processor. Kernel processing unchanged.
