import copy,datetime,json,os,tempfile,unittest
from pathlib import Path
import collect_crash as c
START=1700000000.0
SECRET='PRIVATE_SENTINEL'
def report():
 return {'procName':'com.apple.WebKit.WebContent','pid':123,'captureTime':datetime.datetime.fromtimestamp(START+1,datetime.timezone.utc).isoformat(),'crashReporterKey':SECRET,'procPath':'/Users/'+SECRET+'/WebContent','exception':{'type':'EXC_BAD_ACCESS','signal':'SIGSEGV','rawCodes':[1,2],'subtype':SECRET},'termination':{'namespace':'SIGNAL','code':11,'indicator':SECRET},'faultingThread':0,'threads':[{'id':999,'name':SECRET,'frames':[{'imageIndex':0,'imageOffset':123,'symbol':'WTF::RunLoop::run()','symbolLocation':9,'sourceFile':'/Users/'+SECRET+'/source.cpp'},{'symbol':'https://'+SECRET+'/code'},{'symbol':'/Users/'+SECRET+'/symbol'}]}],'usedImages':[{'path':'/Users/'+SECRET+'/JavaScriptCore','uuid':'12345678-1234-1234-1234-123456789abc','name':'JavaScriptCore','host':SECRET}]}
def write(root,name,body=None,raw=None):
 p=root/name;p.write_bytes(raw if raw is not None else (json.dumps({'bug_type':'309','incident_id':SECRET})+'\n'+json.dumps(body or report())).encode());os.utime(p,(START+1,START+1));return p
class Collector(unittest.TestCase):
 def test_exact_matching_and_privacy_allowlist(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);write(root,'WebContent.ips');out=root/'out';r=c.collect([root],out,START,START+2,{123});self.assertEqual(r['status'],'collected');data=''.join(p.read_text() for p in out.iterdir());self.assertNotIn(SECRET,data);self.assertNotIn('/Users/',data);self.assertNotIn('https:',data);self.assertIn('WTF::RunLoop::run()',data)
 def test_wrong_pid_time_process_never_matches(self):
  for key,value in [('pid',124),('procName','OtherProcess'),('captureTime',datetime.datetime.fromtimestamp(START-1,datetime.timezone.utc).isoformat())]:
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);body=report();body[key]=value;write(root,'WebContent.ips',body);r=c.collect([root],root/'out',START,START+2,{123});self.assertEqual(r['status'],'notfound');self.assertEqual(r['exitCode'],2)
 def test_unsupported_and_oversized_explicit(self):
  for raw,status in [(b'not-json','unsupported'),(b'x'*(c.MAX_BYTES+1),'omitted')]:
   with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp);write(root,'WebContent.ips',raw=raw);r=c.collect([root],root/'out',START,START+2,{123});self.assertEqual(r['status'],status);self.assertNotEqual(r['exitCode'],0)
 def test_three_report_budget_and_symlink_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   for i in range(4):write(root,'WebContent-'+str(i)+'.ips')
   (root/'WebContent-link.ips').symlink_to(root/'WebContent-0.ips');r=c.collect([root],root/'out',START,START+2,{123});self.assertEqual(len(r['reports']),3);self.assertEqual(r['omitted'],1);self.assertEqual(r['status'],'omitted')
 def test_faulting_thread_and_symbol_constraints(self):
  body=report();body['faultingThread']=7
  with self.assertRaises(ValueError):c.sanitize(body,START,START+2,{123})
  for value in ['https://example/path','C:\\Users\\name','file:///tmp/file','fn("secret")','a@b.com','secret.example.com','12345678-1234-1234-1234-123456789abc','asset.swf','save.sol']:
   self.assertIsNone(c.symbol(value))
  self.assertIsNone(c.sanitize(report(),START,START+2,set()))
 def test_no_correlated_pid_never_reads_reports(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);write(root,'WebContent.ips')
   with patch.object(c,'parse',side_effect=AssertionError('must not read')):
    r=c.collect([root],root/'out',START,START+2,set());self.assertEqual(r['reason'],'no-correlated-pid');self.assertEqual(r['exitCode'],2)
 def test_unknown_enums_and_embedded_host_are_omitted(self):
  body=report();body['exception']['type']=SECRET;body['termination']['namespace']=SECRET;body['threads'][0]['frames'][0]['symbol']='secret.example.com';body['usedImages'][0]['name']='private.swf'
  row=c.sanitize(body,START,START+2,{123});text=json.dumps(row);self.assertNotIn(SECRET,text);self.assertNotIn('secret.example.com',text);self.assertNotIn('private.swf',text)
if __name__=='__main__':unittest.main()
