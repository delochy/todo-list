import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('installer',Path(__file__).resolve().parents[1]/'install.py')
installer=importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallTests(unittest.TestCase):
    def test_clean_install_and_update_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            destination=Path(directory)/'skill'
            installed,backup=installer.install(destination)
            self.assertIsNone(backup)
            self.assertTrue((installed/'scripts/core.py').is_file())
            (installed/'local-note.txt').write_text('preserve me')
            installed,backup=installer.install(destination)
            self.assertEqual((backup/'local-note.txt').read_text(),'preserve me')
            self.assertFalse((installed/'local-note.txt').exists())
