"""Invented failure retention only; no optimizer, data, actual fit or IO."""
import unittest
import numpy as np
import torch
import pilot


class FakeNet:
    def state_dict(self):return {'weight':torch.tensor([1.,2.])}


class FailureCheckpointTests(unittest.TestCase):
    def test_early_failure_current_state_and_scalers_retained_once(self):
        calls=[];stats={'initial_mean':np.zeros(35)}
        def checkpoint(seed,arm,state,scalers):calls.append((seed,arm,state,scalers))
        r=pilot.retain_failure_checkpoint(checkpoint,20261012,'C',FakeNet(),stats,False,False)
        self.assertEqual(r,{'status':'saved_failed_fit'});self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][:2],(20261012,'C'));np.testing.assert_array_equal(calls[0][2]['weight'],[1.,2.]);self.assertIs(calls[0][3],stats)
    def test_already_saved_or_attempted_never_overwritten_or_retried(self):
        def forbidden(*_):self.fail('duplicate checkpoint')
        self.assertEqual(pilot.retain_failure_checkpoint(forbidden,1,'T',FakeNet(),{},True,True)['status'],'already_saved_final')
        self.assertEqual(pilot.retain_failure_checkpoint(forbidden,1,'T',FakeNet(),{},True,False)['status'],'checkpoint_callback_failed')
    def test_before_model_and_callback_error_explicit_incomplete_diagnostics(self):
        self.assertEqual(pilot.retain_failure_checkpoint(lambda *_:self.fail('no model'),1,'H',None,{},False,False)['status'],'unavailable_before_model')
        def failing(*_):raise OSError('invented failure')
        r=pilot.retain_failure_checkpoint(failing,1,'H',FakeNet(),{},False,False)
        self.assertEqual(r,{'status':'checkpoint_callback_failed','exception_type':'OSError'})


if __name__=='__main__':unittest.main()
