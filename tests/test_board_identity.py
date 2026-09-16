import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from board import resolve_state_dir

class IdentityTests(unittest.TestCase):
    def test_worktree_and_subdirectory_share_registered_board(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();repo=root/'repo';repo.mkdir()
            def git(*args):
                subprocess.run(['git','-C',str(repo),*args],check=True,capture_output=True)
            git('init');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','--allow-empty','-m','initial')
            worktree=root/'worktree';git('worktree','add','-b','parallel',str(worktree))
            state=root/'existing';state.mkdir();(state/'board.json').write_text(json.dumps({'tasks':[{'id':'kept'}]}))
            base=root/'registry'
            self.assertEqual(resolve_state_dir(repo,state,base),state)
            sub=worktree/'app';sub.mkdir()
            self.assertEqual(resolve_state_dir(sub,base=base),state)
            self.assertEqual(json.loads((state/'board.json').read_text())['tasks'][0]['id'],'kept')
            with self.assertRaises(ValueError):resolve_state_dir(worktree,root/'other',base)
            (state/'board.json').unlink()
            with self.assertRaises(ValueError):resolve_state_dir(repo,base=base)
    def test_unrelated_folders_do_not_share(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();a=root/'a';b=root/'b';a.mkdir();b.mkdir()
            self.assertNotEqual(resolve_state_dir(a,base=root/'states'),resolve_state_dir(b,base=root/'states'))
