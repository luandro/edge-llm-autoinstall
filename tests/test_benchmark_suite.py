"""Offline, dependency-free smoke tests for benchmark logic and HTTP report output."""
import contextlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import benchmark_suite as bench

class Dummy(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers()
        self.wfile.write(b'{"data":[{"id":"edge-llm"}]}')
    def do_POST(self):
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))))
        text=(body.get('messages') or [{}])[-1].get('content','')
        calls=[]
        if text.startswith('Read the existing file '):
            calls=[{'id':'1','type':'function','function':{'name':'read_file','arguments':json.dumps({'path':'/workspace/notes/meeting.md'})}}]
        resp={'choices':[{'message':{'role':'assistant','content':'OK','tool_calls':calls},'finish_reason':'tool_calls' if calls else 'stop'}],
              'usage':{'prompt_tokens':30,'completion_tokens':12},'timings':{'prompt_per_second':30,'predicted_per_second':8}}
        result=json.dumps(resp).encode()
        self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(result)));self.end_headers();self.wfile.write(result)

class TestBench(unittest.TestCase):
    def test_case_bank(self):
        self.assertEqual(len(bench.CASES),40)
        self.assertEqual(sum(c.get('quick',False) for c in bench.CASES),11)
        self.assertEqual(len({c['id'] for c in bench.CASES}),40)
    def test_catalog(self):
        self.assertEqual(bench.models_for('small'),['qwen08','botpsy','mini_agent','qwen2b'])
        self.assertIn('lfm3_hermes',bench.models_for('adapter'))
    def test_score(self):
        a=next(c for c in bench.CASES if c['id']=='tool-read')
        row={'tool_calls':[{'function':{'name':'read_file','arguments':'{"path":"/workspace/notes/meeting.md"}'}}]}
        self.assertTrue(bench.score_case(a,row)['correct'])
        self.assertFalse(bench.score_case(a,{'tool_calls':[]})['correct'])
        self.assertEqual(bench.char_f_score('rio','rio'),1.0)
    def test_http_and_reports(self):
        srv=HTTPServer(('127.0.0.1',0),Dummy)
        thread=threading.Thread(target=srv.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as td:
                rc=bench.main(['--server-url',f'http://127.0.0.1:{srv.server_address[1]}','--suite','quick','--runs','1','--output-dir',td])
                self.assertEqual(rc,0)
                data=json.loads((Path(td)/'results.json').read_text())
                self.assertEqual(len(data['models']['current_server']['cases']),11)
                self.assertTrue((Path(td)/'comparison.csv').exists())
                self.assertTrue((Path(td)/'comparison.md').exists())
        finally:
            srv.shutdown();srv.server_close()

if __name__=='__main__':unittest.main()