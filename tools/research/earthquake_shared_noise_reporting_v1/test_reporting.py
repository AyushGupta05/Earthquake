"""Invented audited-result/receipt fixtures only; no actual scientific outputs."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
import io
import contextlib
import reporting as r

HASH='1'*64
PIN=dict(bytes=1,sha256=HASH)

def fixture():
    roster=[dict(ordinal=i,target=5.7 if i<13 else 4.8,group=i//2)for i in range(22)]
    def panel(arm):
        # Explicit invented values do not describe any real model.
        x=.4 if arm=='S'else .45
        return dict(n=22,nll=.7,crps=.3,mae=x,medae=x,tail_mae_5_5=x,tail_mae_6=None,lower_mae=x,lower_medae=x,tail_bias=-.1,cvar95=.8,maximum=1.,p95=.7,median_mae=.5,coverage_50=.5,coverage_80=.8,coverage_95=.95)
    def fit(pair,new):
        records=[dict(row,horizon=h,receiver=[999.,998.,997.],family='invented',private_extra='stripme')for row in roster for h in r.H];out=dict(seed=pair[0],arm=pair[1],records=records,metrics={str(h):panel(pair[1])for h in r.H})
        if new:out['strata']={'private_groups':[7001,7002]}
        return out
    fits=[fit(p,True)for p in r.NEW];old=[fit(p,False)for p in r.OLD];lookup={(x['seed'],x['arm']):x['metrics']for x in fits+old};checks=[];extra=[]
    for seed in r.SEEDS:
        for h in r.H:
            for a in('B','F','H','T','P','D'):
                item=r.expected_guard(seed,h,a,lookup[seed,'S'][str(h)],lookup[seed,a][str(h)]);(extra if a in('P','D')else checks).append(item)
    paired=[]
    for seed in r.SEEDS:
        for arm in('B','F','H','T','P','D'):
            for h in r.H:
                metrics={k:dict(status='unsupported'if k=='tail_mae_6'else'descriptive',groups=0 if k=='tail_mae_6'else 11,delta=None if k=='tail_mae_6'else-.05,interval=None if k=='tail_mae_6'else[-.1,.02])for k in r.PANEL if k!='n'};paired.append(dict(seed=seed,horizon=h,comparator=arm,metrics=metrics))
    report=dict(schema='marked-sixfit-independent-aggregate-v1',status='pass',checked=396,fits=fits,stronger=old,paired=paired,advance=dict(pass_all=all(i['passed']for i in checks+extra),checks=checks,additional=extra),authority_sha256=HASH)
    raw=r.canonical(report);stages=[dict(index=i,status='complete',unit_inactive=True,cgroup_empty=True,checked=66 if i<6 else 396,report_pin=dict(PIN)if i<6 else r.pin(raw),closed_pin=dict(PIN),root_evidence_pin=dict(PIN))for i in range(7)]
    closed=dict(schema='root-shared-noise-reporting-closure-v1',status='complete',aggregate_pin=r.pin(raw),stages=stages,whole_stop_verified=True,readonly_fetch_verified=True,counts=dict(r.COUNTS),dev_roster_sha256=r.pin(r.canonical(roster))['sha256'])
    return report,closed

def prepare(report,closed):
    raw=r.canonical(report);closed=copy.deepcopy(closed);closed['aggregate_pin']=r.pin(raw);
    if len(closed['stages'])>6:closed['stages'][6]['report_pin']=r.pin(raw)
    closure=r.canonical(closed);return r.prepare_public(raw,closure,r.pin(closure))

class Tests(unittest.TestCase):
    def test_negative_gate_preserved(self):
        report,c=fixture();out=prepare(report,c);self.assertFalse(out['summary']['advance']['pass_all']);self.assertIn('did not pass',out['markdown']);self.assertEqual(len(out['summary']['advance']['checks'])+len(out['summary']['advance']['additional']),36)
    def test_private_records_group_receiver_stripped(self):
        out=prepare(*fixture());text=r.canonical(out).decode()
        for secret in('private_extra','stripme','private_groups','receiver','family','ordinal','999.0','7001'):self.assertNotIn(secret,text)
        self.assertEqual(len(out['summary']['fits']),6);self.assertEqual(len(out['summary']['stronger']),8)
    def test_wrong_root_hash_rejected(self):
        report,c=fixture()
        with self.assertRaisesRegex(ValueError,'root_closure_pin'):r.prepare_public(r.canonical(report),r.canonical(c),PIN)
    def test_wrong_report_hash_rejected(self):
        report,c=fixture();report['fits'][0]['metrics']['1']['mae']=.9;raw=r.canonical(c)
        with self.assertRaisesRegex(ValueError,'aggregate_pin'):r.prepare_public(r.canonical(report),raw,r.pin(raw))
    def test_incomplete_independent_report(self):
        report,c=fixture();report['status']='fail'
        with self.assertRaisesRegex(ValueError,'aggregate_incomplete'):prepare(report,c)
    def test_missing_stage(self):
        report,c=fixture();c['stages'].pop()
        with self.assertRaisesRegex(ValueError,'seven_stages'):prepare(report,c)
    def test_cleanup_not_verified(self):
        report,c=fixture();c['stages'][3]['cgroup_empty']=False
        with self.assertRaisesRegex(ValueError,'stage_closed'):prepare(report,c)
    def test_timer_stop_unknown(self):
        report,c=fixture();c['whole_stop_verified']=False
        with self.assertRaisesRegex(ValueError,'root_not_closed'):prepare(report,c)
    def test_fetch_not_readonly(self):
        report,c=fixture();c['readonly_fetch_verified']=False
        with self.assertRaisesRegex(ValueError,'root_not_closed'):prepare(report,c)
    def test_wrong_native_counts(self):
        report,c=fixture();c['counts']['common_train']=64
        with self.assertRaisesRegex(ValueError,'counts'):prepare(report,c)
    def test_wrong_cohort_rejected(self):
        report,c=fixture();report['fits'][0]['records'][0]['target']=8.
        with self.assertRaisesRegex(ValueError,'cohort_horizons'):prepare(report,c)
    def test_same_changed_cohort_still_root_digest_rejects(self):
        report,c=fixture()
        for fit in report['fits']+report['stronger']:
            for record in fit['records'][:3]:record['target']=8.
        with self.assertRaisesRegex(ValueError,'cohort_pin'):prepare(report,c)
    def test_wrong_guard_cohort_triplet(self):
        report,c=fixture();report['advance']['checks'][0]['horizon']=5
        with self.assertRaisesRegex(ValueError,'guard_cohort_or_outcome'):prepare(report,c)
    def test_averaged_guard_failure_not_success(self):
        report,c=fixture();report['advance']['pass_all']=True
        with self.assertRaisesRegex(ValueError,'guard_cohort_or_outcome'):prepare(report,c)
    def test_numeric_boolean_guard_not_cast(self):
        report,c=fixture();report['advance']['checks'][0]['proper']=0
        with self.assertRaisesRegex(ValueError,'guard_types'):prepare(report,c)
    def test_unknown_metric_cannot_export_private_key(self):
        report,c=fixture();report['fits'][0]['metrics']['1']['event_id']='private'
        with self.assertRaisesRegex(ValueError,'keys'):prepare(report,c)
    def test_missing_paired_panel(self):
        report,c=fixture();report['paired'].pop()
        with self.assertRaisesRegex(ValueError,'paired36'):prepare(report,c)
    def test_unsupported_interval_not_invented(self):
        report,c=fixture();report['paired'][0]['metrics']['tail_mae_6']['interval']=[-.1,.1]
        with self.assertRaisesRegex(ValueError,'unsupported_interval'):prepare(report,c)
    def test_notebook_fourcells_executes_public_only_fixture(self):
        book=json.loads(Path(__file__).with_name('public_results.ipynb').read_text());self.assertEqual(len(book['cells']),4)
        with tempfile.TemporaryDirectory()as d:
            Path(d,'public_summary.json').write_bytes(r.canonical(prepare(*fixture())['summary']));old=os.getcwd();scope={}
            try:
                os.chdir(d)
                for cell in book['cells']:
                    if cell['cell_type']=='code':
                        self.assertEqual(cell['outputs'],[]);self.assertIsNone(cell['execution_count']);
                        with contextlib.redirect_stdout(io.StringIO()):exec(compile(''.join(cell['source']),'<invented-public-notebook>','exec'),scope)
            finally:os.chdir(old)
    def test_markdown_labels_actions_separately(self):
        md=prepare(*fixture())['markdown'];self.assertIn('Mean MAE',md);self.assertIn('Mean MedAE',md);self.assertIn('Median-action MAE',md);self.assertIn('no novelty',md)

if __name__=='__main__':unittest.main()
