"""ROOT executes only after preverified public source/bootstrap and financial gates.

Usage: invoke.py prepare|build|audit AUTHORITY_PATH BYTES SHA
       [PREP_RETURN_PATH BYTES SHA [BUILD_RETURN_PATH BYTES SHA]]
All paths/pins are ROOT private authorities supplied as arguments, not source.
"""
import time
PHASE_BEGIN=time.monotonic()
import sys
# Closed source inventories must stay unchanged even under ordinary Python.
sys.dont_write_bytecode=True
import anchor,deployment


def main(args):
    anchor.need(len(args) in (4,7,10) and args[0] in ('prepare','build','audit'),'arguments')
    def spec(i):
        anchor.need(args[i+1].isascii() and args[i+1].isdigit(),'length');return dict(path=args[i],pin=dict(bytes=int(args[i+1]),sha256=args[i+2]))
    a=anchor.parse(deployment.read(spec(1),4194304),4194304);a['processing_begin']=PHASE_BEGIN
    if args[0]=='prepare':anchor.need(len(args)==4,'arguments');result=deployment.prepare_once(a)
    else:
        anchor.need(len(args)==(7 if args[0]=='build' else 10),'arguments');result=deployment.run_stage(a,spec(4),args[0],processing_begin=PHASE_BEGIN,build_return_spec=None if args[0]=='build' else spec(7))
    # No numerical/metadata/private path values printed by wrapper.
    print(anchor.canonical(dict(status=result['status'],fit_authorized=False)).decode(),flush=True)

if __name__=='__main__':main(sys.argv[1:])
