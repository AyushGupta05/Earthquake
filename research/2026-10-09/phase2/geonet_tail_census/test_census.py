"""Invented fixtures only; no network calls."""
import io
from pathlib import Path
import tempfile
import unittest
import census as c


def csv_body(lines):
    return ('EVENT_ID,Date,Mw,Method\n'+'\n'.join(lines)+'\n').encode()


def xml(picks=None, arrivals=None, origin='o', identity='2000p000001'):
    if picks is None:
        picks=[('a','NZ','AAA','2020-01-01T00:00:00Z',''),('b','NZ','BBB','2020-01-01T00:00:01Z',''),('c','XX','CCC','2020-01-01T00:00:02Z','')]
    if arrivals is None: arrivals=[('a','P',''),('b','Pg',''),('c','P','')]
    ps=''.join(f'<pick publicID="{pid}"><time><value>{tm}</value></time><waveformID networkCode="{net}" stationCode="{sta}" locationCode="10" channelCode="HHZ"/>{extra}</pick>' for pid,net,sta,tm,extra in picks)
    aa=''.join(f'<arrival><pickID>{pid}</pickID><phase>{ph}</phase>{extra}</arrival>' for pid,ph,extra in arrivals)
    return f'<q:quakeml xmlns:q="http://quakeml.org/xmlns/quakeml/1.2"><eventParameters xmlns="http://quakeml.org/xmlns/bed/1.2"><event publicID="smi:example/event/{identity}"><preferredOriginID>{origin}</preferredOriginID><origin publicID="o">{aa}</origin>{ps}<magnitude><type>ML</type></magnitude></event></eventParameters></q:quakeml>'.encode()


