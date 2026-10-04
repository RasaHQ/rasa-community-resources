"""Production SDK requests against an in-process fake provider. No external requests."""
from pathlib import Path
import asyncio,json,os,sys,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
name=sys.argv[1];HERE=Path(__file__).resolve().parent;T=HERE.parents[1]
rows=[]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  rows.append({'path':self.path,'body':body})
  text='Please tell me your full name and date of birth.'
  item={'type':'message','id':'msg_offline','role':'assistant','status':'completed','content':[{'type':'output_text','text':text,'annotations':[]}]}
  response={'id':'resp_offline','object':'response','created_at':int(time.time()),'model':body['model'],'status':'completed','output':[item],'usage':{'input_tokens':100,'output_tokens':12,'total_tokens':112,'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}},'error':None,'incomplete_details':None}
  if body.get('stream'):
   events=[{'type':'response.created','response':{**response,'output':[]}},
    {'type':'response.output_item.added','output_index':0,'item':{**item,'content':[]}},
    {'type':'response.content_part.added','output_index':0,'content_index':0,'item_id':item['id'],'part':{'type':'output_text','text':'','annotations':[]}},
    {'type':'response.output_text.delta','output_index':0,'content_index':0,'item_id':item['id'],'delta':text},
    {'type':'response.output_text.done','output_index':0,'content_index':0,'item_id':item['id'],'text':text},
    {'type':'response.output_item.done','output_index':0,'item':item},
    {'type':'response.completed','response':response}]
   payload=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode();ctype='text/event-stream'
  else:payload=json.dumps(response).encode();ctype='application/json'
  self.send_response(200);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 def do_GET(self):
  payload=b'{}';self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
os.environ.update(OPENAI_API_KEY='offline-test',OPENAI_BASE_URL=f'http://127.0.0.1:{server.server_port}/v1',OPENAI_API_BASE=f'http://127.0.0.1:{server.server_port}/v1',AGNO_TELEMETRY='false',CREWAI_TELEMETRY_DISABLED='true',OTEL_SDK_DISABLED='true')
sys.path.insert(0,str(T/name))
import agent
from cedar_clinic import tools as clinic
async def main():
 c=agent.Conversation('production-sdk-offline')
 async def turn():return [s async for s in c.turn('Hello')]
 said=await asyncio.wait_for(turn(),15)
 assert any(s.kind=='end' and 'full name' in s.text for s in said),[(s.kind,s.text) for s in said]
 if hasattr(c,'close'):await c.close()
try:
 asyncio.run(main())
 assert rows
 for row in rows:
  body=row['body'];assert row['path']=='/v1/responses',row['path']
  assert body['model']=='gpt-5.5-2026-04-23'
  assert body['reasoning']['effort']=='low',body.get('reasoning')
  assert body.get('store') is False,body.get('store')
  assert body.get('parallel_tool_calls') is False,body.get('parallel_tool_calls')
  schemas={t['name']:t['parameters'] for t in body['tools']}
  assert schemas=={n:clinic.json_schema(n)['parameters'] for n in clinic.TOOL_SPECS},schemas
 receipt={'framework':name,'mode':'production SDK against localhost fake provider; no model spend',
  'requests':len(rows),'path':rows[0]['path'],'model':rows[0]['body']['model'],
  'reasoning':rows[0]['body']['reasoning'],'store':False,'parallel_tool_calls':False,
  'tool_schemas_match':True,'output_stream_checked':True}
 output=T/'results'/name/'offline-contract-20261003';output.mkdir(parents=True,exist_ok=True)
 (output/'provider-contract.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
finally:server.shutdown();server.server_close()
