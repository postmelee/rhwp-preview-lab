import copy,pathlib,sys,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'lab'))
from approval import grant,enforce

class Approval(unittest.TestCase):
    def setUp(self):
        self.sha='a'*40
        self.pr={'state':'open','head':{'sha':self.sha,'repo':{'id':2}},'base':{'repo':{'id':1}}}
        self.permission=lambda actor:'write'
        self.grant=grant(self.pr,7,self.sha,['maintainer','maintainer'],self.permission)
    def test_unapproved_fork_blocked(self):
        with self.assertRaisesRegex(ValueError,'awaiting'):enforce(self.pr,7,self.sha,None,self.permission)
    def test_exact_approved_fork_allowed(self):
        enforce(self.pr,7,self.sha,self.grant,self.permission)
    def test_push_or_force_push_invalidates(self):
        self.pr['head']['sha']='b'*40
        with self.assertRaises(ValueError):enforce(self.pr,7,'b'*40,self.grant,self.permission)
    def test_live_head_rechecked_even_with_old_argument(self):
        self.pr['head']['sha']='b'*40
        with self.assertRaises(ValueError):enforce(self.pr,7,self.sha,self.grant,self.permission)
    def test_other_pr_or_repository_rejected(self):
        with self.assertRaises(ValueError):enforce(self.pr,8,self.sha,self.grant,self.permission)
        self.pr['head']['repo']['id']=3
        with self.assertRaises(ValueError):enforce(self.pr,7,self.sha,self.grant,self.permission)
    def test_revoked_permission_and_unprivileged_rerun_rejected(self):
        with self.assertRaises(ValueError):enforce(self.pr,7,self.sha,self.grant,lambda actor:'read')
        with self.assertRaises(ValueError):grant(self.pr,7,self.sha,['maintainer','outsider'],lambda actor:'write' if actor=='maintainer' else 'read')
    def test_closed_and_missing_identity_fail_closed(self):
        self.pr['state']='closed'
        with self.assertRaises(ValueError):enforce(self.pr,7,self.sha,self.grant,self.permission)
        self.pr['head']['repo']=None
        with self.assertRaises(ValueError):enforce(self.pr,7,self.sha,self.grant,self.permission)
    def test_internal_pr_requires_no_grant(self):
        self.pr['head']['repo']['id']=1
        enforce(self.pr,7,self.sha,None,lambda actor: self.fail('unexpected permission query'))
    def test_abbreviated_or_wrong_sha_rejected(self):
        for sha in ['a'*7,'b'*40]:
            with self.assertRaises(ValueError):grant(self.pr,7,sha,['maintainer'],self.permission)

if __name__=='__main__':unittest.main()
