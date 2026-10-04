#!/usr/bin/env python3
"""Export PNGs from vector masters. Requires cairosvg; no borrowed raster inputs."""
from pathlib import Path
import xml.etree.ElementTree as ET
import json,copy
import cairosvg
ROOT=Path(__file__).resolve().parents[1]
NS='http://www.w3.org/2000/svg'
ET.register_namespace('',NS)
ET.register_namespace('xlink','http://www.w3.org/1999/xlink')
m=json.loads((ROOT/'manifest.json').read_text())
exports=[]
for size in (64,128,256):
    scale=size/128
    for a in m['assets']:
        source=ROOT/a['path'];w,h=a['viewBox'][2:]
        out=ROOT/'desktop'/str(size)/Path(a['path']).with_suffix('.png')
        out.parent.mkdir(parents=True,exist_ok=True)
        width=max(1,round(w*scale));height=max(1,round(h*scale))
        cairosvg.svg2png(url=str(source),write_to=str(out),output_width=width,output_height=height)
        exports.append({'source':a['path'],'path':str(out.relative_to(ROOT)),'pixel_size':[width,height],
                        'cell_pixels':size,'trim_offset':[0,0],'scale':scale})
    source=ET.parse(ROOT/'robot/robot.svg').getroot()
    for part in [n for n in source if n.get('data-part')]:
        r=copy.deepcopy(source)
        name=part.get('data-part')
        for child in list(r):
            if child.get('data-part') and child.get('data-part')!=name:r.remove(child)
            elif child.get('data-part')==name:child.set('opacity','1')
        out=ROOT/'desktop'/str(size)/'robot-layers'/f'{name}.png';out.parent.mkdir(parents=True,exist_ok=True)
        cairosvg.svg2png(bytestring=ET.tostring(r),write_to=str(out),output_width=size,output_height=size)
        exports.append({'source':'robot/robot.svg','part':name,'path':str(out.relative_to(ROOT)),
                        'pixel_size':[size,size],'cell_pixels':size,'trim_offset':[0,0],'scale':scale,
                        'note':'Full-canvas layer. Visibility forced to 1 for this exported part.'})
(ROOT/'desktop/manifest.json').write_text(json.dumps({'format':'tlfrobot-raster-exports/1','input':'SVG masters only','items':exports},indent=2)+'\n')
print(f'{len(exports)} transparent PNG exports at 64/128/256 pixels per cell.')
