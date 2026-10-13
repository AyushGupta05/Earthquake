"""Invented result-retention boundaries; no training, optimizer, data or IO."""
import unittest
from unittest.mock import patch
import pilot


class FinalizationTests(unittest.TestCase):
    def invoke(self,canonical,tick=lambda *_:None):
        fits=[{'seed':1,'arm':'C','metrics':{},'predictions':[{'invented':True}]}]
        comparisons=[{'retained':True}];capacity={'invented':1}
        with patch.object(pilot,'diagnostics',return_value={'retained':True}),patch.object(pilot,'advance',return_value={'pass_all':True,'checks':[]}),patch.object(pilot.observations,'canonical',side_effect=canonical),patch.object(pilot,'deadline',side_effect=tick):
            result=pilot.finalize_result({},fits,capacity,comparisons,0.)
        self.assertIs(result['fits'],fits);self.assertIs(result['comparisons'],comparisons);self.assertIs(result['capacity'],capacity)
        return result
    def failed(self,result,reason):
        self.assertEqual(result['status'],'incomplete');self.assertFalse(result['advance']['pass_all']);self.assertFalse(result['bounded_export']);self.assertEqual(result['exception_reason'],reason)
        self.assertEqual(result['reason'],'finalization_incomplete');self.assertEqual(result['diagnostics'],{'retained':True})
    def test_private_size_failure_preserves_predictions_and_comparisons(self):
        self.failed(self.invoke(lambda _:b'x'*(16*1024*1024+1)),'private_result_cap')
    def test_public_size_failure_preserves_predictions_and_comparisons(self):
        self.failed(self.invoke([b'x',b'x'*(64*1024+1)]),'public_result_cap')
    def test_deadline_failure_preserves_predictions_and_comparisons(self):
        def expired(*_):raise RuntimeError('whole_deadline')
        self.failed(self.invoke(lambda _:b'x',expired),'whole_deadline')
    def test_success_remains_complete_with_original_evidence(self):
        result=self.invoke(lambda _:b'x');self.assertEqual(result['status'],'complete');self.assertTrue(result['advance']['pass_all']);self.assertNotIn('bounded_export',result)


if __name__=='__main__':unittest.main()
