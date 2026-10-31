import json,sys
r=json.load(open(sys.argv[1]));summary={'passed':r['passed'],'scope':r['scope'],'rows':[]}
for row in r['rows']:
 out={'case':row['case'],'states':[],'failure':row.get('failure')}
 for s in row['states']:
  gl=s['gl'];ids={e['texture'] for e in gl['events'] if e.get('width')==512 and e.get('height')==512 and e.get('sourceKind')=='view' and e.get('sourceViewByteLength')==1048576 and e.get('expectedRequestRGBA8Bytes')==1048576 and e['name']=='texImage2D'}
  tex=[t for t in gl['textures'] if t['id'] in ids]
  pending=[t for t in tex if not t['deleteRequested']]
  out['states'].append({'label':s['label'],'wasmPages':[m.get('pages') for m in s['memories']],'actualTargetRGBAUploadTextureIds':len(ids),'targetDeleteRequestedUnique':sum(t['deleteRequested'] for t in tex),'targetWithoutDeleteRequest':len(pending),'expectedTargetBaseRGBA8BytesWithoutDeleteRequest':sum(t['expectedBaseRGBA8Bytes'] or 0 for t in pending),'allTextureSummary':gl['summary'],'totalTargetTexImageCalls':sum(e.get('texture') in ids and e['name']=='texImage2D' for e in gl['events'])})
 summary['rows'].append(out)
print(json.dumps(summary,indent=2))