class ParseTests(unittest.TestCase):
    def test_cmt_dedup_bounds_and_provenance(self):
        rr,gg=c.parse_cmt(csv_body(['2000p000001,20100101000000,5.4,1','2000p000001,20100101000000,5.6,2','1234567,20090715092200,7.0,n/a','9999999,20100102000000,8.0,1']))
        s=c.summarize(rr,gg,{})
        self.assertEqual(s['duplicate_extra_rows'],1)
        self.assertEqual(s['thresholds']['5.5']['unique_id_lower'],1)
        self.assertEqual(s['thresholds']['5.5']['unique_id_upper'],2)
        self.assertEqual(s['thresholds']['7.0']['external_wphase_lower'],1)
        self.assertEqual(s['row_exclusion_reasons']['unknown_9999999'],1)
        self.assertEqual(len(c.query_order(gg)),2)

    def test_bad_and_mixed_rows_not_selected(self):
        rr,gg=c.parse_cmt(csv_body(['2000p000001,20100101000000,6,1','2000p000001,20250101000000,6,2','2000p000002,20100101000000,nan,1','2000p000003,bad,6,1','no-id,20100101000000,7,1']))
        self.assertFalse(any(g['eligible'] for g in gg)); self.assertEqual(len(rr),5)

    def test_date_boundary_and_unknown_ids_not_merged(self):
        rr,gg=c.parse_cmt(csv_body(['12345,20030801000000,6,1','12346,20241231235900,7,2','9999999,20100101000000,6,1','9999999,20100201000000,6,1']))
        self.assertEqual(len(gg),2); self.assertTrue(all(g['eligible'] for g in gg))
        self.assertEqual(c.summarize(rr,gg,{})['row_exclusion_reasons']['unknown_9999999'],2)

    def test_schema_fail_closed(self):
        for b in [b'Id,Mw\n1,6\n',b'EVENT_ID,Date,Mw,Method,mw\n',b'EVENT_ID,Date,Mw,Method\n1,2,3,4,5\n']:
            with self.assertRaises(ValueError): c.parse_cmt(b)

    def test_publicid_alias_preserves_original_and_rejects_ambiguity(self):
        body=b' PublicID ,Date,Mw,Method\n12345,20100101000000,6,1\n'
        rows,groups=c.parse_cmt(body)
        self.assertEqual(rows[0]['event_id'],'12345')
        self.assertEqual(rows[0]['original'][' PublicID '],'12345')
        self.assertTrue(groups[0]['eligible'])
        for header in ('PublicID,EVENT_ID,Date,Mw,Method','publicid,PublicID,Date,Mw,Method'):
            with self.assertRaises(ValueError): c.parse_cmt((header+'\n').encode())

    def test_order_stable(self):
        _,gg=c.parse_cmt(csv_body(['12345,20100101000000,6,1','12346,20100101000000,7,2']))
        self.assertEqual(c.query_order(gg),c.query_order(list(reversed(gg))))

    def test_utc_strict_boundary_scopes(self):
        r=c.parse_quakeml(xml(),'2000p000001')
        self.assertEqual(r['all_network']['before_seconds'],{'1':1,'3':3,'5':3})
        self.assertEqual(r['nz']['before_seconds'],{'1':1,'3':2,'5':2})
        self.assertEqual(r['catalog_magnitude_types'],['ML'])
        self.assertEqual(c.utc('2020-01-01T01:00:00+01:00'),c.utc('2020-01-01T00:00:00Z'))

    def test_duplicate_channels_arrivals_not_stations(self):
        ps=[('a','NZ','AAA','2020-01-01T00:00:00Z',''),('b','NZ','AAA','2020-01-01T00:00:02Z','')]
        r=c.parse_quakeml(xml(ps,[('a','P',''),('a','P',''),('b','Pn','')]),'2000p000001')
        self.assertEqual(r['nz']['stations'],1); self.assertEqual(len(r['accepted_picks']),2)
        self.assertEqual(r['reasons']['duplicate_accepted_arrival_reference'],1)

    def test_missing_origin_unknown(self):
        r=c.parse_quakeml(xml(origin='absent'),'2000p000001'); self.assertIsNone(r['nz'])
        rr,gg=c.parse_cmt(csv_body(['2000p000001,20100101000000,6,1']))
        p=c.summarize(rr,gg,{'2000p000001':r})['thresholds']['6.0']['coverage']['nz']
        self.assertEqual(p['unknown_coverage_events'],1); self.assertEqual(p['known_coverage_events'],0)

    def test_rejections_no_phase_hint_fallback(self):
        ps=[('a','NZ','AAA','2020-01-01T00:00:00',''),('b','','BBB','2020-01-01T00:00:00Z',''),('c','NZ','CCC','2020-01-01T00:00:00Z','<evaluationStatus>rejected</evaluationStatus>'),('d','NZ','DDD','2020-01-01T00:00:00Z','<phaseHint>P</phaseHint>')]
        aa=[('a','P',''),('b','P',''),('c','P',''),('missing','P',''),('d','S',''),('d','P','<timeWeight>0</timeWeight>')]
        r=c.parse_quakeml(xml(ps,aa),'2000p000001')
        self.assertEqual(r['nz']['stations'],0); self.assertEqual(len(r['reasons']),6)

    def test_ambiguous_pick_reference(self):
        ps=[('a','NZ','AAA','2020-01-01T00:00:00Z','')]*2
        r=c.parse_quakeml(xml(ps,[('a','P','')]),'2000p000001')
        self.assertEqual(r['nz']['stations'],0)
        self.assertEqual(r['reasons']['missing_or_ambiguous_pick_reference'],1)

    def test_identity_dtd_fail(self):
        for b in [xml(identity='2000p000002'),b'<!DOCTYPE a><a/>']:
            with self.assertRaises(ValueError): c.parse_quakeml(b,'2000p000001')

    def test_no_origin_clock_geometry_use(self):
        original=c.parse_quakeml(xml(),'2000p000001')
        changed=xml().replace(b'<origin publicID="o">',b'<origin publicID="o"><time><value>1900-01-01T00:00:00Z</value></time><latitude><value>40</value></latitude>')
        self.assertEqual(original['nz'],c.parse_quakeml(changed,'2000p000001')['nz'])

    def test_foreign_fields_cannot_supply_bed_pick_evidence(self):
        b=xml().replace(b'<event publicID=',b'<event xmlns:x="https://fixture.invalid/extension" publicID=')
        foreign_preferred=b.replace(b'<preferredOriginID>o</preferredOriginID>',b'<x:preferredOriginID>o</x:preferredOriginID>')
        self.assertEqual(c.parse_quakeml(foreign_preferred,'2000p000001')['status'],'missing_or_ambiguous_preferred_origin')
        foreign_time=b.replace(b'<time><value>2020-01-01T00:00:00Z</value></time>',b'<x:time><x:value>2020-01-01T00:00:00Z</x:value></x:time>')
        r=c.parse_quakeml(foreign_time,'2000p000001')
        self.assertEqual(r['nz']['stations'],1)
        self.assertEqual(r['reasons']['invalid_or_naive_pick_time'],1)
        foreign_origin=b.replace(b'<origin publicID="o">',b'<x:origin publicID="o">').replace(b'</origin>',b'</x:origin>')
        self.assertEqual(c.parse_quakeml(foreign_origin,'2000p000001')['status'],'missing_or_ambiguous_preferred_origin')
        for field in ('phase','pickID','waveformID'):
            changed=b.replace(('<'+field).encode(),('<x:'+field).encode()).replace(('</'+field+'>').encode(),('</x:'+field+'>').encode())
            self.assertEqual(c.parse_quakeml(changed,'2000p000001')['nz']['stations'],0)

    def test_wrong_root_and_bed_namespaces_rejected(self):
        for namespace in (c.QML_NS,c.BED_NS):
            with self.assertRaises(ValueError): c.parse_quakeml(xml().replace(namespace.encode(),b'https://fixture.invalid/foreign'),'2000p000001')


