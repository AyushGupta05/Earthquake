"""Invented complete fixture, independent normal references and invalid bindings."""
import copy
import math
import unittest
from unittest.mock import patch
import numpy as np
import auditor


def fixture():
    rows=[];common=set(range(30))|set(range(41,59))|set(range(65,105));mw=lambda i:(6. if i<65 else 5.75) if i%2==0 else 4.
    for i in range(115):
        cells=[]
        for h in (1,3,5):
            good=i in common
            cells.append(dict(horizon=h,status="available" if good else "unavailable",reason="supported" if good else "operational_ineligible",
                              array="wave_%03d_%d"%(i,h) if good else None,shape=[3,100*(h+3)] if good else None,first=[1704067200000000000,1] if good else None,
                              period=[10000000,1] if good else None,precontext_count=300 if good else None,channels=["HHE","HHN","HHZ"],view_sha256=["0"*64]*3 if good else None))
        rows.append(dict(ordinal=i,partition="TRAIN" if i<41 or i>=65 else "DEV",group=-1 if i==114 else i,mw=mw(i),operational_eligible=i!=114,cohort=i in common,source="original65" if i<65 else "new50",original_group=i if i<65 else None,original_cohort=i in common if i<65 else None,cells=cells))
    manifest=dict(schema="earthquake-TRAIN115-native-count-artifact-v1",study=auditor.STUDY,proposal_sha256=auditor.PROPOSAL_SHA,custody={k:dict(bytes=1,sha256="0"*64) for k in ("old_npz","old_manifest","new_plan","new_qualified","metadata")},native_namespaces=dict(original_rows=65,original_bodies=17,new_rows=50,new_bodies=13),observed_new_samples=1000,rows=rows,denominators=dict(rows=115,cells=345,train=91,dev=24,test_excluded=31))
    # Independent scalar standard-normal formula, no auditor score call.
    z=1.;cdf=.5*(1+math.erf(z/math.sqrt(2)));phi=math.exp(-.5*z*z)/math.sqrt(2*math.pi)
    nll=.5*math.log(2*math.pi)+.5;crps=z*(2*cdf-1)+2*phi-1/math.sqrt(math.pi)
    metric=dict(n=18,nll=nll,crps=crps,mae=1.,medae=1.,tail_mae_5_5=1.,tail_mae_6=1.,tail_bias=-1.,lower_mae=1.,lower_medae=1.,cvar95=1.,p95=1.,maximum=1.,median_mae=1.,coverage_50=0.,coverage_90=1.,coverage_95=1.)
    train=list(range(30))+list(range(65,105));dev=list(range(41,59))
    support=dict(status="pass",counts=dict(train=70,dev=18,train_high=35,dev_high=9,train_lower=35,dev_lower=9,dev_high_groups=9,old_train=30,new_train=40,old_train_high=15,new_train_high=20,old_train_lower=15,new_train_lower=20,unknown_groups=1),train=train,dev=dev,status_panels={"original65":{str(h):48 for h in (1,3,5)},"new50":{str(h):40 for h in (1,3,5)}},DEV_reused_exploratory=True)
    history=[dict(update=i,nll=nll,seconds=i/100) for i in range(1,301)]
    fits=[]
    for seed in auditor.SEEDS:
        for arm in auditor.ARMS:
            preds=[dict(ordinal=i,horizon=h,rate=[100,1],target=mw(i),pi=[.2]*5,mu=[5.]*5,sigma=[1.]*5,mean=5.,median=5.,nll=nll,crps=crps) for i in dev for h in (1,3,5)]
            fits.append(dict(seed=seed,arm=arm,status="complete",history=copy.deepcopy(history),predictions=preds,metrics={str(h):dict(metric) for h in (1,3,5)},rate_strata={str(h):[dict(rate=[100,1],n=18,groups=18,status="descriptive",metrics=dict(metric))] for h in (1,3,5)}))
    intervals={}
    for k in metric:
        if k=="n":continue
        groups=9 if k in ("tail_mae_5_5","tail_mae_6","tail_bias","lower_mae","lower_medae") else 18
        intervals[k]=dict(status="descriptive",groups=groups,mean=0.,interval=[0.,0.])
    comparisons=[dict(seed=seed,horizon=h,pair="W-"+other,intervals=copy.deepcopy(intervals),rate_strata=[dict(rate=[100,1],n=18,intervals=copy.deepcopy(intervals))]) for seed in auditor.SEEDS for other in ("M","P") for h in (1,3,5)]
    guard=dict(pass_all=True,checks=[dict(seed=seed,horizon=h,mae_not_worse=True,medae_not_worse=True) for seed in auditor.SEEDS for h in (1,3,5)])
    return dict(status="complete",support=support,fits=fits,original_advance=False,bulk_guard=guard,advance=False,comparisons=comparisons),manifest


