import pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'lab'))
from hosting import PREFIX, latest_pointers, retained_ids, Pages
import json


def deployment(id, branch, kind='asset', **kw):
    return {'id':id,'created_on':id,'latest_stage':{'status':'success'},'deployment_trigger':{'metadata':{'branch':branch,'commit_message':PREFIX+json.dumps({'kind':kind,**kw})}}}

class Hosting(unittest.TestCase):
    def test_shared_baseline_survives_devel_move_and_one_pr_close(self):
        items=[deployment('1','assets'),deployment('2','assets'),deployment('3','assets'),
               deployment('4','devel','pointer',asset='1'),
               deployment('5','pr-1','pointer',asset='2',baseline='1'),
               deployment('6','pr-2','pointer',asset='3',baseline='1'),
               deployment('7','devel','pointer',asset='3')]
        self.assertEqual(retained_ids(items,[2],'7'),{'1','3','6','7'})
        self.assertEqual(retained_ids(items,[],'7'),{'3','7'})
    def test_failed_pointer_does_not_replace_last_success(self):
        old=deployment('1','pr-1','pointer',asset='a')
        failed=deployment('2','pr-1','pointer',asset='b')
        failed['latest_stage']['status']='failure'
        self.assertEqual(latest_pointers([failed,old])['pr-1']['id'],'1')
    def test_public_probe_rejects_foreign_or_authenticated_url(self):
        p=Pages.__new__(Pages);p.domain='rhwp-preview-lab.pages.dev'
        for url in ['https://evil.test', 'https://rhwp-preview-lab.pages.dev.evil.test', 'https://user@rhwp-preview-lab.pages.dev','http://rhwp-preview-lab.pages.dev']:
            with self.assertRaises(ValueError):p.url(url)
    def test_cleanup_only_managed_and_protects_canonical(self):
        p=Pages.__new__(Pages);p.deleted=[]
        manual=deployment('0','main');manual['deployment_trigger']['metadata']['commit_message']='manual'
        old=deployment('1','assets');old['environment']='preview'
        app=deployment('2','assets')
        pointer=deployment('3','devel','pointer',asset='2')
        items=[manual,old,app,pointer]
        p.deployments=lambda:[d for d in items if d['id'] not in p.deleted]
        calls=[]
        def api(path,method='GET'):
            calls.append((path,method))
            return {'canonical_deployment':{'id':'3'}} if not path else None
        p.api=api
        result=p.cleanup([],lambda:None)
        self.assertEqual(result['deleted'],['1'])
        self.assertIn(('/deployments/1?force=true','DELETE'),calls)

if __name__=='__main__':unittest.main()
