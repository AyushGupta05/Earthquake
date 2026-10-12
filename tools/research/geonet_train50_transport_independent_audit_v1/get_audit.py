"""Fixed production GET profile only; no acquisition authority."""
from engine import run_audit,public_summary

def audit(plan_bytes,manifest_bytes,bounded_member_reader,*,execution_summary_bytes=None,execution_summary_pin=None):
    return run_audit('GET',plan_bytes,manifest_bytes,bounded_member_reader,execution_summary_bytes=execution_summary_bytes,execution_summary_pin=execution_summary_pin)