class ScoreTests(unittest.TestCase):
    def test_normal_nll_crps_and_mixture_normalization(self):
        out=auditor.score(0,[.2]*5,[0.]*5,[1.]*5)
        self.assertAlmostEqual(out["nll"],.5*math.log(2*math.pi),places=12)
        self.assertAlmostEqual(out["crps"],(math.sqrt(2)-1)/math.sqrt(math.pi),places=12)
        self.assertEqual(out["median"],0);self.assertEqual(out["mean"],0)
        self.assertEqual(out["coverage_50"],1)
        out=auditor.score(100,[1.,0,0,0,0],[0.]*5,[.05]*5)
        self.assertTrue(math.isfinite(out["nll"]))
        for pi,mu,sd in (([.1]*5,[0.]*5,[1.]*5),([.2]*5,[float("nan")]*5,[1.]*5),([.2]*5,[0.]*5,[.049]*5)):
            with self.assertRaises(ValueError):auditor.score(1.,pi,mu,sd)

    def test_crps_independent_cdf_integral_and_mean(self):
        pi=[.1,.2,.3,.15,.25];mu=[-2.,-1.,0,2.,3.];sd=[.4,.5,1.,2.,.2];target=.75
        out=auditor.score(target,pi,mu,sd)
        grid=np.linspace(-30,30,120001)
        cdf=np.array([sum(p*.5*(1+math.erf((x-m)/(s*math.sqrt(2)))) for p,m,s in zip(pi,mu,sd)) for x in grid])
        self.assertAlmostEqual(out["crps"],float(np.trapezoid((cdf-(grid>=target))**2,grid)),delta=.0003)
        self.assertAlmostEqual(out["mean"],.65)

    def test_preserve_float32_pi_and_declared_score_tolerance(self):
        pi=np.asarray([.1,.2,.3,.15,.25],dtype=np.float32).tolist()
        out=auditor.score(1.,pi,[1,2,3,4,5],[1.]*5)
        self.assertAlmostEqual(out["mean"],sum(p*m for p,m in zip(pi,[1,2,3,4,5])),places=12)
        self.assertTrue(auditor._close(out["mean"]+1e-7,out["mean"]))
        self.assertFalse(auditor._close(out["mean"]+.01,out["mean"]))
        self.assertFalse(auditor._close(True,1));self.assertFalse(auditor._close(1.,1))


class AuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result,cls.manifest=fixture()
        cls.replay=auditor.audit(cls.result,cls.manifest)

    def test_complete_sixfit_replay_with_false_advance(self):
        self.assertEqual(self.replay["status"],"pass")
        self.assertFalse(self.replay["advance"])
        self.assertEqual(len(self.replay["fits"]),6)
        self.assertEqual(sum(len(f["predictions"]) for f in self.replay["fits"]),324)
        self.assertEqual(self.replay["support"]["counts"]["dev"],18)

    def test_exact_ordinals_labels_rates_horizons_before_scoring(self):
        for key,value in (("ordinal",True),("ordinal",40),("horizon",5),("target",6.1),("rate",[200,2]),("rate",[50,1])):
            r=copy.deepcopy(self.result);r["fits"][0]["predictions"][0][key]=value
            with patch.object(auditor,"score",side_effect=AssertionError("score")):
                self.assertEqual(auditor.audit(r,self.manifest)["status"],"fail")

    def test_missing_duplicate_permuted_prediction_and_arm(self):
        cases=[]
        r=copy.deepcopy(self.result);r["fits"][0]["predictions"].pop();cases.append(r)
        r=copy.deepcopy(self.result);r["fits"][0]["predictions"][1]=r["fits"][0]["predictions"][0];cases.append(r)
        r=copy.deepcopy(self.result);r["fits"][0],r["fits"][1]=r["fits"][1],r["fits"][0];cases.append(r)
        r=copy.deepcopy(self.result);r["fits"][0]["status"]="incomplete";cases.append(r)
        for r in cases:self.assertEqual(auditor.audit(r,self.manifest)["status"],"fail")

    def test_manifest_denominator_cohort_cross_group_and_test_reject(self):
        for change in (lambda m:m["rows"].pop(),lambda m:m["rows"][0].update(cohort=False),lambda m:m["rows"][41].update(group=0),lambda m:m["rows"][41].update(partition="TEST")):
            m=copy.deepcopy(self.manifest);change(m)
            self.assertEqual(auditor.audit(self.result,m)["status"],"fail")

    def test_stored_scores_and_metrics_cannot_be_trusted(self):
        # One full mismatch replay tests independently recomputed outputs.
        r=copy.deepcopy(self.result);r["fits"][0]["predictions"][0]["mean"]+=.1
        r["fits"][0]["metrics"]["1"]["mae"]+=.1;r["fits"][0]["rate_strata"]["1"][0]["groups"]-=1
        r["comparisons"][0]["intervals"]["mae"]["mean"]+=.1;r["advance"]=True
        replay=auditor.audit(r,self.manifest)
        self.assertEqual(replay["status"],"fail")
        self.assertEqual(set(replay["reasons"]),{"stored_prediction","stored_metrics","stored_rate_strata","stored_comparisons","stored_advance"})
        self.assertFalse(replay["advance"])

    def test_histories_exact300_and_injected_journal(self):
        r=copy.deepcopy(self.result);r["fits"][0]["history"][3]["update"]=5
        self.assertEqual(auditor.audit(r,self.manifest)["status"],"fail")
        r=copy.deepcopy(self.result);r["fits"][0]["history"][0]["seconds"]=-.1
        self.assertEqual(auditor.audit(r,self.manifest)["status"],"fail")
        histories={(f["seed"],f["arm"]):copy.deepcopy(f["history"]) for f in self.result["fits"]}
        histories[(auditor.SEEDS[0],"W")][0]["nll"]+=.1
        self.assertEqual(auditor.audit(self.result,self.manifest,histories)["status"],"fail")

    def test_small_group_intervals_unsupported_and_rate_counts(self):
        preds=self.replay["fits"][0]["predictions"][:3]
        out=auditor.paired(preds,preds,list(range(115)))
        self.assertEqual(out["nll"]["status"],"unsupported")
        mixed=copy.deepcopy(self.replay["fits"][0]["predictions"][:6]);mixed[0]["rate"]=[3,2]
        strata=auditor.rate_strata(mixed,list(range(115)))
        self.assertEqual(sum(s["n"] for s in strata),6)
        self.assertEqual({tuple(s["rate"]) for s in strata},{(3,2),(100,1)})

    def test_strict_advance_all_seed_horizon_guards(self):
        fits=[]
        for seed in auditor.SEEDS:
            for arm in auditor.ARMS:
                m=dict(nll=2.,crps=2.,tail_mae_5_5=.5,lower_mae=.2,lower_medae=.2,cvar95=.9,maximum=1.,mae=.3,medae=.25)
                if arm=="W":m.update(nll=1.,crps=1.,tail_mae_5_5=.47)
                fits.append(dict(seed=seed,arm=arm,status="complete",metrics={str(h):dict(m) for h in (1,3,5)}))
        self.assertTrue(auditor.original_advance(fits))
        for name,value in (("nll",2.),("tail_mae_5_5",.49),("maximum",1.01),("lower_mae",.21)):
            bad=copy.deepcopy(fits);bad[3]["metrics"]["5"][name]=value;self.assertFalse(auditor.original_advance(bad))
        self.assertFalse(auditor.original_advance(fits[:-1]))
        bad=copy.deepcopy(fits);bad[0]["status"]="incomplete";self.assertFalse(auditor.original_advance(bad))

    def test_output_admission_cannot_promote(self):
        with patch.object(auditor,"MAX_OUTPUT",1):
            replay=auditor.audit(self.result,self.manifest)
        self.assertEqual(replay["status"],"fail");self.assertEqual(replay["fits"],[])

    def test_new115_support_counts_status_panels_and_original_dev_only(self):
        support=self.replay["support"]
        self.assertEqual(support["counts"]["train"],70);self.assertEqual(support["counts"]["old_train"],30)
        self.assertEqual(support["counts"]["new_train"],40);self.assertEqual(support["counts"]["unknown_groups"],1)
        self.assertTrue(support["DEV_reused_exploratory"])
        self.assertEqual(support["status_panels"],{"original65":{str(h):48 for h in (1,3,5)},"new50":{str(h):40 for h in (1,3,5)}})
        self.assertTrue(all(p["ordinal"]<65 for f in self.replay["fits"] for p in f["predictions"]))
        for mutate in (lambda s:s["counts"].update(new_train=39),lambda s:s["status_panels"]["original65"].update({"1":47}),lambda s:s.update(DEV_reused_exploratory=False)):
            r=copy.deepcopy(self.result);mutate(r["support"])
            with patch.object(auditor,"score",side_effect=AssertionError("score")):
                self.assertEqual(auditor.audit(r,self.manifest)["status"],"fail")

    def test_manifest_provenance_custody_namespaces_and_new_train_strict(self):
        for mutate in (lambda m:m["denominators"].update(rows=114),lambda m:m["native_namespaces"].update(new_bodies=12),
                       lambda m:m.update(observed_new_samples=True),lambda m:m.update(observed_new_samples=104000001),
                       lambda m:m["custody"]["old_npz"].update(bytes=True),lambda m:m["custody"]["metadata"].update(sha256="g"*64),
                       lambda m:m["rows"][65].update(partition="DEV"),lambda m:m["rows"][65].update(original_cohort=False),
                       lambda m:m["rows"][65].update(source="original65"),lambda m:m["rows"][0]["cells"][0].update(array="wave_00_1")):
            m=copy.deepcopy(self.manifest);mutate(m)
            with self.assertRaises(ValueError):auditor._manifest(m)

    def test_original_role_false_with_available_cells_retained(self):
        m=copy.deepcopy(self.manifest);m["rows"][0]["cohort"]=False
        rows,support=auditor._manifest(m)
        self.assertTrue(rows[0]["original_cohort"]);self.assertTrue(all(c["status"]=="available"for c in rows[0]["cells"]))
        self.assertEqual(support["status_panels"]["original65"]["1"],48);self.assertNotIn(0,support["train"])
        m["rows"][0]["original_cohort"]=False
        with self.assertRaises(ValueError):auditor._manifest(m)

    def test_unknown_mixed_groups_and_new_cohort_implication(self):
        m=copy.deepcopy(self.manifest);m["rows"][65]["cohort"]=False
        with self.assertRaises(ValueError):auditor._manifest(m)
        m=copy.deepcopy(self.manifest);m["rows"][65].update(group=-1,operational_eligible=False,cohort=False)
        _,support=auditor._manifest(m);self.assertEqual(support["counts"]["unknown_groups"],2)
        m["rows"][65]["operational_eligible"]=True
        with self.assertRaises(ValueError):auditor._manifest(m)
        m=copy.deepcopy(self.manifest);m["rows"][65].update(group=41,cohort=False,operational_eligible=False)
        with self.assertRaises(ValueError):auditor._manifest(m)
        m["rows"][41].update(cohort=False,operational_eligible=False)
        _,support=auditor._manifest(m);self.assertNotIn(41,support["dev"]);self.assertNotIn(65,support["train"])

    def test_bulk_guard_shapes_order_exact_bools_before_scoring(self):
        for mutate in (lambda g:g.update(pass_all=1),lambda g:g["checks"].pop(),lambda g:g["checks"].reverse(),
                       lambda g:g["checks"][0].update(horizon=True),lambda g:g["checks"][0].update(mae_not_worse=1)):
            r=copy.deepcopy(self.result);mutate(r["bulk_guard"])
            with patch.object(auditor,"score",side_effect=AssertionError("score")):
                self.assertEqual(auditor.audit(r,self.manifest)["status"],"fail")

    def test_original_and_bulk_stored_flags_are_recomputed(self):
        r=copy.deepcopy(self.result);r["original_advance"]=True;r["bulk_guard"]["pass_all"]=False
        r["bulk_guard"]["checks"][5]["medae_not_worse"]=False;r["advance"]=True
        out=auditor.audit(r,self.manifest)
        self.assertEqual(set(out["reasons"]),{"stored_original_advance","stored_bulk_guard","stored_advance"})
        self.assertFalse(out["original_advance"]);self.assertTrue(out["bulk_guard"]["pass_all"]);self.assertFalse(out["advance"])

    def test_bulk_guard_every_seed_horizon_and_equality(self):
        fits=[]
        for seed in auditor.SEEDS:
            for arm in auditor.ARMS:
                m=dict(mae=.3,medae=.25)
                fits.append(dict(seed=seed,arm=arm,status="complete",metrics={str(h):dict(m) for h in (1,3,5)}))
        guard=auditor.bulk_guard(fits);self.assertTrue(guard["pass_all"])
        self.assertEqual([(c["seed"],c["horizon"])for c in guard["checks"]],[(s,h)for s in auditor.SEEDS for h in (1,3,5)])
        for seed_index in (0,3):
            for h in (1,3,5):
                for k in ("mae","medae"):
                    bad=copy.deepcopy(fits);bad[seed_index]["metrics"][str(h)][k]+=.001
                    self.assertFalse(auditor.bulk_guard(bad)["pass_all"])

    def test_injected_history_float_seed_key_cannot_equal_integer_key(self):
        histories={(float(f["seed"]),f["arm"]):copy.deepcopy(f["history"]) for f in self.result["fits"]}
        with patch.object(auditor,"score",side_effect=AssertionError("score")):
            self.assertEqual(auditor.audit(self.result,self.manifest,histories)["status"],"fail")