class Response(io.BytesIO):
    def __init__(self,body,length=True,status=200):
        super().__init__(body); self.status=status
        self.headers={'Content-Length':str(len(body))} if length else {}


class Opener:
    def __init__(self,responses): self.responses=list(responses); self.calls=[]
    def open(self,req,timeout):
        self.calls.append((req.full_url,timeout)); return self.responses.pop(0)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)/'raw'; self.root.mkdir(); self.now=0
    def tearDown(self): self.temp.cleanup()
    def clock(self): return self.now
    def sleep(self,seconds): self.now+=seconds
    def fetcher(self,responses,**kwargs): return c.Fetcher(self.root,self.clock,self.sleep,Opener(responses),**kwargs)

    def test_success_hash_rate_attempt_cap(self):
        f=self.fetcher([Response(b'abc'),Response(b'd')],max_requests=2)
        self.assertEqual(f.fetch('https://fixture.invalid/a','a',100),b'abc')
        f.fetch('https://fixture.invalid/b','b',100)
        self.assertEqual(f.bytes,4); self.assertEqual(self.now,1); self.assertEqual(f.log[0]['sha256'],c.sha(b'abc'))
        with self.assertRaises(c.LimitReached): f.fetch('https://fixture.invalid/c','c',100)
        self.assertEqual(len(f.opener.calls),2)

    def test_header_limit(self):
        f=self.fetcher([Response(b'12345')],max_bytes=4)
        with self.assertRaises(c.LimitReached): f.fetch('https://fixture.invalid/a','a',10)
        self.assertEqual(f.bytes,0); self.assertEqual(len(f.log),1); self.assertEqual((self.root/'a').read_bytes(),b'')

    def test_unknown_length_cap_partial(self):
        f=self.fetcher([Response(b'1234567',False)],max_bytes=4)
        with self.assertRaises(c.LimitReached): f.fetch('https://fixture.invalid/a','a',10)
        self.assertEqual(f.bytes,4); self.assertEqual((self.root/'a').read_bytes(),b'1234')

    def test_exact_known_length_deadline(self):
        f=self.fetcher([Response(b'1234')],max_bytes=4)
        self.assertEqual(f.fetch('https://fixture.invalid/a','a',10),b'1234')
        self.now=2000
        with self.assertRaises(c.LimitReached): f.check()

    def test_http_status_consumes_attempt(self):
        f=self.fetcher([Response(b'',status=204)])
        with self.assertRaises(ValueError): f.fetch('https://fixture.invalid/a','a',10)
        self.assertEqual(f.log[0]['http_status'],204); self.assertEqual(len(f.log),1)

    def test_redirect_disabled(self):
        self.assertIsNone(c.NoRedirect().redirect_request(None,None,302,'',{},'https://other.invalid'))



