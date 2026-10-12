"""Invented complete fixture, independent normal references and invalid bindings."""
import copy
import math
import unittest
from unittest.mock import patch
import numpy as np
import auditor


def fixture():
    rows=[];common=set(range(30))|set(range(41,59));mw=lambda i:6. if i%2==0 else 4.
    for i in range(65):
        cells=[]
        for h in (1,3,5):
            good=i in common
            cells.append(dict(horizon=h,status="available" if good else "unavailable",reason="supported" if good else "operational_ineligible",
                              array="wave_%02d_%d"%(i,h) if good else None,shape=[3,100*(h+3)] if good else None,first=[1704067200000000000,1] if good else None,
                              period=[10000000,1] if good else None,precontext_count=300 if good else None,channels=["HHE","HHN","HHZ"],view_sha256=["0"*64]*3 if good else None))
        rows.append(dict(ordinal=i,partition="TRAIN" if i<41 else "DEV",group=i,mw=mw(i),cohort=i in common,cells=cells))
    manifest=dict(schema="earthquake-native-count-artifact-v1",study=auditor.STUDY,rows=rows,denominators=dict(rows=65,cells=195,train=41,dev=24,test_excluded=31))
    # Independent scalar standard-normal formula, no auditor score call.
    z=1.;cdf=.5*(1+math.erf(z/math.sqrt(2)));phi=math.exp(-.5*z*z)/math.sqrt(2*math.pi)
    nll=.5*math.log(2*math.pi)+.5;crps=z*(2*cdf-1)+2*phi-1/math.sqrt(math.pi)
    metric=dict(n=18,nll=nll,crps=crps,mae=1.,medae=1.,tail_mae_5_5=1.,tail_mae_6=1.,tail_bias=-1.,lower_mae=1.,lower_medae=1.,cvar95=1.,p95=1.,maximum=1.,median_mae=1.,coverage_50=0.,coverage_90=1.,coverage_95=1.)
    train=list(range(30));dev=list(range(41,59))
    support=dict(status="pass",counts=dict(train=30,dev=18,train_high=15,dev_high=9,train_lower=15,dev_lower=9,dev_high_groups=9),train=train,dev=dev)
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
    return dict(status="complete",support=support,fits=fits,advance=False,comparisons=comparisons),manifest


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
        out=auditor.paired(preds,preds,list(range(65)))
        self.assertEqual(out["nll"]["status"],"unsupported")
        mixed=copy.deepcopy(self.replay["fits"][0]["predictions"][:6]);mixed[0]["rate"]=[3,2]
        strata=auditor.rate_strata(mixed,list(range(65)))
        self.assertEqual(sum(s["n"] for s in strata),6)
        self.assertEqual({tuple(s["rate"]) for s in strata},{(3,2),(100,1)})

    def test_strict_advance_all_seed_horizon_guards(self):
        fits=[]
        for seed in auditor.SEEDS:
            for arm in auditor.ARMS:
                m=dict(nll=2.,crps=2.,tail_mae_5_5=.5,lower_mae=.2,lower_medae=.2,cvar95=.9,maximum=1.)
                if arm=="W":m.update(nll=1.,crps=1.,tail_mae_5_5=.47)
                fits.append(dict(seed=seed,arm=arm,status="complete",metrics={str(h):dict(m) for h in (1,3,5)}))
        self.assertTrue(auditor.advance(fits))
        for name,value in (("nll",2.),("tail_mae_5_5",.49),("maximum",1.01),("lower_mae",.21)):
            bad=copy.deepcopy(fits);bad[3]["metrics"]["5"][name]=value;self.assertFalse(auditor.advance(bad))
        self.assertFalse(auditor.advance(fits[:-1]))
        bad=copy.deepcopy(fits);bad[0]["status"]="incomplete";self.assertFalse(auditor.advance(bad))

    def test_output_admission_cannot_promote(self):
        with patch.object(auditor,"MAX_OUTPUT",1):
            replay=auditor.audit(self.result,self.manifest)
        self.assertEqual(replay["status"],"fail");self.assertEqual(replay["fits"],[])
