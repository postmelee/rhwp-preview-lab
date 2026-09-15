import unittest
from test_hosting import deployment
from reuse import missing_sources
from recipe import fingerprint
class Reuse(unittest.TestCase):
    def test_devel_reuses_verified_same_sha(self):
        self.assertEqual(missing_sources({'number':0,'sha':'s'},[deployment('1','assets',sha='s',recipe=fingerprint(),producer="trusted-source")]),[])
    def test_privileged_job_builds_only_missing_exact_base(self):
        self.assertEqual(missing_sources({'number':1,'sha':'s','base_sha':'b'},[]),['b'])
    def test_existing_pr_keeps_original_baseline_after_base_moves(self):
        self.assertEqual(missing_sources({'number':1,'sha':'s','base_sha':'new'},[deployment('1','pr-1','pointer',sha='old',asset='a',baseline='original')]),[])
    def test_failed_asset_never_skips_build(self):
        d=deployment('1','assets',sha='s',recipe=fingerprint(),producer="trusted-source");d['latest_stage']['status']='failure'
        self.assertEqual(missing_sources({'number':0,'sha':'s'},[d]),['s'])

    def test_old_recipe_requires_new_build(self):
        self.assertEqual(missing_sources({'number':0,'sha':'s'},[deployment('1','assets',sha='s',recipe='old')]),['s'])

    def test_pr_artifact_cannot_supply_trusted_devel_or_baseline(self):
        d=deployment('1','assets',sha='s',recipe=fingerprint(),producer='pull_request')
        self.assertEqual(missing_sources({'number':0,'sha':'s'},[d]),['s'])
        self.assertEqual(missing_sources({'number':1,'sha':'head','base_sha':'s'},[d]),['s'])
