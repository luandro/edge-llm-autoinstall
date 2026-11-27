import http.server
import json
import pathlib
import subprocess
import sys
import threading
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts/edge-task.py"
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        if self.path == "/v1/models":
            self.reply({"data":[{"id":"fixture"}]})
        else:
            self.send_error(404)
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.body = body
        if self.server.redirect:
            self.send_response(302)
            self.send_header("Location","http://127.0.0.1:1/no")
            self.end_headers()
            return
        self.reply({"choices":[{"message":{"content":"A reunião será sexta-feira."},"finish_reason":"stop"}]})
    def reply(self, body):
        data=json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type","application/json")
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)
class EdgeTaskTest(unittest.TestCase):
    def setUp(self):
        self.server=http.server.HTTPServer(("127.0.0.1",0),Handler)
        self.server.redirect=False
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
    def call(self,*args):
        return subprocess.run([sys.executable,str(SCRIPT),*args,"--port",str(self.server.server_port)],
                              text=True,capture_output=True,timeout=15)
    def test_health(self):
        out=self.call("health")
        self.assertEqual(out.returncode,0,out.stderr)
        self.assertIn("fixture",out.stdout)
    def test_translation(self):
        out=self.call("pt","The meeting is Friday.")
        self.assertEqual(out.returncode,0,out.stderr)
        self.assertIn("sexta-feira",out.stdout)
        self.assertEqual(self.server.body["model"],"fixture")
        self.assertEqual(self.server.body["messages"][1]["content"],"The meeting is Friday.")
    def test_redirect_rejected(self):
        self.server.redirect=True
        out=self.call("pt","test")
        self.assertNotEqual(out.returncode,0)
        self.assertIn("302",out.stderr)
if __name__=="__main__":
    unittest.main()