class ReviewRegressionTests(unittest.TestCase):
    def test_nonzero_date_seconds_excluded(self):
        rr,gg=c.parse_cmt(csv_body(['12345,20100101000059,6,1']))
        self.assertEqual(rr[0]['reasons'],['invalid_date']); self.assertFalse(gg[0]['eligible'])

    def test_conflicting_singleton_fields_fail_closed(self):
        for b in [xml().replace(b'<preferredOriginID>o</preferredOriginID>',b'<preferredOriginID>o</preferredOriginID><preferredOriginID>x</preferredOriginID>'), xml().replace(b'<phase>P</phase>',b'<phase>P</phase><phase>S</phase>',1), xml().replace(b'<time><value>',b'<evaluationStatus>reviewed</evaluationStatus><evaluationStatus>rejected</evaluationStatus><time><value>',1)]:
            with self.assertRaises(ValueError): c.parse_quakeml(b,'2000p000001')

    def test_output_traversal_rejected(self):
        base=Path(c.__file__).resolve().parent
        self.assertEqual(c.validate_output(base/'local_runs'/'fixture'),base/'local_runs'/'fixture')
        for path in [base/'local_runs'/'..'/'leak',base/'local_runs',Path('/tmp/local_runs/leak')]:
            with self.assertRaises(ValueError): c.validate_output(path)

    def test_whole_request_clock_limit(self):
        now=[0]
        class SlowResponse(Response):
            def read1(self,n):
                now[0]+=21
                return super().read1(n)
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'; raw.mkdir()
            f=c.Fetcher(raw,lambda:now[0],lambda s:None,Opener([SlowResponse(b'body',False)]))
            with self.assertRaises(TimeoutError): f.fetch('https://fixture.invalid/a','a',100)
            self.assertEqual(f.log[0]['status'],'TimeoutError')

    def test_limit_attempt_recorded_not_unqueried(self):
        from unittest.mock import patch
        import json
        class LimitedFetcher:
            def __init__(self, root, **kwargs):
                self.root=root; self.log=[]; self.bytes=0; self.started=0
            def clock(self): return 1
            def check(self): pass
            def fetch(self, url, name, cap):
                self.log.append({'url':url})
                if name=='commit.json': return json.dumps({'sha':'a'*40}).encode()
                if name=='README.md': return b'invented README'
                if name.endswith('.csv'): return csv_body(['12345,20100101000000,6,1'])
                raise c.LimitReached('fixture cap')
        with tempfile.TemporaryDirectory() as tmp, patch.object(c,'Fetcher',LimitedFetcher):
            out=Path(tmp)/'run'
            self.assertEqual(c.run(out),2)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['not_queried'],0)
            self.assertEqual(summary['query_outcome_status'],{'incomplete':1})



    def test_duplicate_pick_time_is_schema_failure(self):
        b=xml().replace(b'<value>2020-01-01T00:00:00Z</value>',b'<value>2020-01-01T00:00:00Z</value><value>2020-01-01T00:00:01Z</value>',1)
        with self.assertRaisesRegex(ValueError,'duplicate singleton'): c.parse_quakeml(b,'2000p000001')

    def test_duplicate_empty_time_container_is_schema_failure(self):
        for extra in (b'<time/>',b'<time><value>2020-01-01T00:00:01Z</value></time>'):
            b=xml().replace(b'<time><value>2020-01-01T00:00:00Z</value></time>',extra+b'<time><value>2020-01-01T00:00:00Z</value></time>',1)
            with self.assertRaisesRegex(ValueError,'duplicate singleton'): c.parse_quakeml(b,'2000p000001')

    def test_response_persistence_alarm_disabled(self):
        from unittest.mock import patch
        observed=[]; original_dump=c.dump
        def checked_dump(path,obj):
            observed.append(c.signal.getitimer(c.signal.ITIMER_REAL)[0])
            original_dump(path,obj)
        with tempfile.TemporaryDirectory() as tmp:
            raw=Path(tmp)/'raw'; raw.mkdir()
            f=c.Fetcher(raw,opener=Opener([Response(b'body')]),request_alarm=True)
            try:
                with patch.object(c,'dump',checked_dump): f.fetch('https://fixture.invalid/a','a',100)
            finally: c.signal.setitimer(c.signal.ITIMER_REAL,0)
        self.assertEqual(observed,[0.0])



    def test_encoded_dtd_entity_rejected(self):
        text='<!DOCTYPE a [<!ENTITY x "expanded">]><a>&x;</a>'
        for encoding in ('utf-16','utf-16-le','utf-16-be','utf-32','utf-8'):
            with self.assertRaises(ValueError): c.parse_quakeml(text.encode(encoding),'2000p000001')



    def test_limit_before_attempt_remains_unqueried(self):
        from unittest.mock import patch
        import json
        class LimitedFetcher:
            def __init__(self, root, **kwargs): self.log=[]; self.bytes=0; self.started=0
            def clock(self): return 1
            def check(self): pass
            def fetch(self, url, name, cap):
                if name.endswith('.xml'): raise c.LimitReached('fixture rate wait cap')
                self.log.append({'url':url})
                if name=='commit.json': return json.dumps({'sha':'a'*40}).encode()
                if name=='README.md': return b'invented README'
                return csv_body(['12345,20100101000000,6,1'])
        with tempfile.TemporaryDirectory() as tmp, patch.object(c,'Fetcher',LimitedFetcher):
            out=Path(tmp)/'run'
            self.assertEqual(c.run(out),2)
            summary=json.loads((out/'summary.json').read_text())
            self.assertEqual(summary['not_queried'],1)
            self.assertEqual(summary['query_outcome_status'],{})


