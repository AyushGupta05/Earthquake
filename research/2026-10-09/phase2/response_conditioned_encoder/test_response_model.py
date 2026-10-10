"""CPU tests only, invented data, no real arrays or training job."""
import unittest
import numpy as np
import torch
from response_model import ResponseConditionedModel,identity_normalizers,GAIN_INDICES
from response_data import gain_reexpression
from synthetic_shared_fixture import fixture


def batch(seconds=1):
    raw,rows,e,p=fixture()
    out={'counts':np.array([raw['data'][r['trace_name']][:,200:200+100*seconds] for r in rows[:3]]),
         'sensitivity':e['sensitivities'][:3],
         'static':np.array([p(r)[0] for r in rows[:3]]),'response':np.array([p(r)[3] for r in rows[:3]])}
    return {k:torch.tensor(v,dtype=torch.float32) for k,v in out.items()}


def model(arm):
    torch.manual_seed(20261009)
    return ResponseConditionedModel(arm,identity_normalizers())


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(2);torch.use_deterministic_algorithms(True)

    def test_equal_capacity_and_state_initialization(self):
        models=[model(arm) for arm in 'ABCD']
        self.assertEqual([m.parameter_count() for m in models],[380706]*4)
        for m in models[1:]:
            for name,value in models[0].state_dict().items():self.assertTrue(torch.equal(value,m.state_dict()[name]),name)

    def test_exact_native_early_late_neutral_forward_and_backbone_gradient(self):
        for seconds in (1,3,5):
            b,c=model('B'),model('C');x=batch(seconds)
            yb,yc=b.forward_prefix(x,seconds),c.forward_prefix(x,seconds)
            self.assertTrue(torch.equal(yb,yc));self.assertEqual(yb.shape,(3,66))
            yb.square().sum().backward();yc.square().sum().backward()
            for (name,p),(_,q) in zip(b.named_parameters(),c.named_parameters()):
                if not name.startswith('conditioner.'):
                    self.assertTrue(torch.equal(p.grad,q.grad),name)

    def test_conditioning_placement_has_nonredundant_effect_after_modulation(self):
        b,c=model('B'),model('C')
        with torch.no_grad():
            b.conditioner[-1].bias.fill_(.3);c.conditioner[-1].bias.fill_(.3)
        self.assertGreater(float((b(batch(1),1)-c(batch(1),1)).abs().max().detach()),1e-6)

    def test_prefix_only_and_unread_labels(self):
        m=model('B');x=batch(5)
        prefix={**x,'counts':x['counts'][:,:,:100].clone()}
        y=m(prefix,1)
        x['counts'][:,:,100:]=float('nan')
        again={**x,'counts':x['counts'][:,:,:100].clone(),'targets':object(),'event_ids':object()}
        self.assertTrue(torch.equal(y,m(again,1)))
        with self.assertRaises(ValueError):m(x,1)
        with self.assertRaises(ValueError):m(x,5)

    def test_masks_gain_and_shape_fail_closed(self):
        m=model('B')
        x=batch();x['response'][0,3]=.5
        with self.assertRaises(ValueError):m(x,1)
        x=batch();x['response'][0,20]=1 # first record E16Hz is masked
        with self.assertRaises(ValueError):m(x,1)
        x=batch();x['sensitivity'][0,0]*=2
        with self.assertRaises(ValueError):m(x,1)
        x=batch();x['static']=x['static'][:,:33]
        with self.assertRaises(ValueError):m(x,1)

    def test_native_amplitudes_do_not_mean_whole_model_gain_invariance(self):
        x=batch();arrays={k:v.numpy() for k,v in x.items()}
        xx,gg,ss=gain_reexpression(arrays['counts'],arrays['sensitivity'],arrays['static'],np.arange(3),20261009,1)
        changed={k:torch.tensor(v,dtype=torch.float32) for k,v in dict(arrays,counts=xx,sensitivity=gg,static=ss).items()}
        # The full late metadata intentionally retains absolute gain.
        self.assertGreater(float((model('B')(x,1)-model('B')(changed,1)).abs().max().detach()),1e-8)

    def test_checkpoint_roundtrip_and_finite_one_step(self):
        m=model('C');x=batch();opt=torch.optim.AdamW(m.parameters(),lr=3e-4)
        loss=m(x,1).square().mean();loss.backward();torch.nn.utils.clip_grad_norm_(m.parameters(),5);opt.step()
        self.assertTrue(all(torch.isfinite(p).all() for p in m.parameters()))
        fresh=model('C');fresh.load_state_dict(m.state_dict())
        self.assertTrue(torch.equal(m(x,1),fresh(x,1)))


if __name__=='__main__':unittest.main()
