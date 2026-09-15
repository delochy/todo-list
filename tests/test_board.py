"""Deterministic runner, stale evidence and HTTP guard tests; no AI calls."""
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from board import Board, fingerprint, handler, verdict
from core import translate_payload

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name).resolve()
        self.art=self.root/'answer.txt';self.art.write_text('42')
        self.board=Board(self.root,self.root/'state')
        self.task=self.board.add({'title':'Answer','paths':['answer.txt'],'criteria':['정답이 42다']})
    def tearDown(self):
        self.tmp.cleanup()
    def result(self,status='pass'):
        return {'summary':'Checked','checks':[{'criterion':'정답이 42다','status':status,'evidence':'answer.txt contains 42'}],'findings':[]}
    def test_missing_evidence_never_passes(self):
        r=self.result();r['checks'][0]['evidence']=''
        with self.assertRaises(ValueError):verdict(r,self.task['criteria'])
        r=self.result();r['checks']=[]
        with self.assertRaises(ValueError):verdict(r,self.task['criteria'])
        self.assertEqual(verdict(self.result('blocked'),self.task['criteria']),'blocked')
        self.assertEqual(verdict(self.result('fail'),self.task['criteria']),'changes')
    def test_stale_and_restart(self):
        self.task.update(review='complete',result=self.result(),fingerprint=fingerprint(self.root,self.task['paths']))
        self.board.save();self.art.write_text('43')
        self.assertEqual(self.board.state()['tasks'][0]['review'],'stale')
        self.task['review']='running';self.board.save()
        other=Board(self.root,self.root/'state')
        self.assertEqual(other.find(self.task['id'])['review'],'error')
    def test_title_only(self):
        task=self.board.add({'title':'화면 검수'})
        self.assertEqual(task['paths'],[])
        self.assertTrue(task['criteria'])
        with patch('core.shutil.which',return_value=None):
            self.board.run(task['id'])
        self.assertEqual(task['review'],'blocked')
    def test_discovery_then_review(self):
        task=self.board.add({'title':'Answer','criteria':['정답이 42다']})
        executable=self.root/'fixture-codex'
        code="#!/usr/bin/env python3\nimport sys,json\nfrom pathlib import Path\nsys.stdin.read()\nout=Path(sys.argv[sys.argv.index('-o')+1])\nr="+repr(self.result())+"\nif out.name=='discovery.json':r={'paths':['answer.txt'],'reason':'정답 파일'}\nout.write_text(json.dumps(r))\n"
        executable.write_text(code);executable.chmod(0o700)
        with patch('core.shutil.which',return_value=str(executable)):
            self.board.run(task['id'])
        self.assertEqual(task['paths'],['answer.txt'])
        self.assertEqual(task['review'],'complete')
    def test_rename_persists(self):
        self.board.rename('VEIL 할 일')
        other=Board(self.root,self.root/'state')
        self.assertEqual(other.state()['name'],'VEIL 할 일')
        with self.assertRaises(ValueError):self.board.rename(' ')
    def test_multiple_requests_queue(self):
        second=self.board.add({'title':'Second','paths':['answer.txt'],'criteria':['정답이 42다']})
        self.board.status(self.task['id'],'done');self.board.status(second['id'],'done')
        entered=threading.Event();release=threading.Event();calls=[]
        def runner(task_id):
            calls.append(task_id);entered.set();release.wait(3)
            with self.board.lock:self.board.find(task_id)['review']='complete'
        with patch.object(self.board,'run',side_effect=runner):
            self.board.review(self.task['id'],mode='code');self.assertTrue(entered.wait(1))
            self.board.review(second['id']);self.assertEqual(second['review'],'queued')
            with self.assertRaises(ValueError):self.board.review(second['id'])
            release.set()
            deadline=time.time()+3
            while second['review']!='complete' and time.time()<deadline:time.sleep(.02)
        self.assertEqual(calls,[self.task['id'],second['id']])
    def test_project_change_invalidates_scopes(self):
        other=self.root/'actual-app';other.mkdir();(other/'code.py').write_text('x=1')
        self.task.update(review='complete',result=self.result())
        self.board.configure(str(other))
        self.assertEqual(self.task['review'],'stale')
        self.assertEqual(self.task['paths'],[])
        self.assertEqual(Board(self.root,self.root/'state').project,other)
    def test_request_preserves_work_state(self):
        with patch.object(self.board,'run_queued'):
            self.board.review(self.task['id'],mode='code')
        self.assertEqual(self.task['work'],'todo')
        self.assertEqual(self.task['review'],'queued')
    def test_malformed_result_is_not_complete(self):
        r=self.result();r['checks']=[None]
        with self.assertRaises(ValueError):verdict(r,self.task['criteria'])
    def test_outside_symlink_and_secret_rejected(self):
        outside=Path(tempfile.mkdtemp());target=outside/'code.py';target.write_text('x')
        try:
            (self.root/'link.py').symlink_to(target)
            with self.assertRaises(ValueError):fingerprint(self.root,['link.py'])
            (self.root/'.env').write_text('placeholder')
            with self.assertRaises(ValueError):fingerprint(self.root,['.env'])
        finally:
            target.unlink();outside.rmdir()
    def test_shutdown_rejects_new_requests(self):
        self.board.shutdown()
        with self.assertRaises(ValueError):self.board.review(self.task['id'],mode='code')
    def test_review_language_is_snapshotted(self):
        with patch.object(self.board,'run_queued'):
            self.board.review(self.task['id'],'en')
        self.assertEqual(self.task['language'],'en')
        with self.assertRaises(ValueError):self.board.review(self.task['id'],'xx')
    def test_translation_preserves_user_report(self):
        data={'message':'검수 이후 대상 파일이 바뀌었습니다.','title':'할 일','result':{'summary':'할 일'}}
        english=translate_payload(data,'en')
        self.assertEqual(english['message'],'Files changed since the last review.')
        self.assertEqual(english['title'],'할 일')
        self.assertEqual(english['result']['summary'],'할 일')
    def test_english_default_criterion(self):
        task=self.board.add({'title':'Check login','language':'en'})
        self.assertIn('artifacts satisfy',task['criteria'][0])
    def test_idea_conversion_preserves_content(self):
        idea=self.board.add({'kind':'note','title':'Later','note':'Detailed idea','platforms':['web']})
        with self.assertRaises(ValueError):self.board.review(idea['id'])
        task=self.board.add({'kind':'task','title':idea['title'],'note':idea['note'],'platforms':['web']},idea['id'])
        self.assertEqual(task['id'],idea['id'])
        self.assertEqual(task['kind'],'task')
        self.assertEqual(task['note'],'Detailed idea')
        self.assertEqual(task['review'],'pending')
    def test_delete_and_restore(self):
        self.board.archive(self.task['id'],True)
        self.assertTrue(self.task['deletedAt'])
        with self.assertRaises(ValueError):self.board.review(self.task['id'])
        self.board.archive(self.task['id'],False)
        self.assertIsNone(self.task['deletedAt'])
        self.assertTrue(self.art.exists())
    def test_scope_guards(self):
        for p in ['.','../outside','state']:
            with self.assertRaises(ValueError):self.board.add({'title':'x','criteria':['y'],'paths':[p]})
    def test_edit_invalidates_review(self):
        self.task.update(review='complete',result=self.result(),work='done')
        updated=self.board.add({'title':'Edited','paths':['answer.txt'],'criteria':['새 조건']},self.task['id'])
        self.assertEqual(updated['review'],'pending')
        self.assertEqual(updated['work'],'todo')
        self.assertEqual(len(updated['history']),1)
        self.assertIsNone(updated['result'])
    def test_real_process_pipeline_with_fixture(self):
        executable=self.root/'fixture-codex'
        executable.write_text('#!/usr/bin/env python3\nimport json,sys,time\nfrom pathlib import Path\nsys.stdin.read()\ntime.sleep(.2)\nPath(sys.argv[sys.argv.index("-o")+1]).write_text('+repr(json.dumps(self.result()))+')\n')
        executable.chmod(0o700)
        self.board.status(self.task['id'],'done')
        with patch('core.shutil.which',return_value=str(executable)):
            self.board.review(self.task['id'],mode='code')
            self.assertIn(self.task['review'],('queued','running'))
            with self.assertRaises(ValueError):self.board.review(self.task['id'],mode='code')
            deadline=time.time()+5
            while self.task['review'] in ('queued','running') and time.time()<deadline:time.sleep(.03)
        self.assertEqual(self.task['review'],'complete')
        self.assertTrue(self.task['finished'])
    def test_changed_during_review(self):
        executable=self.root/'fixture-codex'
        executable.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\nsys.stdin.read()\nPath('+repr(str(self.art))+').write_text("43")\nPath(sys.argv[sys.argv.index("-o")+1]).write_text('+repr(json.dumps(self.result()))+')\n')
        executable.chmod(0o700);self.board.status(self.task['id'],'done')
        with patch('core.shutil.which',return_value=str(executable)):
            self.board.run(self.task['id'])
        self.assertEqual(self.task['review'],'stale')
    def test_http_requires_token_and_same_origin(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),handler(self.board,'secret'))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url=f'http://127.0.0.1:{server.server_port}'
        try:
            with self.assertRaises(HTTPError):urlopen(url+'/api/state')
            req=Request(url+'/api/state',headers={'X-Board-Token':'secret'})
            self.assertEqual(len(json.loads(urlopen(req).read())['tasks']),1)
            req=Request(url+'/api/review',data=b'{}',headers={'X-Board-Token':'secret','Origin':'https://example.com'})
            with self.assertRaises(HTTPError) as e:urlopen(req)
            self.assertEqual(e.exception.code,403)
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main()
