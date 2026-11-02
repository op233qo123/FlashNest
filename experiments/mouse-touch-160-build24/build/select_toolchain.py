#!/usr/bin/env python3
"""Select only an installed, explicitly supported Xcode/SDK/runtime tuple."""
import argparse,json,os,subprocess
from pathlib import Path
SUPPORTED=[('16.4','18.5')]
def cmd(args,env):return subprocess.check_output(args,env=env,text=True,stderr=subprocess.STDOUT,timeout=90).strip()
def select(output):
 inspected=[]
 for version,sdk in SUPPORTED:
  developer=Path('/Applications')/('Xcode_'+version+'.app')/'Contents/Developer'
  if not developer.is_dir():inspected.append({'xcode':version,'installed':False});continue
  env=dict(os.environ,DEVELOPER_DIR=str(developer))
  try:
   actual=cmd(['xcodebuild','-version'],env);device_sdk=cmd(['xcrun','--sdk','iphoneos','--show-sdk-version'],env);sim_sdk=cmd(['xcrun','--sdk','iphonesimulator','--show-sdk-version'],env)
   runtimes=json.loads(cmd(['xcrun','simctl','list','runtimes','--json'],env));types=json.loads(cmd(['xcrun','simctl','list','devicetypes','--json'],env))
   inspected.append({'developerDir':str(developer),'xcode':actual,'deviceSDK':device_sdk,'simulatorSDK':sim_sdk,'runtimes':runtimes,'deviceTypes':types})
   if actual.splitlines()[0]!='Xcode '+version or device_sdk!=sdk or sim_sdk!=sdk:continue
   matches=[r for r in runtimes['runtimes'] if r.get('isAvailable') is True and r.get('version')==sdk and r['identifier'].startswith('com.apple.CoreSimulator.SimRuntime.iOS-')]
   if len(matches)!=1:continue
   runtime=matches[0];supported={d['identifier'] for d in runtime.get('supportedDeviceTypes',[])};available={d['identifier'] for d in types['devicetypes']}
   device=next((d for d in ['com.apple.CoreSimulator.SimDeviceType.iPhone-SE-3rd-generation','com.apple.CoreSimulator.SimDeviceType.iPhone-16'] if d in available and (not supported or d in supported)),None)
   if not device:continue
   result={'schema':1,'developerDir':str(developer),'xcodeVersion':version,'xcodeBuild':actual,'deviceSDK':sdk,'simulatorSDK':sdk,'runtimeID':runtime['identifier'],'runtimeVersion':runtime['version'],'deviceTypeID':device,'inspected':inspected,'sdkChangedFromPrior18_2':sdk!='18.2','head':os.environ['GITHUB_SHA'],'runID':os.environ['GITHUB_RUN_ID']}
   output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2)+'\n')
   with open(os.environ['GITHUB_ENV'],'a') as f:f.write('DEVELOPER_DIR='+str(developer)+'\n')
   print('Selected installed Xcode',version,'iOS SDK/runtime',sdk,'device',device);return
  except (subprocess.CalledProcessError,subprocess.TimeoutExpired,ValueError,KeyError) as err:inspected.append({'xcode':version,'error':str(err)})
 output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps({'selectionFailed':True,'inspected':inspected},indent=2)+'\n')
 raise RuntimeError('No installed supported Xcode+SDK+available runtime tuple; no SDK download or silent fallback')
def verify(path):
 t=json.loads(Path(path).read_text());assert (t['xcodeVersion'],t['deviceSDK']) in SUPPORTED
 assert t['head']==os.environ['GITHUB_SHA'] and t['runID']==os.environ['GITHUB_RUN_ID']
 assert os.environ.get('DEVELOPER_DIR')==t['developerDir']
 assert cmd(['xcodebuild','-version'],os.environ)==t['xcodeBuild']
 assert cmd(['xcrun','--sdk','iphoneos','--show-sdk-version'],os.environ)==t['deviceSDK']
 assert cmd(['xcrun','--sdk','iphonesimulator','--show-sdk-version'],os.environ)==t['simulatorSDK']==t['runtimeVersion']
 return t
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();select(a.output)
