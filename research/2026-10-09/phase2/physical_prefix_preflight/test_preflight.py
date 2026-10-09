import json
import math
from pathlib import Path
import unittest

import numpy as np

import preflight as p


class PrefixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings = json.loads(Path('protocol.json').read_text())

    def test_protocol_is_prespecified(self):
        self.assertEqual(p.sha256('protocol.json'),p.PROTOCOL_SHA256)

    def test_identical_prefix_different_final_moment(self):
        for seconds in (1,3,5):
            n = int(seconds*20)
            durations = np.array([2*seconds+1,4*seconds+2,8*seconds+4])
            history = p.source_history(durations,20,n)
            np.testing.assert_array_equal(history, np.repeat(history[:,:1],3,axis=1))
            moments = durations**3/12
            self.assertTrue(np.all(np.diff(moments)>0))

    def test_completed_and_postpeak_histories_are_informative(self):
        history = p.source_history([.4,1.5,7.,20.],20,100)
        self.assertTrue(np.all(history[9:,0] == 0))
        self.assertLess(history[99,2],history[70,2])
        self.assertGreater(np.max(np.abs(history[:,2]-history[:,3])),0)

    def test_future_values_cannot_change_any_observed_operator(self):
        rng = np.random.default_rng(4)
        x = rng.normal(size=(160,3)); altered = x.copy(); altered[60:] += 1e8
        for sensor in self.settings['sensor_models']:
            y = p.sensor_transform(p.lowpass(x,.12,20),sensor,20)
            changed = p.sensor_transform(p.lowpass(altered,.12,20),sensor,20)
            np.testing.assert_array_equal(y[:60],changed[:60])
            np.testing.assert_array_equal(y[:60],p.sensor_transform(p.lowpass(x[:60],.12,20),sensor,20))
            matrix = p.noise_operator(100,sensor,self.settings)
            np.testing.assert_array_equal(matrix,np.tril(matrix))
            np.testing.assert_array_equal(matrix[:60,:60],p.noise_operator(60,sensor,self.settings))

    def test_basis_orthonormal_and_covariance_positive(self):
        for n in (20,60,100):
            basis = p.spectral_basis(n,4)
            np.testing.assert_allclose(p.product(basis,basis.T),np.eye(9),atol=1e-14)
            for sensor in self.settings['sensor_models']:
                covariance = p.projected_covariance(n,basis,sensor,self.settings)
                self.assertGreater(np.linalg.eigvalsh(covariance).min(),0)
                # Every hypothesis shares this same covariance, not a final-M scale.
                copies = np.repeat(covariance[None],9,axis=0)
                for cov in copies:np.testing.assert_array_equal(cov,covariance)

    def test_gaussian_includes_determinant_and_matches_2d_formula(self):
        y = np.array([[1.,2.],[-.4,.5]])
        mean = np.array([[.5,-1.]])
        cov = np.array([[2.,.3],[.3,.7]])
        det = 2*.7-.3**2
        inverse = np.array([[.7,-.3],[-.3,2.]])/det
        d = y-mean
        expected = -.5*(np.einsum('bi,ij,bj->b',d,inverse,d)+math.log(det)+2*math.log(2*math.pi))
        np.testing.assert_allclose(p.gaussian_logpdf(y,mean,cov)[:,0],expected,atol=1e-14)
        small = p.gaussian_logpdf(np.zeros((1,2)),np.zeros((1,2)),np.eye(2))[0,0]
        large = p.gaussian_logpdf(np.zeros((1,2)),np.zeros((1,2)),4*np.eye(2))[0,0]
        self.assertAlmostEqual(large-small,-math.log(4))

    def test_bad_covariance_is_not_silently_repaired(self):
        for cov in (np.zeros((2,2)),np.array([[1,2],[2,1]]),np.array([[1,0],[1,1]])):
            with self.assertRaises((ValueError,np.linalg.LinAlgError)):
                p.gaussian_logpdf(np.zeros((1,2)),np.zeros((1,2)),cov)

    def test_gain_marginalization_matches_manual_density(self):
        y=np.array([[.4],[2.]])
        template=np.array([[.2],[1.]])
        gains=np.array([.7,1.4]); gp=np.array([.25,.75]); prior=np.array([.6,.4])
        likelihood,log_p=p.likelihood_and_posterior(y,template,np.array([[.5]]),gains,gp,prior)
        expected=np.zeros((2,2))
        for i in range(2):
            for j in range(2):
                expected[i,j]=sum(w*math.exp(-((y[i,0]-g*template[j,0])**2)/(2*.5))/math.sqrt(2*math.pi*.5) for g,w in zip(gains,gp))
        np.testing.assert_allclose(np.exp(likelihood),expected,atol=1e-14)
        expected*=prior
        expected/=expected.sum(1,keepdims=True)
        np.testing.assert_allclose(np.exp(log_p),expected,atol=1e-14)

    def test_sensor_gain_rescaling_preserves_posterior_and_density_jacobian(self):
        rng=np.random.default_rng(8)
        y=rng.normal(size=(5,9)); templates=rng.normal(size=(3,9))
        a=rng.normal(size=(9,9));cov=p.product(a,a.T)+np.eye(9)
        gains=np.array([.7,1,1.4]);gp=np.array([.25,.5,.25]);prior=np.array([.2,.3,.5])
        l0,p0=p.likelihood_and_posterior(y,templates,cov,gains,gp,prior)
        for scale in (.01,100.):
            l1,p1=p.likelihood_and_posterior(scale*y,scale*templates,scale**2*cov,gains,gp,prior)
            np.testing.assert_allclose(p1,p0,atol=1e-11,rtol=0)
            np.testing.assert_allclose(l1-l0,-9*np.log(scale),atol=1e-10,rtol=0)

    def test_null_posterior_is_prior_and_complete_template_fails(self):
        s=self.settings;fs=s['sample_rate_hz'];n=100;durations=np.array([12.,20.,40.])
        source=p.lowpass(p.source_history(durations,fs,810),s['path_lowpass_tau_seconds'],fs)
        basis=p.spectral_basis(n,4);prior=np.array([.7,.2,.1])
        for sensor in s['sensor_models']:
            signal=p.sensor_transform(source,sensor,fs)
            prefix=p.product(basis,signal[:n]).T
            complete=p.product(p.spectral_basis(n,4,810),signal).T
            cov=p.projected_covariance(n,basis,sensor,s)
            for c in (cov,np.diag(np.diag(cov))):
                ll,lp=p.likelihood_and_posterior(prefix[:1],prefix,c,np.array([1.]),np.array([1.]),prior)
                np.testing.assert_array_equal(ll,np.repeat(ll[:,:1],3,axis=1))
                np.testing.assert_allclose(np.exp(lp),prior[None,:],atol=1e-12,rtol=0)
                bad,_=p.likelihood_and_posterior(prefix[:1],complete,c,np.array([1.]),np.array([1.]),prior)
                self.assertGreater(np.max(np.abs(bad-bad[:,:1])),1.)

    def test_product_matches_independent_fsum(self):
        rng=np.random.default_rng(91)
        a=rng.normal(size=(9,20));b=rng.normal(size=(20,7))
        expected=np.array([[math.fsum(float(a[i,k])*float(b[k,j]) for k in range(20)) for j in range(7)] for i in range(9)])
        np.testing.assert_allclose(p.product(a,b),expected,rtol=0,atol=1e-14)

    def test_large_common_log_likelihood_stays_normalized(self):
        _,logp=p.likelihood_and_posterior(np.array([[1e5,0.]]),np.array([[0.,0.],[0.,0.]]),np.eye(2),np.array([1.]),np.array([1.]),np.array([.5,.5]))
        np.testing.assert_allclose(np.exp(logp),[[.5,.5]],rtol=0,atol=1e-14)

    def test_projected_covariance_matches_combined_innovation_operator(self):
        n=20;b=p.spectral_basis(n,4);s=self.settings
        for sensor in s['sensor_models']:
            operator=p.noise_operator(n,sensor,s)
            combined=np.concatenate([s['physical_noise_innovation_sd']*p.product(b,operator),s['count_noise_sd']*b],axis=1)
            expected=p.product(combined,combined.T)
            np.testing.assert_allclose(p.projected_covariance(n,b,sensor,s),expected,atol=1e-14,rtol=0)

    def test_scores_pointmass_and_fractional_cvar(self):
        logp=np.array([[0.,-1000.],[-1000.,0.]])
        result=p.scores(logp,np.array([4.,6.]),np.array([0,1]),np.ones(2))
        for key in ('categorical_nll','crps','mean_mae','median_mae'):
            self.assertAlmostEqual(result[key],0.)
        self.assertEqual(result['interval90_coverage'],1.)
        self.assertEqual(p.weighted_cvar(np.array([10.,2.]),np.array([.02,.98])),5.2)


if __name__ == '__main__':unittest.main()
