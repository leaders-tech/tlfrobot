#!/usr/bin/env python3
"""Validate real vector contents, required part IDs, references, counts and export manifests."""
from pathlib import Path
import json,re,hashlib
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
NS='{http://www.w3.org/2000/svg}'
REQUIRED={'body','drive','heading','sensor','gripper-base','gripper-left','gripper-right','roller','eraser','cargo-hatch','eyes','eyelids','shadow'}
CONTROL={'play','pause','stop','step','reset','history-back','history-forward','speed','zoom-in','zoom-out','fit','settings'}
FORBIDDEN={'image','script','foreignObject','filter','style','text','animate','animateMotion','animateTransform','set'}
manifest=json.loads((ROOT/'manifest.json').read_text());errors=[];results=[]
for asset in manifest['assets']:
    p=ROOT/asset['path'];r=ET.parse(p).getroot();raw=p.read_text()
    if r.tag!=NS+'svg':errors.append(f'{p.name}: root is not svg')
    if r.get('viewBox') is None:errors.append(f'{p.name}: no viewBox')
    ids=[n.get('id') for n in r.iter() if n.get('id')]
    if len(set(ids))!=len(ids):errors.append(f'{p.name}: duplicate IDs')
    for n in r.iter():
        tag=n.tag.rsplit('}',1)[-1]
        if tag in FORBIDDEN:errors.append(f'{p.name}: forbidden {tag}')
        for k,v in n.attrib.items():
            k=k.rsplit('}',1)[-1]
            if k.lower().startswith('on'):errors.append(f'{p.name}: event handler {k}')
            if 'data:image' in v.lower() or 'base64,' in v.lower():errors.append(f'{p.name}: embedded raster')
            if k=='href' and (not v.startswith('#') or v[1:] not in ids):errors.append(f'{p.name}: invalid/external href {v}')
            for reference in re.findall(r'url\(#([^)]+)\)',v):
                if reference not in ids:errors.append(f'{p.name}: unknown local ref {reference}')
    results.append({'path':asset['path'],'bytes':p.stat().st_size,'elements':sum(1 for _ in r.iter()),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
if {str(p.relative_to(ROOT)) for p in ROOT.rglob('*.svg')}!={a['path'] for a in manifest['assets']}:errors.append('unlisted SVG or missing listed SVG')
robot=ET.parse(ROOT/'robot/robot.svg').getroot()
parts={n.get('data-part') for n in robot.iter() if n.get('data-part')}
if not REQUIRED<=parts:errors.append('missing required robot groups: '+str(REQUIRED-parts))
controls=ET.parse(ROOT/'ui/controls.svg').getroot()
if {n.get('id') for n in controls.iter(NS+'symbol')}!=CONTROL:errors.append('control symbol mismatch')
counts={key:sum(a['scope']==key for a in manifest['assets']) for key in ['R1','art-reserve','derived-control']}
if counts!={'R1':22,'art-reserve':3,'derived-control':12}:errors.append('inventory counts mismatch')
clips=json.loads((ROOT/'animation/clips.json').read_text())['items']
if len(clips)!=20 or len({c['key'] for c in clips})!=20:errors.append('clip inventory mismatch')
raster=json.loads((ROOT/'desktop/manifest.json').read_text())['items']
for item in raster:
    p=ROOT/item['path']
    if not p.exists() or p.read_bytes()[:8]!=b'\x89PNG\r\n\x1a\n':errors.append('missing or invalid raster export '+str(p))
report={'status':'passed' if not errors else 'failed','svg_files':len(results),'required_svg_masters':counts['R1'],'reserve_svg_masters':counts['art-reserve'],'derived_control_svgs':counts['derived-control'],'embedded_raster_images':0 if not any('raster' in e for e in errors) else 'error','svg_scripts':0 if not any('script' in e for e in errors) else 'error','desktop_png_exports':len(raster),'animation_preview_templates':len(clips),'errors':errors,'files':results,'test_scope':'XML and content validation. Runtime adapter integration is outside this test.'}
(ROOT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='files'},indent=2))
if errors:raise SystemExit(1)
