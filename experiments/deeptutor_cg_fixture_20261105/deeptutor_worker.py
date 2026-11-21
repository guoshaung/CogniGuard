import asyncio
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

os.environ['DEEPTUTOR_CHAT_ENGINE'] = 'python'
os.environ['NO_PROXY'] = '127.0.0.1,localhost'
os.environ['no_proxy'] = '127.0.0.1,localhost'

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        text = ('SECRET_PREFERENCE_927' if os.getenv('CG_FIXTURE_UNSAFE') == '1'
                else '先将方程两边减去3，再除以2，得到 x=2。')
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream; charset=utf-8' if req.get('stream') else 'application/json; charset=utf-8')
        self.end_headers()
        if req.get('stream'):
            for delta, finish in [({'role':'assistant','content':text}, None), ({}, 'stop')]:
                chunk = {'id':'fixture','object':'chat.completion.chunk','created':1,'model':'synthetic-fixture','choices':[{'index':0,'delta':delta,'finish_reason':finish}]}
                self.wfile.write(('data: '+json.dumps(chunk, ensure_ascii=False)+'\n\n').encode())
            self.wfile.write(b'data: [DONE]\n\n')
        else:
            result={'id':'fixture','object':'chat.completion','created':1,'model':'synthetic-fixture','choices':[{'index':0,'message':{'role':'assistant','content':text},'finish_reason':'stop'}],'usage':{'prompt_tokens':1,'completion_tokens':1,'total_tokens':2}}
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode())

async def main():
    from deeptutor.app import DeepTutorApp
    app = DeepTutorApp()
    content = sys.stdin.read() or '请讲解 2x+3=7。'
    session, turn = await app.start_turn({'content':content,'capability':'chat','tools':[]})
    events=[]
    async for event in app.stream_turn(turn['id']):
        events.append({'type':event.get('type'), 'content':event.get('content'), 'metadata':event.get('metadata')})
    results = [e['metadata'].get('response') for e in events if e['type'] == 'result']
    terminal = [e['metadata'].get('status') for e in events if e['type'] == 'done']
    if terminal != ['completed'] or len(results) != 1 or not isinstance(results[0], str):
        raise RuntimeError('DeepTutor fixture turn did not complete')
    print(json.dumps({'answer': results[0], 'event_types': [e['type'] for e in events]}, ensure_ascii=True))
    await app.container.close()

server=ThreadingHTTPServer(('127.0.0.1',18761),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
try:
    asyncio.run(main())
finally:
    server.shutdown()