class RecoveryTests(unittest.TestCase):
    def fixture(self,root):
        import json
        prior=root/'prior'; raw=prior/'raw'; raw.mkdir(parents=True)
        commit='a'*40
        names=['commit.json','README.md','GeoNet_CMT_solutions.csv']
        bodies=[json.dumps({'sha':commit}).encode(),b'invented README',b'PublicID,Date,Mw,Method\n']
        urls=[c.COMMIT_URL]+[f'https://raw.githubusercontent.com/GeoNet/data/{commit}/moment-tensor/'+n for n in names[1:]]
        log=[]; files={}
        for name,body,url in zip(names,bodies,urls):
            (raw/name).write_bytes(body)
            log.append({'file':name,'url':url,'utc':'2000-01-01T00:00:00+00:00','status':'ok','bytes':len(body),'sha256':c.sha(body)})
            files['raw/'+name]={'bytes':len(body),'sha256':c.sha(body)}
        c.dump(prior/'requests.json',log)
        files['requests.json']={'sha256':c.sha((prior/'requests.json').read_bytes())}
        manifest={'completed':False,'stop_reason':'ValueError: missing/duplicate CMT required columns',
                  'geonet_commit':commit,'files':files,'response_body_bytes':sum(map(len,bodies))}
        c.dump(prior/'manifest.json',manifest)
        return prior,{'prior_manifest_sha256':c.sha((prior/'manifest.json').read_bytes())}

    def test_expired_original_window_keeps_new_clock_and_combined_counts(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); prior,plan=self.fixture(root)
            raw=root/'new'/'raw'; raw.mkdir(parents=True)
            f=c.Fetcher(raw,clock=lambda:123.0,opener=Opener([]))
            with patch.object(c,'validate_output',lambda p:p):
                commit,body,pin=c.bootstrap_sources(prior,raw,f,plan)
            self.assertEqual(commit,'a'*40)
            self.assertEqual(body,b'PublicID,Date,Mw,Method\n')
            self.assertEqual(pin,plan['prior_manifest_sha256'])
            self.assertEqual(f.started,123.0); self.assertEqual(f.deadline,1923.0)
            self.assertEqual(len(f.log),3); self.assertGreater(f.bytes,0)
            self.assertEqual((raw.parent/'requests.json').read_bytes(),(prior/'requests.json').read_bytes())

    def test_bootstrap_tamper_rejected(self):
        from unittest.mock import patch
        for name in ('manifest.json','requests.json','raw/README.md','raw/GeoNet_CMT_solutions.csv'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); prior,plan=self.fixture(root)
                path=prior/name; path.write_bytes(path.read_bytes()+b' ')
                raw=root/'new'/'raw'; raw.mkdir(parents=True)
                f=c.Fetcher(raw,opener=Opener([]))
                with patch.object(c,'validate_output',lambda p:p), self.assertRaises(ValueError):
                    c.bootstrap_sources(prior,raw,f,plan)

    def test_bootstrap_never_resets_expired_new_window(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); prior,plan=self.fixture(root)
            raw=root/'new'/'raw'; raw.mkdir(parents=True)
            now=[123.0]; f=c.Fetcher(raw,clock=lambda:now[0],opener=Opener([]))
            now[0]=2000.0
            with patch.object(c,'validate_output',lambda p:p), self.assertRaises(c.LimitReached):
                c.bootstrap_sources(prior,raw,f,plan)
            self.assertEqual(f.deadline,1923.0)

    def test_recovery_manifest_requires_current_processing_hashes_and_fixed_caps(self):
        base=Path(c.__file__).resolve().parent
        names=('census.py','test_census.py','PROTOCOL_v1.md','AMENDMENT_20261010_PUBLICID.md','RECOVERY_WINDOW_v1.md')
        plan={'version':'geonet-source-header-recovery-v1','window_seconds':1800,
              'combined_request_limit':500,'combined_body_byte_limit':100*c.MIB,
              'prior_manifest_sha256':'a'*64,
              'processing_files':{name:c.sha((base/name).read_bytes()) for name in names}}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'plan.json'; c.dump(path,plan)
            self.assertEqual(c.validate_recovery_plan(path),plan)
            plan['window_seconds']=1801; c.dump(path,plan)
            with self.assertRaises(ValueError): c.validate_recovery_plan(path)
            plan['window_seconds']=1800; plan['processing_files']['census.py']='0'*64; c.dump(path,plan)
            with self.assertRaises(ValueError): c.validate_recovery_plan(path)

    def test_unpaired_recovery_arguments_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            with self.assertRaises(ValueError): c.run(out,Path(tmp)/'prior')
            self.assertFalse(out.exists())

if __name__=='__main__': unittest.main()
