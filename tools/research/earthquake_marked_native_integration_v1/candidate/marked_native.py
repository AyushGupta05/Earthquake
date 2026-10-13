"""Pure native-byte replay and marked features. No paths, IO, fitting or authority.

ROOT must bind the injected original modules/decoder and anchor to their reviewed
sources and original private packet. A Python object or a hash assertion is not
proof of that external custody. The builder never imports a model or inverts f32.
"""
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import statistics
import time

import numpy as np

SCHEMA = "earthquake-TRAIN115-marked-noise-observations-v1"
STUDY = "earthquake-TRAIN115-marked-noise-study-v1"
ANCHOR_SCHEMA = "marked-native-original-activity-anchor-v1"
ORIGINAL_SCHEMA = "earthquake-TRAIN115-receiver-observations-v2"
ORIGINAL_STUDY = "earthquake-TRAIN115-receiver-renewal-v2"
HORIZONS = (1, 3, 5)
Q = 250_000_000
SECOND = 1_000_000_000
DELTA = -12.0
CENSOR_LIMIT = math.exp(DELTA)
LIMITS = dict(old_plan=131072, old_qualified=64*1024*1024,
              new_plan=131072, new_qualified=64*1024*1024,
              metadata=131072, roster=131072, activity_anchor=4*1024*1024)
DENOMINATORS = dict(events=115, horizon_cells=345, train=91, dev=24,
                    common_train=65, common_dev=22, test_excluded=31)
ORIGINAL_DENOMINATORS = dict(events=115, cells=345, train=91, dev=24, test_excluded=31)


class FeatureError(ValueError):
    """No successful packet on failure; bounded partial evidence stays private."""
    def __init__(self, code, *, rows=None, observed_samples=None, diagnostics=None):
        super().__init__(code)
        self.code = code
        self.partial_rows = [] if rows is None else rows
        self.observed_samples = dict(old=0, new=0) if observed_samples is None else dict(observed_samples)
        self.diagnostics = {} if diagnostics is None else diagnostics


def need(ok, code):
    if not ok:
        raise FeatureError(code)


def keys(obj, names):
    return type(obj) is dict and all(type(k) is str for k in obj) and set(obj) == set(names)


def integer(x, lo, hi):
    return type(x) is int and lo <= x <= hi


def number(x, lo=-math.inf, hi=math.inf):
    return type(x) in (int, float) and math.isfinite(x) and lo <= x <= hi


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")


