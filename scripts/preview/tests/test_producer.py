import unittest
from producer import select_run,PATH
class Producer(unittest.TestCase):
    request={'sha':'a'*40,'head_branch':'topic','head_repository_id':2}
    def run_value(self,**kw):
        return dict(id=10,run_attempt=1,workflow_id=9,path=PATH,event='pull_request',head_sha='a'*40,head_branch='topic',head_repository={'id':2},status='completed',conclusion='success')|kw
    def test_exact_native_producer(self):
        self.assertEqual(select_run([self.run_value()],self.request,9)['id'],10)
    def test_privileged_event_never_supplies_pr_artifact(self):
        for event in ['workflow_run','workflow_dispatch','pull_request_target','push']:
            with self.assertRaises(ValueError):select_run([self.run_value(event=event)],self.request,9)
    def test_wrong_identity_rejected(self):
        for kw in [{'head_repository':{'id':3}},{'head_branch':'other'},{'head_sha':'b'*40},{'path':'.github/workflows/other.yml'},{'workflow_id':3}]:
            with self.assertRaises(ValueError):select_run([self.run_value(**kw)],self.request,9)
    def test_latest_rerun_or_newer_failed_run_never_falls_back(self):
        old=self.run_value()
        for new in [self.run_value(run_attempt=2,status='in_progress',conclusion=None),self.run_value(id=11,conclusion='failure')]:
            with self.assertRaises(ValueError):select_run([old,new],self.request,9)
