import copy
import json
from pathlib import Path
import unittest
import tempfile

from judge_packet_codec import encode,decode,compact
import judge_protocol


class JudgeProtocolTest(unittest.TestCase):
    def setUp(self):
        self.packet={'scoring_version':'redact-scoring-v2','case':'test','trajectory_sha256':'a'*64,
            'input_hashes':{'hidden':'h','visible':'v','rubrics':'r'},
            'calls':[{'action':{'action':'FINISH'},'observation':{'time':0}}],
            'actual_final_record':{'time':36},'criteria':{'goals':[{'id':'G','weight':1}],
                'critical_violations':[]}}
        evidence=[{'path':'/calls/0/action','note':'actual action'}]
        self.judgment={k:self.packet[k] for k in ['scoring_version','case','trajectory_sha256','input_hashes']}
        self.judgment.update(goals=[{'id':'G','status':'pass','reason':'completed','evidence':evidence,
            'is_time_limited':True,'timing_reason':'deadline applies','timing_evidence':[{'path':'/actual_final_record/time'}],
            'timing_checks':[{'id':'w1','status':'pass','deadline':30,'completion_time':36,
                'inclusive':True,'reason':'late actual completion','evidence':evidence}]}],
            critical_violations=[],dimensions=[{'id':k,'score':3,'reason':'evidence','evidence':evidence}
                for k in ['evidence','timing','authorization','helpfulness','restraint','communication']],
            cq={'status':'not_scorable','score':None,'reason':'No calibrated anchors','evidence':evidence},
            needs_primary_review=[])

    def test_late_completion_keeps_gcr_but_fails_strict_tsr(self):
        metrics=judge_protocol.validate(self.judgment,self.packet)
        self.assertEqual(metrics['GCR_lower'],100)
        self.assertFalse(metrics['TSR_success'])
        self.assertEqual(metrics['LCR_lower'],0)

    def test_nonexistent_evidence_and_fabricated_quote_rejected(self):
        value=copy.deepcopy(self.judgment);value['goals'][0]['evidence']=[{'path':'/fake'}]
        with self.assertRaises(ValueError):judge_protocol.validate(value,self.packet)
        value=copy.deepcopy(self.judgment);value['goals'][0]['evidence']=[{'path':'/calls/0/action/action','quote':'BOOKING_CONFIRMED'}]
        with self.assertRaises(ValueError):judge_protocol.validate(value,self.packet)

    def test_binding_and_unresolved_deadlines_rejected(self):
        value=copy.deepcopy(self.judgment);value['trajectory_sha256']='b'*64
        with self.assertRaises(ValueError):judge_protocol.validate(value,self.packet)
        value=copy.deepcopy(self.judgment);value['goals'][0]['timing_checks'][0]['deadline']=None
        with self.assertRaises(ValueError):judge_protocol.validate(value,self.packet)

    def test_codec_preserves_json_types_paths_and_all_real_packets(self):
        repeated={'a/b~':['你好'*200,None,True,1,1.5],'inner':{'text':'long evidence '*100}}
        value={'first':repeated,'second':copy.deepcopy(repeated),'list':[repeated,repeated]}
        self.assertEqual(compact(decode(encode(value))),compact(value))
        self.assertLess(len(compact(encode(value))),len(compact(value)))
        root=Path(__file__).resolve().parent/'github_test_bundle/output/ab-eval-20261119/gpt-6.1-sol-science/judge-v2-api-20261120/reviews/paired-000/judge-inputs'
        if not root.exists():root=root.parents[2]/'lanes/0/reviews/paired-000/judge-inputs'
        paths=list(root.rglob('*.json'));self.assertEqual(len(paths),20)
        for path in paths:
            packet=json.loads(path.read_text())
            self.assertEqual(compact(decode(encode(packet))),compact(packet))

    def test_lane_aggregation_uses_episode_counts_and_timing_denominators(self):
        from run_judge_supervisor import collect
        failed=copy.deepcopy(self.judgment);failed['goals'][0]['status']='fail'
        failed['goals'][0]['timing_checks'][0].update(status='fail',completion_time=None)
        passed=copy.deepcopy(self.judgment);passed['goals'][0]['timing_checks'][0]['completion_time']=29
        def row(value,case):
            return dict(case=case,actual_tool_calls=1,requests=1,tool_errors=0,format_errors=0,
                **judge_protocol.validate(value,self.packet))
        manifest=json.loads((Path(__file__).resolve().parent/'github_test_bundle/data/current-counterfactual-manifest.json').read_text())['episodes']
        old_a=manifest[0]['case']
        contrast_a=next(entry for entry in manifest if '/contrast/' in entry['case'] and entry['configuration']=='A')
        contrast_b=next(entry['case'] for entry in manifest if entry['pair_id']==contrast_a['pair_id'] and entry['configuration']=='B')
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)
            for lane,rows in [(0,[row(failed,old_a)]),(1,[row(passed,contrast_a['case']),row(passed,contrast_b),row(passed,'primary')])]:
                root=output/'lanes'/str(lane);(root/'reviews/shard').mkdir(parents=True)
                (root/'status.json').write_text(json.dumps({'completed_cases':len(rows),'needs_review':[],'failed_cases':[]}))
                (root/'reviews/shard/metrics-v2.json').write_text(json.dumps({'overall':{'scored_episodes':len(rows)},'rows':rows}))
            collect(output,'gpt-6.1-sol-science')
            result=json.loads((output/'summary.json').read_text())
            self.assertEqual(result['overall']['scored_episodes'],4)
            self.assertEqual(result['overall']['GCR'],75)
            self.assertEqual(result['overall']['LCR'],75)
            self.assertEqual(result['overall']['TSR'],75)
            self.assertEqual(result['by_variant']['paired_A']['scored_episodes'],2)
            self.assertEqual(result['by_variant']['paired_B']['scored_episodes'],1)
            self.assertEqual(result['by_variant']['unpaired_primary']['scored_episodes'],1)


if __name__=='__main__':unittest.main(verbosity=2)
