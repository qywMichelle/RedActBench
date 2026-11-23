"""Memory reservations and process locks; offline, no paid model requests."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

import judge_resources
from run_parallel_judge import available_slots,live_adopted

ROOT=Path(__file__).resolve().parent


class ParallelJudgeTest(unittest.TestCase):
    def test_adopted_requests_keep_their_parallel_slots(self):
        config={'max_extra_workers':4,'extra_while_opus_running':4}
        self.assertEqual(available_slots(config,False,[11,12]),2)
        self.assertEqual(available_slots(config,True,[11,12,13,14]),0)
        self.assertEqual(available_slots(config,False,[]),4)
        config['extra_while_opus_running']=2
        self.assertEqual(available_slots(config,False,[11,12]),0)
        self.assertEqual(live_adopted([999999999]),[])

    def test_memory_charge_includes_image_and_packet_reserve(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'packet.json';path.write_text('{"calls":[{"image_inputs":[]}]}')
            normal=judge_resources.charge(path)
            path.write_text('{"calls":[{"image_inputs":[{"path":"asset"}]}]}')
            self.assertGreater(judge_resources.charge(path),normal+120*1024**2)

    def test_reservations_count_unallocated_memory_without_double_counting(self):
        self.assertTrue(judge_resources.admitted(300,{1:200},{1:100,2:50},2,100,450))
        self.assertFalse(judge_resources.admitted(300,{1:200},{1:100,2:50},2,100,449))
        self.assertTrue(judge_resources.admitted(300,{1:100},{1:200,2:50},2,100,350))

    def test_same_case_processes_are_serialized_before_main(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp);packet=output/'lanes/0/reviews/x/judge-inputs/case.json'
            packet.parent.mkdir(parents=True);packet.write_text('{"calls":[]}')
            entry=output/'judge_case.py';entry.write_text('pass')
            config=output/'config.json'
            config.write_text(json.dumps({'enabled':True,'entrypoint':str(entry),'output':str(output),
                'resources_source':str(ROOT/'judge_resources.py'),
                'resources_sha256':hashlib.sha256((ROOT/'judge_resources.py').read_bytes()).hexdigest(),
                'reservation_limit_bytes':8*1024**3}))
            script=('import sys,time; sys.path.insert(0,'+repr(str(ROOT))+'); '
                'cfg=sys.argv[1]; sys.argv=sys.argv[2:]; import judge_case_startup as startup; '
                'startup.configure(cfg); print(time.time(),flush=True); time.sleep(.7)')
            command=[sys.executable,'-S','-c',script,str(config),str(entry),'--packet',str(packet)]
            first=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            entered=float(first.stdout.readline())
            second=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
            out,error=second.communicate(timeout=5);first.communicate(timeout=5)
            self.assertEqual(second.returncode,0,error)
            self.assertGreaterEqual(float(out.strip())-entered,.65)

    def test_repeated_venv_startup_keeps_one_reservation(self):
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp);packet=output/'lanes/0/reviews/x/judge-inputs/case.json'
            packet.parent.mkdir(parents=True);packet.write_text('{"calls":[]}')
            entry=output/'judge_case.py';entry.write_text('pass')
            config=output/'config.json'
            config.write_text(json.dumps({'enabled':True,'entrypoint':str(entry),'output':str(output),
                'resources_source':str(ROOT/'judge_resources.py'),
                'resources_sha256':hashlib.sha256((ROOT/'judge_resources.py').read_bytes()).hexdigest(),
                'reservation_limit_bytes':8*1024**3}))
            script=('import sys; sys.path.insert(0,'+repr(str(ROOT))+'); '
                'cfg=sys.argv[1]; sys.argv=sys.argv[2:]; import judge_case_startup as startup; '
                'startup.configure(cfg); first=startup.HELD; startup.configure(cfg); '
                'print(startup.HELD is first,flush=True)')
            result=subprocess.run([sys.executable,'-S','-c',script,str(config),str(entry),'--packet',str(packet)],
                capture_output=True,text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'True')
            state=json.loads((output/'memory-reservations.json').read_text())
            self.assertEqual(state,{'charges':{},'waiting':[]})


if __name__=='__main__':unittest.main(verbosity=2)