def pin(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def valid_pin(p, cap):
    return (keys(p, ("bytes", "sha256")) and integer(p["bytes"], 0, cap)
            and type(p["sha256"]) is str and len(p["sha256"]) == 64
            and all(c in "0123456789abcdef" for c in p["sha256"]))


def deadline(begin):
    now = time.monotonic()
    need(number(begin, 0, now) and now-begin <= 300, "deadline")


def array(values, dtype, shape=None):
    a = np.ascontiguousarray(values, dtype=dtype)
    need((shape is None or a.shape == shape) and np.isfinite(a).all(), "feature_array")
    return a


def bit_equal(a, b):
    return a.dtype.str == b.dtype.str and a.shape == b.shape and a.tobytes(order="C") == b.tobytes(order="C")


def report_ratio(value):
    need(number(value,0,1e25),"ratio_bound")
    if value<=CENSOR_LIMIT:
        return DELTA,1
    logged=math.log(value)
    # A representational boundary collision cannot become a fake uncensored mark.
    need(logged>DELTA,"censor_log_roundoff")
    return logged,0


@dataclass(frozen=True)
class Bindings:
    """Original renewal_v2 observations module, independently source-bound by ROOT."""
    observations: object

    def validate(self):
        o = self.observations
        need(o.SCHEMA == ORIGINAL_SCHEMA and o.STUDY == ORIGINAL_STUDY, "binding_schema")
        for name in ("qualified_validate", "metadata_validate", "replay_batch", "components", "context", "json_load"):
            need(callable(getattr(o, name, None)), "binding_callable")
        for name in ("_piece_geometry", "_mean", "_window_values", "_noise", "_sequence"):
            need(callable(getattr(o.am, name, None)), "binding_reducer")
        need(o.am.QUARTER == Q and o.am.SECOND == SECOND, "binding_clock")


def _numeric_list(xs, n, lo=-math.inf, hi=math.inf):
    return type(xs) is list and len(xs) == n and all(number(x, lo, hi) for x in xs)


def _validate_anchor(anchor, metadata=None, roster=None, input_pins=None):
    need(keys(anchor, ("schema", "original_schema", "original_study", "source_pins", "input_pins", "denominators", "rows")), "anchor_schema")
    need(anchor["schema"] == ANCHOR_SCHEMA and anchor["original_schema"] == ORIGINAL_SCHEMA
         and anchor["original_study"] == ORIGINAL_STUDY, "anchor_schema")
    need(keys(anchor["source_pins"], ("archive", "manifest"))
         and valid_pin(anchor["source_pins"]["archive"], 128*1024*1024)
         and valid_pin(anchor["source_pins"]["manifest"], 4*1024*1024), "anchor_source_pins")
    need(keys(anchor["input_pins"], set(LIMITS)-{"activity_anchor"})
         and all(valid_pin(p, LIMITS[k]) for k,p in anchor["input_pins"].items()), "anchor_input_pins")
    if input_pins is not None:
        need(canonical(anchor["input_pins"]) == canonical(input_pins), "anchor_input_binding")
    need(canonical(anchor["denominators"]) == canonical(ORIGINAL_DENOMINATORS), "anchor_denominators")
    need(type(anchor["rows"]) is list and len(anchor["rows"]) == 115, "anchor_rows")
    totals = dict(TRAIN=0, DEV=0); common = dict(TRAIN=0, DEV=0)
    for i,r in enumerate(anchor["rows"]):
        need(keys(r, ("ordinal", "partition", "mw", "group", "common", "status", "context35", "horizons")), "anchor_row")
        need(integer(r["ordinal"], i, i) and type(r["partition"]) is str and r["partition"] in totals
             and number(r["mw"], -5, 15) and integer(r["group"], -1, i)
             and type(r["common"]) is bool, "anchor_role")
        totals[r["partition"]] += 1
        if metadata is not None:
            need(all(canonical(r[k]) == canonical(metadata[i][k]) for k in ("ordinal", "partition", "group"))
                 and float(r["mw"]) == float(metadata[i]["mw"]) and r["common"] is roster["rows"][i]["common"], "anchor_role_binding")
        need(type(r["horizons"]) is list and len(r["horizons"]) == 3, "anchor_horizons")
        if not r["common"]:
            need(r["status"] == "unavailable" and r["context35"] is None
                 and canonical(r["horizons"]) == canonical([dict(seconds=h, status="unavailable") for h in HORIZONS]), "anchor_unavailable")
            continue
        common[r["partition"]] += 1
        need(r["group"] >= 0 and r["status"] == "available" and _numeric_list(r["context35"], 35), "anchor_context")
        previous = None
        for h,a in zip(HORIZONS, r["horizons"]):
            need(keys(a, ("seconds", "status", "ratios", "states", "run_ages"))
                 and integer(a["seconds"], h, h) and a["status"] == "available", "anchor_horizon")
            rs = a["ratios"]; n = len(rs) if type(rs) is list else -1
            need(1 <= n <= 20 and _numeric_list(rs, n, 0, 1e25)
                 and type(a["states"]) is list and len(a["states"]) == n
                 and type(a["run_ages"]) is list and len(a["run_ages"]) == n, "anchor_history")
            age = 0; prev = None
            for ratio,s,run in zip(rs,a["states"],a["run_ages"]):
                expected = int(ratio > 9.0); age = age+1 if prev == expected else 1
                need(integer(s, expected, expected) and integer(run, age, age), "anchor_history")
                prev = expected
            if previous is not None:
                m = len(previous["ratios"])
                need(n == m+8 and all(bit_equal(array(a[k][:m], "<f8" if k == "ratios" else "u1"),
                                                        array(previous[k], "<f8" if k == "ratios" else "u1"))
                                      for k in ("ratios", "states", "run_ages")), "anchor_future_mismatch")
            previous = a
    need(totals == dict(TRAIN=91, DEV=24) and common == dict(TRAIN=65, DEV=22), "anchor_counts")


def project_anchor(original_packet, *, source_pins):
    """Project ROOT-verified original memory packet; never fabricate from marks.

    Does not inspect original waves/amplitudes. ROOT must separately establish
    canonical equality to its positively bound packet before authorizing build.
    """
    p = original_packet
    need(keys(p, ("schema", "study", "rows", "denominators", "input_pins", "observed_samples", "fit_authorized"))
         and p["schema"] == ORIGINAL_SCHEMA and p["study"] == ORIGINAL_STUDY
         and p["fit_authorized"] is False and type(p["rows"]) is list and len(p["rows"]) == 115, "original_packet")
    rows = []
    for i,r in enumerate(p["rows"]):
        need(keys(r, ("ordinal", "partition", "mw", "group", "common", "status", "initial", "horizons")), "original_row")
        item = {k:r[k] for k in ("ordinal", "partition", "mw", "group", "common", "status")}
        if r["common"] is True:
            need(keys(r["initial"], ("wave", "amplitude", "context")), "original_initial")
            ctx = r["initial"]["context"]
            need(type(ctx) is np.ndarray and ctx.dtype == np.dtype("float64") and ctx.shape == (35,)
                 and ctx.flags.c_contiguous and np.isfinite(ctx).all(), "original_context")
            item["context35"] = ctx.tolist(); item["horizons"] = []
            need(type(r["horizons"]) is list and len(r["horizons"]) == 3, "original_horizons")
            for h,x in zip(HORIZONS,r["horizons"]):
                need(keys(x, ("seconds", "rate", "wave", "amplitude", "context", "ratios", "states", "run_ages"))
                     and integer(x["seconds"], h, h), "original_horizon")
                item["horizons"].append(dict(seconds=h,status="available",**{k:x[k] for k in ("ratios","states","run_ages")}))
        else:
            need(r["initial"] is None, "original_unavailable")
            item.update(context35=None, horizons=r["horizons"])
        rows.append(item)
    a = dict(schema=ANCHOR_SCHEMA, original_schema=p["schema"], original_study=p["study"],
             source_pins=source_pins, input_pins=p["input_pins"], denominators=p["denominators"], rows=rows)
    _validate_anchor(a)
    raw = canonical(a); need(len(raw) <= LIMITS["activity_anchor"], "anchor_cap")
    return raw


def event_marks(native, row, meta, anchor_row, *, bindings, processing_begin):
    diagnostics={"stage":"native_geometry"}
    try:
        return _event_marks(native,row,meta,anchor_row,bindings=bindings,processing_begin=processing_begin,diagnostics=diagnostics)
    except Exception as error:
        code=error.code if isinstance(error,FeatureError) else "native_reduction_failure:"+type(error).__name__
        raise FeatureError(code,diagnostics=diagnostics) from error


def _event_marks(native, row, meta, anchor_row, *, bindings, processing_begin,diagnostics):
    """Exact native reductions after original full-record/piece qualification."""
    deadline(processing_begin); bindings.validate(); o = bindings.observations; am = o.am
    prepared = am._piece_geometry(native, row["family"])
    t0,p = row["t0_ns"],row["pick_ns"]
    need(integer(t0, -(2**63)+3*SECOND, 2**63-1-5*SECOND)
         and integer(p,t0,t0+750_000_000), "current_clock")
    rate = Fraction(SECOND)/Fraction(*native[0]["pieces"][0]["rational_period"])
    need(all(Fraction(SECOND)/step == rate for pieces in prepared for _,step,_,_ in pieces), "native_rate")

    def power(pieces, lo, hi, center):
        # Original scalar reducer/order; additional schema bound never repairs.
        for v in am._window_values(pieces,lo,hi):
            need(abs(v-center) <= 1e12, "centered_bound")
        value = am._mean(pieces,lo,hi,center,True)
        need(number(value,0,1e24), "power_bound")
        return value

    centers=[]; quarters=[]; nhat=[]; floors=[]
    diagnostics.update(stage="noise",centers=centers,quarter_powers=quarters,nhat=nhat,floors=floors)
    for pieces in prepared:
        deadline(processing_begin)
        center=am._mean(pieces,t0-3*SECOND,t0)
        values=[power(pieces,t0-3*SECOND+j*Q,t0-3*SECOND+(j+1)*Q,center) for j in range(12)]
        med=statistics.median(values)
        centers.append(center);quarters.append(values);nhat.append(max(1.0,med));floors.append(int(med<1.0))
    old_c,old_n,old_f=am._noise(prepared,t0)
    need(bit_equal(array(centers,"<f8"),array(old_c,"<f8"))
         and bit_equal(array(nhat,"<f8"),array(old_n,"<f8")) and floors == [int(f) for f in old_f], "noise_reducer_parity")
    eta=[[math.log(max(1.0,statistics.median(qs[:ell]+qs[ell+1:]))) for qs in quarters] for ell in range(12)]
    offsets=[math.fsum(eta[ell][c] for ell in range(12))/12 for c in range(3)]
    nu=[[eta[ell][c]-offsets[c] for c in range(3)] for ell in range(12)]
    noise=dict(centers=array(centers,"<f8",(3,)),powers=array(quarters,"<f8",(3,12)),nhat=array(nhat,"<f8",(3,)),
               floors=array(floors,"u1",(3,)),nu=array(nu,"<f8",(12,3)),weights=array([1.0/12]*12,"<f8",(12,)),
               rate=[rate.numerator,rate.denominator],arrival_offset_ns=p-t0)
    horizons=[]; base_context=None
    diagnostics.update(stage="current_cells",noise=noise,horizons=horizons)
    for h,anchor in zip(HORIZONS,anchor_row["horizons"]):
        deadline(processing_begin); n=(h*SECOND-(p-t0))//Q
        need(1<=n<=20 and anchor["seconds"]==h and anchor["status"]=="available", "anchor_deadline")
        ratios=[[power(pieces,p+j*Q,p+(j+1)*Q,center)/ref for pieces,center,ref in zip(prepared,centers,nhat)] for j in range(n)]
        need(all(number(v,0,1e25) for r in ratios for v in r), "ratio_bound")
        maxima=[max(r) for r in ratios]; states,ages,_,_=am._sequence(maxima)
        need(bit_equal(array(maxima,"<f8"),array(anchor["ratios"],"<f8"))
             and states==anchor["states"] and ages==anchor["run_ages"], "activity_anchor_parity")
        if base_context is None:
            context35=array([*[math.log10(x) for x in nhat],*map(float,floors),float(states[0]),*o.context(row,meta,.25,rate)[1:]],"<f8",(35,))
            need(bit_equal(context35,array(anchor_row["context35"],"<f8",(35,))), "context_anchor_parity")
            base_context=np.ascontiguousarray(np.delete(context35,6),dtype="<f8")
        diagnostics.update(current_horizon=h,current_ratios=ratios)
        marks=[[report_ratio(v) for v in r] for r in ratios]
        reported=[[x[0] for x in r] for r in marks];censor=[[x[1] for x in r] for r in marks]
        horizons.append(dict(seconds=h,status="available",ratios=array(ratios,"<f8",(n,3)),reported=array(reported,"<f8",(n,3)),
                             censor=array(censor,"u1",(n,3)),max_ratios=array(maxima,"<f8",(n,)),states=array(states,"u1",(n,)),run_ages=array(ages,"u1",(n,))))
    for a,b in zip(horizons,horizons[1:]):
        n=len(a["ratios"]);need(len(b["ratios"])==n+8 and all(bit_equal(a[k],b[k][:n]) for k in ("ratios","reported","censor","max_ratios","states","run_ages")), "prefix_parity")
    deadline(processing_begin)
    return base_context,noise,horizons


def build_marked(old_plan_bytes,old_qualified_bytes,old_bodies,new_plan_bytes,new_qualified_bytes,new_bodies,
                 metadata_bytes,roster_bytes,activity_anchor_bytes,decode_record,*,bindings,pins,processing_begin):
    """Fixed 115 slots/345 statuses. Any common-row failure rejects the stage."""
    rows=[]; counts=dict(old=0,new=0)
    try:
        deadline(processing_begin);bindings.validate();o=bindings.observations
        inputs=dict(old_plan=old_plan_bytes,old_qualified=old_qualified_bytes,new_plan=new_plan_bytes,new_qualified=new_qualified_bytes,
                    metadata=metadata_bytes,roster=roster_bytes,activity_anchor=activity_anchor_bytes)
        need(keys(pins,inputs),"input_pins")
        for k,raw in inputs.items():
            need(type(raw) is bytes and len(raw)<=LIMITS[k] and valid_pin(pins[k],LIMITS[k]) and pin(raw)==pins[k],"input_pin")
        parsed={k:o.json_load(v,LIMITS[k]) for k,v in inputs.items()}
        op,oq,np_,nq,metadata,roster,anchor=(parsed[k] for k in inputs)
        o.qualified_validate(o.old_native,op,oq,old_bodies,65,17)
        o.qualified_validate(o.new_native,np_,nq,new_bodies,50,13)
        o.metadata_validate(metadata,(op,np_),roster)
        _validate_anchor(anchor,metadata,roster,{k:pins[k] for k in pins if k!="activity_anchor"})
        need(callable(decode_record),"decoder")
        need(sum(m["partition"]=="TRAIN" for m in metadata)==91 and sum(m["partition"]=="DEV" for m in metadata)==24,"role_counts")
        numeric_bytes=0
        for core,plan,q,bodies,offset,namespace in ((o.old_native,op,oq,old_bodies,0,"old"),(o.new_native,np_,nq,new_bodies,65,"new")):
            cached=None;records={}
            for r,qr in zip(plan["rows"],q["rows"]):
                deadline(processing_begin);i=offset+r["ordinal"];m=metadata[i];common=roster["rows"][i]["common"]
                result=dict(ordinal=i,partition=m["partition"],mw=float(m["mw"]),group=m["group"],common=common,
                            status="available" if common else "unavailable",precontext=None,noise=None,
                            horizons=[dict(seconds=h,status="unavailable") for h in HORIZONS])
                if common:
                    if cached!=r["batch"]:
                        records.clear();records=o.replay_batch(core,plan,q,bodies,decode_record,r["batch"],counts,namespace,processing_begin);cached=r["batch"]
                    native=o.components(core,r,qr,records)
                    context,noise,hs=event_marks(native,r,m,anchor["rows"][i],bindings=bindings,processing_begin=processing_begin)
                    del native
                    result.update(precontext=context,noise=noise,horizons=hs)
                    numeric_bytes+=context.nbytes+sum(a.nbytes for a in noise.values() if type(a) is np.ndarray)+sum(a.nbytes for h in hs for a in h.values() if type(a) is np.ndarray)
                    need(numeric_bytes<=1024*1024,"numeric_output_cap")
                rows.append(result)
            records.clear()
        deadline(processing_begin)
        need(len(rows)==115,"row_count")
        return dict(schema=SCHEMA,study=STUDY,rows=rows,denominators=dict(DENOMINATORS),input_pins={k:dict(v) for k,v in pins.items()},observed_samples=counts,fit_authorized=False)
    except Exception as error:
        code=error.code if isinstance(error,FeatureError) else "original_replay_failure:"+type(error).__name__
        diagnostics=dict(error.diagnostics) if isinstance(error,FeatureError) else {}
        if 'i' in locals():diagnostics['ordinal']=i
        raise FeatureError(code,rows=rows,observed_samples=counts,diagnostics=diagnostics) from error
