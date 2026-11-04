import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from shift_resume import submit,stored,Interrupted


class IntakeRecovery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'intake.db'

    def send(self,resume=True,**kw):
        args=dict(path=self.path,request='a1',employee='e1',shift='night1',replacement='e2',qualified=False,resume=resume)
        args.update(kw);return submit(**args)

    def crash(self,resume):
        with self.assertRaises(Interrupted):self.send(resume,interrupt=True)
        self.assertEqual(stored(self.path)[0][-1],'pending')

    def test_request_dedup_preserves_one_report_but_strands_pending_swap(self):
        self.crash(False)
        self.assertEqual(self.send(False),'already_recorded')
        self.assertEqual(len(stored(self.path)),1)
        self.assertEqual(stored(self.path)[0][-1],'pending')

    def test_stage_replay_resolves_denial_without_losing_intake(self):
        self.crash(True)
        self.assertEqual(self.send(True),'denied')
        self.assertEqual(len(stored(self.path)),1)
        self.assertEqual(stored(self.path)[0][-1],'denied')

    def test_stage_replay_can_finish_approval_after_crash(self):
        with self.assertRaises(Interrupted):self.send(qualified=True,interrupt=True)
        self.assertEqual(self.send(qualified=True),'approved')
        self.assertEqual(stored(self.path)[0][-1],'approved')

    def test_completed_stage_retries_are_stable(self):
        self.assertEqual(self.send(),'denied')
        self.assertEqual(self.send(),'denied')
        self.assertEqual(len(stored(self.path)),1)

    def test_fact_change_cannot_reuse_a_pending_identity(self):
        self.crash(True)
        with self.assertRaises(ValueError):self.send(qualified=True)
        self.assertEqual(stored(self.path)[0][-1],'pending')

    def test_ordinary_no_crash_oracle_misses_the_difference(self):
        self.assertEqual(self.send(False),'denied')
        self.assertEqual(stored(self.path)[0][-1],'denied')


if __name__=='__main__':unittest.main()
