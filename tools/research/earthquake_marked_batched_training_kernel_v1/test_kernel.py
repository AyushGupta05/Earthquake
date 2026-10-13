import ast
import math
import time
import unittest
import numpy as np
import torch
import kernel as k
import scalar_reference as ref


torch.set_num_threads(1)
D = torch.float64


def fixture(batch=24, spread=1., coeff_scale=1.):
    generator = torch.Generator().manual_seed(1234)
    horizons = tuple((1, 3, 5)[i % 3] for i in range(batch))
    offsets = tuple((i % 4)*250000000 for i in range(batch))
    marks = tuple(torch.randn((h*1000000000-o)//250000000, 3, generator=generator, dtype=D)*.2+1 for h, o in zip(horizons, offsets))
    nu = torch.randn(batch, 12, 3, generator=generator, dtype=D)*.1
    logw = torch.log_softmax(torch.randn(batch, 5, generator=generator, dtype=D), 1).detach().requires_grad_()
    mu = (torch.randn(batch, 5, generator=generator, dtype=D)*spread+6).requires_grad_()
    sigma = (torch.rand(batch, 5, generator=generator, dtype=D)*spread+.05).requires_grad_()
    coeff = torch.tensor([[.4,.15,.1,.01,.2,-.3]]*3, dtype=D).mul(coeff_scale).requires_grad_()
    target = torch.randn(batch, generator=generator, dtype=D)*.2+6
    return (logw, mu, sigma), marks, coeff, nu, target, horizons, offsets


def batched(f, arm):
    p, m, c, n, y, h, o = f
    return k.marked_nll(p, m, c, n, y, arm, 6., h, o, processing_begin=time.monotonic())


def scalars(f, arm):
    p, m, c, n, y, h, o = f
    posterior = [ref.forecast(tuple(x[i] for x in p), m[i], c, n[i], arm, 6., h[i], o[i], processing_begin=time.monotonic()) for i in range(len(y))]
    return dict(nll=torch.stack([x.nll(y[i]) for i,x in enumerate(posterior)]), logz=torch.stack([x.logz for x in posterior]), logw=torch.stack([x.logw for x in posterior]), mu=torch.stack([x.mu for x in posterior]), sigma=torch.stack([x.sigma for x in posterior]))


class Tests(unittest.TestCase):
    def parity(self, arm, **kwargs):
        f = fixture(**kwargs)
        actual = batched(f, arm); expected = scalars(f, arm)
        for name in ('nll','logz','logw','mu','sigma'):
            torch.testing.assert_close(actual[name], expected[name], rtol=1e-9, atol=1e-9)
        params = list(f[0])+[f[2]]
        a = torch.autograd.grad(actual['nll'].mean(), params, retain_graph=True)
        b = torch.autograd.grad(expected['nll'].mean(), params)
        for x,y in zip(a,b):
            torch.testing.assert_close(x,y,rtol=1e-9,atol=1e-9)
        width = 60 if arm == 'S' else 5
        self.assertEqual(actual['density_points'], tuple((len(m)*3+1)*width for m in f[1]))

    def test_s_ragged_gradient(self): self.parity('S')
    def test_p_ragged_gradient(self): self.parity('P')
    def test_s_narrow(self): self.parity('S', spread=.0001, coeff_scale=8.)
    def test_p_broad(self): self.parity('P', spread=30., coeff_scale=.02)
    def test_one_row(self): self.parity('S', batch=1)

    def test_ulp_exact(self):
        values = np.array([0.,-0.,np.nextafter(0.,1.),-np.nextafter(0.,1.),1.,-1.,2.,-2.,.5,-.5,1e6,1e-100,np.finfo(float).max,np.finfo(float).tiny])
        np.testing.assert_array_equal(k.ulp(values),[math.ulp(float(x)) for x in values])

    def test_d_parity(self):
        p,m,c,n,y,h,o = fixture()
        summary = torch.stack([ref.summaries(x,n[i]) for i,x in enumerate(m)])
        mean,std,active = ref.summary_scaler(summary.repeat(9,1)[:195])
        value = torch.stack([ref.standardized_summary(x,mean,std) for x in summary])
        theta = torch.linspace(-.03,.03,len(active),dtype=D).requires_grad_(); tau=torch.tensor(.2,dtype=D,requires_grad=True)
        a=k.direct_nll(p,value,theta,tau,active,y,processing_begin=time.monotonic())
        expected=[ref.direct(tuple(x[i] for x in p),value[i],theta,tau,active,processing_begin=time.monotonic()) for i in range(24)]
        b=torch.stack([x.nll(y[i]) for i,x in enumerate(expected)])
        torch.testing.assert_close(a['nll'],b,rtol=1e-9,atol=1e-9)
        params=list(p)+[theta,tau]
        ag=torch.autograd.grad(k.loss24(a['nll']),params,retain_graph=True)
        bg=torch.autograd.grad(sum(x/24 for x in b),params)
        for x,z in zip(ag,bg):torch.testing.assert_close(x,z,rtol=1e-9,atol=1e-9)
        torch.testing.assert_close(a['logw'],p[0],rtol=0,atol=0)
        self.assertTrue(bool((a['logz']==0).all()))

    def test_prior_network_gradient_k0_and30(self):
        for dim in (0,30):
            net=ref.Prior(dim);net.initialize(6.,.8)
            ctx=torch.randn(8,dim,dtype=D)
            f=fixture()
            priors=[net(x) for x in ctx]
            p=tuple(torch.stack([priors[i//3][j] for i in range(24)]) for j in range(3))
            f=(p,)+f[1:]
            a=batched(f,'S')['nll']; b=scalars(f,'S')['nll']
            ag=torch.autograd.grad(k.loss24(a),tuple(net.parameters()),retain_graph=True)
            bg=torch.autograd.grad(sum(x/24 for x in b),tuple(net.parameters()))
            for x,y in zip(ag,bg):torch.testing.assert_close(x,y,rtol=1e-9,atol=1e-9)

    def test_joint_support_permutation(self):
        f=fixture();p,m,c,n,y,h,o=f
        a=batched(f,'S')['nll']
        b=batched((p,m,c,n[:,torch.arange(11,-1,-1)],y,h,o),'S')['nll']
        torch.testing.assert_close(a,b,rtol=1e-9,atol=1e-9)
        unrelated=n.clone();unrelated[:,:,1]=n[:,torch.arange(11,-1,-1),1]
        self.assertGreater(float((a-batched((p,m,c,unrelated,y,h,o),'S')['nll']).detach().abs().max()),1e-7)

    def test_clock_future_and_censor_rejected(self):
        f=list(fixture());f[1]=(torch.cat((f[1][0],f[1][0][:1])),)+f[1][1:]
        with self.assertRaisesRegex(ValueError,'tensor'):batched(tuple(f),'S')
        f=list(fixture());bad=f[1][0].clone();bad[0,0]=-12;f[1]=(bad,)+f[1][1:]
        with self.assertRaisesRegex(ValueError,'allpositive'):batched(tuple(f),'S')

    def test_deadline(self):
        f=fixture();p,m,c,n,y,h,o=f
        with self.assertRaisesRegex(ValueError,'deadline'):k.marked_nll(p,m,c,n,y,'S',6.,h,o,processing_begin=time.monotonic()-11)

    def test_dtype_prior_and_target(self):
        f=list(fixture());f[4]=f[4].float()
        with self.assertRaisesRegex(ValueError,'tensor'):batched(tuple(f),'S')
        f=list(fixture());f[0]=(f[0][0]+.1,)+f[0][1:]
        with self.assertRaisesRegex(ValueError,'proper_prior'):batched(tuple(f),'S')

    def test_precision_rejection_both(self):
        f=list(fixture());f[4]=torch.full((24,),1e9,dtype=D)
        for call in (batched,scalars):
            with self.assertRaisesRegex(ValueError,'target_precision'):call(tuple(f),'S')

    def test_capacity_and_loss_denominator(self):
        with self.assertRaises(ValueError):k.loss24(torch.ones(23,dtype=D))
        p,m,c,n,y,h,o=fixture()
        with self.assertRaisesRegex(ValueError,'capacity_schema'):k.direct_nll(p,torch.zeros(24,20,dtype=D),torch.zeros(1,dtype=D),torch.tensor(0.,dtype=D),(4,),y,processing_begin=time.monotonic())

    def test_original_separate_backward_order(self):
        f=fixture(); params=list(f[0])+[f[2]]
        p,m,c,n,y,h,o=f
        for i in range(24):
            posterior=ref.forecast(tuple(x[i] for x in p),m[i],c,n[i],'S',6.,h[i],o[i],processing_begin=time.monotonic())
            (posterior.nll(y[i])/24).backward()
        original=[x.grad.clone() for x in params]
        for x in params:x.grad=None
        k.loss24(batched(f,'S')['nll']).backward()
        for x,y in zip(params,original):torch.testing.assert_close(x.grad,y,rtol=1e-9,atol=1e-9)

    def test_mean_precision_rejection_both(self):
        p,m,c,n,y,h,o=fixture(batch=1)
        p=(p[0],torch.full_like(p[1],1000.),torch.full_like(p[2],.05))
        c=torch.tensor([[-1e6,1000.,0.,0.,0.,-40.]]*3,dtype=D)
        with self.assertRaisesRegex(ValueError,'gaussian_mean_precision'):
            k.marked_nll(p,m,c,n*0,y,'S',0.,h,o,processing_begin=time.monotonic())
        with self.assertRaisesRegex(ValueError,'gaussian_mean_precision'):
            ref.forecast(tuple(x[0] for x in p),m[0],c,n[0]*0,'S',0.,h[0],o[0],processing_begin=time.monotonic())

    def test_python39(self):
        from pathlib import Path
        for p in Path('.').glob('*.py'):ast.parse(p.read_text(),feature_version=(3,9))


if __name__=='__main__':unittest.main()
