"""Invented score references, TRAIN isolation and frozen pilot gates; no fits."""
import copy
import math
import unittest
from unittest.mock import patch
import numpy as np
import density
import artifact
import pilot
import invented


class DensityTests(unittest.TestCase):
    def test_single_normal_references(self):
        p=[.2]*5;m=[0.]*5;s=[1.]*5
        self.assertAlmostEqual(density.nll(0,p,m,s),.5*math.log(2*math.pi),places=12)
        self.assertAlmostEqual(density.crps(0,p,m,s),(math.sqrt(2)-1)/math.sqrt(math.pi),places=12)
        self.assertEqual(density.quantile(.5,p,m,s),0)
        self.assertAlmostEqual(density.quantile(.975,p,m,s),1.95996398454005,places=10)

    def test_mixture_crps_independent_cdf_integral(self):
        p=[.1,.2,.3,.15,.25];m=[-2,-1,0,2,3];s=[.4,.5,1,2,.2];y=.75
        x=np.linspace(-30,30,120001);cdf=np.array([density.cdf(v,p,m,s) for v in x]);z=(cdf-(x>=y))**2
        reference=np.trapezoid(z,x)
        self.assertAlmostEqual(density.crps(y,p,m,s),reference,delta=.0003)
        self.assertGreater(density.crps(y,p,m,s),0)
        self.assertAlmostEqual(density.cdf(100,p,m,s),1)
        self.assertAlmostEqual(density.mean_action(p,m),.65)

    def test_extreme_tail_nll_is_stable(self):
        self.assertTrue(math.isfinite(density.nll(100,[1,0,0,0,0],[0]*5,[.05]*5)))
        for p,m,s in (([.1]*5,[0]*5,[1]*5),([.2]*5,[0]*5,[0]*5),([.2]*5,[float("nan")]*5,[1]*5)):
            with self.assertRaises(ValueError):density.nll(0,p,m,s)


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.arrays,cls.manifest=invented.build_fixture()[3:]

    def test_gate_fixed_counts_groups_and_no_fit_failure(self):
        gate=pilot.gate(self.manifest)
        self.assertEqual(gate["status"],"pass")
        self.assertEqual((gate["counts"]["train"],gate["counts"]["dev"]),(41,20))
        bad=copy.deepcopy(self.manifest)
        for row in bad["rows"]:
            row["cohort"]=False
            row["cells"]=[artifact._empty_cell(h,"qualification_unknown",[]) for h in (1,3,5)]
        callback=lambda *a:self.fail("checkpoint/fit")
        result=pilot.run(self.arrays,bad,callback)
        self.assertEqual(result["status"],"gate_failed");self.assertEqual(result["fits"],[])

    def test_original_manifest_not_success_denominator(self):
        m=copy.deepcopy(self.manifest);m["rows"].pop()
        with self.assertRaises(ValueError):pilot.gate(m)
        m=copy.deepcopy(self.manifest);m["rows"][0]["cohort"]=False
        with self.assertRaises(ValueError):pilot.gate(m)

    def test_train_only_scaler_dev_mutation_and_flags(self):
        rng=np.random.default_rng(12);ctx=rng.normal(size=(65,3,29));ctx[:,:,9]=1
        train=list(range(41));a,mean,std=pilot.standardize(ctx,train)
        changed=ctx.copy();changed[41:,:,:]=1e9;b,m,s=pilot.standardize(changed,train)
        np.testing.assert_array_equal(a[:41],b[:41]);np.testing.assert_array_equal(mean,m);np.testing.assert_array_equal(std,s)
        np.testing.assert_array_equal(a[:,:,9],ctx[:,:,9])
        for col in pilot.CONTINUOUS:
            self.assertAlmostEqual(a[train,:,col].mean(),0,places=12)
            self.assertAlmostEqual(a[train,:,col].std(),1,places=12)
        zero=np.zeros((65,3,29));self.assertFalse(pilot.standardize(zero,train)[0].any())

    def test_permutation_whole_event_and_uniform_order_replay(self):
        train=list(range(41));perm=pilot.permutation(train)
        self.assertEqual(set(perm),set(train));self.assertFalse(np.array_equal(perm,train))
        a=list(pilot.event_order(train,pilot.SEEDS[0]));b=list(pilot.event_order(train,pilot.SEEDS[0]))
        self.assertEqual(len(a),300)
        for x,y in zip(a,b):np.testing.assert_array_equal(x,y);self.assertEqual(len(set(x)),8);self.assertTrue(set(x)<=set(train))

    def test_descriptive_metrics_fixed_tail_and_cvar(self):
        p=[]
        for i,(y,e) in enumerate(((4,0),(6,1),(7,3),(4,2))):
            pi=[.2]*5;mu=[y+e]*5;s=[1.]*5
            p.append(dict(ordinal=i,target=y,mean=y+e,median=y+e,pi=pi,mu=mu,sigma=s,nll=density.nll(y,pi,mu,s),crps=density.crps(y,pi,mu,s)))
        m=pilot.metrics(p)
        self.assertEqual(m["mae"],1.5);self.assertEqual(m["tail_mae_5_5"],2);self.assertEqual(m["cvar95"],3);self.assertEqual(m["lower_medae"],1)
        interval=pilot.paired_intervals(p,p,[0,0,1,1])
        self.assertEqual(interval["nll"]["status"],"unsupported")
        interval=pilot.paired_intervals(p,p,[0,1,2,3]);self.assertEqual(interval["nll"]["interval"],[0,0])

    def test_advance_all_seeds_all_h_strict_guards(self):
        base=dict(nll=2.,crps=2.,tail_mae_5_5=.5,lower_mae=.2,lower_medae=.2,cvar95=.9,maximum=1.)
        fits=[]
        for seed in pilot.SEEDS:
            for arm in pilot.ARMS:
                m=dict(base)
                if arm=="W":m.update(nll=1.,crps=1.,tail_mae_5_5=.47)
                fits.append(dict(seed=seed,arm=arm,status="complete",metrics={str(h):dict(m) for h in pilot.HORIZONS}))
        self.assertTrue(pilot.advance(fits))
        for field,value in (("nll",2.),("tail_mae_5_5",.49),("maximum",1.01),("lower_mae",.21)):
            bad=copy.deepcopy(fits);bad[3]["metrics"]["5"][field]=value
            self.assertFalse(pilot.advance(bad))
        self.assertFalse(pilot.advance(fits[:-1]))

    def test_rate_strata_retain_exact_rates_and_small_denominators(self):
        p=[]
        for i in range(4):
            p.append(dict(ordinal=i,target=6.,mean=6.,median=6.,pi=[.2]*5,mu=[6.]*5,sigma=[1.]*5,nll=1.,crps=.2,rate=[100,1] if i<3 else [3,2]))
        strata=pilot.rate_strata(p,list(range(65)))
        self.assertEqual(sum(r["n"] for r in strata),4)
        by={tuple(r["rate"]):r for r in strata}
        self.assertEqual(by[(100,1)]["status"],"descriptive")
        self.assertEqual(by[(3,2)]["status"],"unsupported")
        self.assertEqual(by[(3,2)]["metrics"]["n"],1)
