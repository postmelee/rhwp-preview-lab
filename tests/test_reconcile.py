import importlib.util,json,os,pathlib,sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'lab'))
os.environ.setdefault('GITHUB_REPOSITORY','postmelee/rhwp-preview-lab')
import publish

class Reconcile(unittest.TestCase):
    def test_old_event_reconciles_all_current_prs_and_devel(self):
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
            json.dump({'workflow_run':{'id':123}},f);f.flush()
            with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_run','GITHUB_EVENT_PATH':f.name}),patch.object(publish,'api',return_value={'event':'pull_request','head_sha':'old'}),patch.object(publish,'pages',return_value=[{'number':1},{'number':2}]),patch.object(publish,'reconcile',side_effect=lambda n:{'target':n}) as reconcile:
                result=publish.main()
                self.assertEqual(result,[{'target':0},{'target':1},{'target':2}])
                self.assertEqual(reconcile.call_count,3)
    def test_one_blocked_request_does_not_hide_another(self):
        with tempfile.NamedTemporaryFile(mode='w',suffix='.json') as f:
            json.dump({'workflow_run':{'id':123}},f);f.flush()
            with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_run','GITHUB_EVENT_PATH':f.name}),patch.object(publish,'api',return_value={'event':'push'}),patch.object(publish,'pages',return_value=[{'number':1}]),patch.object(publish,'reconcile',side_effect=[ValueError('missing CI'),{'target':1} ]):
                result=publish.main()
                self.assertEqual(result[0]['state'],'blocked');self.assertEqual(result[1],{'target':1})

if __name__=='__main__':unittest.main()
