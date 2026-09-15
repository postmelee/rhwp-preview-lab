import pathlib,tempfile,unittest
from unittest.mock import patch
from prepare import prepare
class Prepare(unittest.TestCase):
    def fixture(self,root):
        source=pathlib.Path(root);public=source/'rhwp-studio/public';public.mkdir(parents=True)
        fonts=source/'assets/fonts';fonts.mkdir(parents=True)
        (fonts/'font.woff2').write_bytes(b'font')
        (public/'fonts').symlink_to(fonts,target_is_directory=True)
        (public/'samples').mkdir();(public/'samples/private.hwp').write_bytes(b'never copy')
        (public/'escape').symlink_to('/etc',target_is_directory=True)
        (fonts/'escape').symlink_to('/etc',target_is_directory=True)
        (public/'favicon.svg').write_text('<svg/>')
        return source
    def test_only_distributable_fonts_and_regular_public_assets(self):
        with tempfile.TemporaryDirectory() as root,patch('prepare.subprocess.check_output',return_value='a'*40):
            source=self.fixture(root);prepare(source,'a'*40)
            public=source/'rhwp-studio/.preview-public'
            self.assertEqual((public/'fonts/font.woff2').read_bytes(),b'font')
            for path in ['samples','escape','fonts/escape']:self.assertFalse((public/path).exists())
            self.assertTrue((public/'favicon.svg').is_file())
    def test_mismatched_checkout_never_prepared(self):
        with tempfile.TemporaryDirectory() as root,patch('prepare.subprocess.check_output',return_value='b'*40):
            source=self.fixture(root)
            with self.assertRaises(ValueError):prepare(source,'a'*40)
            self.assertFalse((source/'rhwp-studio/.preview-public').exists())
