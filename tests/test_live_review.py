import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from core import Board
from live_review import extend_schema, validate_evidence, ui_config_args, device_inventory, live_prompt
from types import SimpleNamespace

class LiveReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def test_code_only_cannot_pass_live_review(self):
        result={'platforms':[{'platform':'web','status':'pass','steps':['read source'],'screenshots':[]}]}
        with self.assertRaises(ValueError):validate_evidence(result,self.root,['web'])
    def test_selected_platforms_must_all_be_present(self):
        result={'platforms':[{'platform':'android','status':'blocked','steps':['No device'],'screenshots':[]}]}
        with self.assertRaises(ValueError):validate_evidence(result,self.root,['android','ios'])
        outcome,files=validate_evidence(result,self.root,['android'])
        self.assertEqual(outcome,'blocked');self.assertEqual(files,[])
    def test_outside_screenshot_is_rejected(self):
        result={'platforms':[{'platform':'web','status':'pass','steps':['clicked'],'screenshots':['../outside.png']}]}
        with self.assertRaises(ValueError):validate_evidence(result,self.root,['web'])
    def test_platform_selection_and_url_persist(self):
        b=Board(self.root,self.root/'state')
        t=b.add({'title':'Open settings','platforms':['web'],'webUrl':'http://localhost:3000'})
        self.assertEqual(Board(self.root,self.root/'state').find(t['id'])['platforms'],['web'])
        for platforms in [[],['invalid'],['web','web']]:
            with self.assertRaises(ValueError):b.add({'title':'x','platforms':platforms})
        with self.assertRaises(ValueError):b.add({'title':'x','webUrl':'https://user:pass@example.com'})
    def test_ui_config_excludes_unrelated_servers(self):
        output=type('Result',(),{'returncode':0,'stdout':json.dumps([{'name':'cua_repl','enabled':True,'transport':{'type':'stdio','command':'fixture'}},{'name':'database','enabled':True}])})()
        with patch('live_review.subprocess.run',return_value=output):args,environment=ui_config_args('codex')
        self.assertFalse(any('database' in arg for arg in args))
        self.assertIn('mcp_servers.cua_repl.command="fixture"',args)

class DeviceInventoryTests(unittest.TestCase):
    def test_connected_unauthorized_and_absent_are_distinct(self):
        outputs=[SimpleNamespace(returncode=0,stdout='List of devices attached\nabc unauthorized\ndef device model:TestPhone\n'),SimpleNamespace(returncode=0,stdout='{"devices":{}}')]
        with patch('live_review.subprocess.run',side_effect=outputs):
            result=device_inventory()
        self.assertEqual(result['android']['status'],'found')
        self.assertEqual(result['android']['devices'][0]['status'],'unauthorized')
        self.assertEqual(result['ios']['status'],'missing')
    def test_tool_failure_is_not_absent_device(self):
        with patch('live_review.subprocess.run',side_effect=OSError('denied')):
            result=device_inventory()
        self.assertEqual(result['android']['status'],'unavailable')
        self.assertEqual(result['ios']['status'],'unavailable')
    def test_review_receives_environment_context(self):
        task={'title':'test','criteria':['screen'],'paths':[], 'reviewContext':'Use test phone', 'deviceInventory':{'android':{'status':'found'}}}
        prompt=live_prompt(task,Path('/tmp'),Path('/tmp/run'),'English')
        self.assertIn('Use test phone',prompt)
        self.assertIn('"status": "found"',prompt)
        self.assertIn('NOT evidence of UI tool access',prompt)
