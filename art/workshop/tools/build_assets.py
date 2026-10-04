#!/usr/bin/env python3
"""Rebuild the original Timo workshop SVG masters. Python standard library only."""
from pathlib import Path
import json
import math
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://www.w3.org/2000/svg'
XLINK = 'http://www.w3.org/1999/xlink'
ET.register_namespace('', NS)
ET.register_namespace('xlink', XLINK)
P = {
    'outline': '#21364B', 'body': '#F8F6EE', 'body-shade': '#CCDCE2',
    'frame': '#537486', 'accent': '#367FC1', 'accent-light': '#A3DEE9',
    'accent-pale': '#E3F3F6', 'paint': '#F2B24F', 'paint-light': '#F7D894',
    'paint-shade': '#BE833A', 'screen': '#21364B', 'eye': '#B8EEF2',
    'white': '#FFFFFF', 'quiet': '#DFE8EC', 'muted': '#7E94A2',
    'positive': '#38846E', 'positive-light': '#D4EEE2',
    'negative': '#667C91', 'negative-light': '#E6EDF3',
    'error': '#C1664F', 'error-light': '#F9E4D5',
    'crystal': '#41A9D1', 'crystal-light': '#B9EEF2', 'crystal-shade': '#3476B8',
}

def E(tag, **attrs):
    e = ET.Element('{%s}%s' % (NS, tag))
    for k, v in attrs.items():
        if v is not None:
            e.set(k.replace('_', '-'), str(v))
    return e

def add(parent, tag, **attrs):
    e = E(tag, **attrs); parent.append(e); return e

def part(parent, name, **attrs):
    return add(parent, 'g', id=name, data_part=name, **attrs)

def shape(parent, tag, fill=None, stroke=None, sw=2.5, **attrs):
    if fill:
        attrs['fill'] = P.get(fill, fill)
        if fill in P: attrs['data_fill_role'] = fill
    else: attrs['fill'] = 'none'
    if stroke:
        attrs['stroke'] = P.get(stroke, stroke)
        attrs['stroke_width'] = sw
        attrs['stroke_linecap'] = 'round'
        attrs['stroke_linejoin'] = 'round'
        if stroke in P: attrs['data_stroke_role'] = stroke
    return add(parent, tag, **attrs)

def path(parent, d, fill=None, stroke=None, sw=2.5, **a):
    return shape(parent, 'path', fill, stroke, sw, d=d, **a)
def rect(parent,x,y,w,h,fill=None,stroke=None,sw=2.5,rx=0,**a):
    return shape(parent,'rect',fill,stroke,sw,x=x,y=y,width=w,height=h,rx=rx,**a)
def circle(parent,x,y,r,fill=None,stroke=None,sw=2.5,**a):
    return shape(parent,'circle',fill,stroke,sw,cx=x,cy=y,r=r,**a)
def ellipse(parent,x,y,rx,ry,fill=None,stroke=None,sw=2.5,**a):
    return shape(parent,'ellipse',fill,stroke,sw,cx=x,cy=y,rx=rx,ry=ry,**a)
def line(parent,x1,y1,x2,y2,stroke='outline',sw=2.5,**a):
    return shape(parent,'line',None,stroke,sw,x1=x1,y1=y1,x2=x2,y2=y2,**a)

def doc(title,w=64,h=64):
    r=E('svg',viewBox=f'0 0 {w} {h}',width=w,height=h,role='img',data_theme='workshop')
    add(r,'title').text=title
    add(r,'desc').text='Original Timo workshop vector artwork. Geometric paths and shapes only; no raster images.'
    return r

assets=[]
def save(r,name,aid,title,anchors=None,scope='R1'):
    p=ROOT/name; p.parent.mkdir(parents=True,exist_ok=True)
    ET.indent(r,space='  ')
    ET.ElementTree(r).write(p,encoding='utf-8',xml_declaration=True)
    assets.append(dict(id=aid,path=name,title=title,scope=scope,viewBox=list(map(float,r.get('viewBox').split())),
                       parts=[e.get('data-part') for e in r.iter() if e.get('data-part')],anchors=anchors or {}))

# A01: circular, omnidirectional rover. The face stays upright; the explicit pointer defines heading.
r=doc('Timo — workshop rover, layered master',128,128)
g=part(r,'shadow'); circle(g,64,64,44,'outline',opacity='.10')
g=part(r,'drive')
circle(g,64,64,41,'frame','outline',3)
# Four diagonal drive pods avoid a misleading forward-facing wheel layout.
for i,angle in enumerate((45,135,225,315)):
    pod=part(g,f'drive-pod-{i}',transform=f'rotate({angle} 64 64)')
    rect(pod,53,19,22,16,'outline',rx=7)
    rect(pod,56,21,16,10,'frame',rx=4)
    line(pod,60,22,60,29,'body-shade',1.5);line(pod,65,22,65,29,'body-shade',1.5)
    line(pod,70,23,70,28,'body-shade',1.5)
circle(g,64,64,36.5,'accent','outline',2.5)
g=part(r,'body')
circle(g,64,64,35,'body','outline',2.5)
path(g,'M 31 73 A 35 35 0 0 0 97 73 C 91 84 79 91 64 91 C 49 91 37 84 31 73 Z','body-shade')
path(g,'M 41 39 C 49 32 58 29 68 30',None,'white',3.5)
# A curved band and round tool sockets give the little rover a workshop identity.
path(g,'M 33 74 Q 64 90 95 74',None,'accent',4)
circle(g,30,64,5.5,'paint','outline',2)
circle(g,98,64,5.5,'accent-light','outline',2)
line(g,30,62,30,66,'outline',1.5);line(g,96,64,100,64,'outline',1.5)
rect(g,39,41,50,37,'screen','outline',2,rx=14)
path(g,'M 44 47 Q 47 44 54 44',None,'frame',2)
# All expressions are separate small parts, not direction-specific robot drawings.
g=part(r,'eyes')
for cx,n in [(53,'left'),(75,'right')]:
    eg=part(g,'eye-'+n)
    ellipse(eg,cx,57,6,8,'eye')
    ellipse(eg,cx+1.5,57,2.3,4.5,'screen')
    circle(eg,cx-1,53,1.5,'white')
path(g,'M 60 69 Q 64 72 68 69',None,'eye',2.2)
g=part(r,'eyelids',opacity=0)
rect(g,44,47,40,20,'screen',rx=8)
path(g,'M 48 58 Q 53 54 58 58 M 70 58 Q 75 54 80 58',None,'eye',2.5)
g=part(r,'cargo-hatch')
path(g,'M 49 84 Q 64 90 79 84 L 76 98 Q 64 103 52 98 Z','paint','outline',2.5)
path(g,'M 55 89 Q 64 92 73 89',None,'paint-light',2)
rect(g,61,90,6,6,'accent','outline',1.4,rx=2)
g=part(r,'heading')
path(g,'M 64 6 L 74 21 L 64 17 L 54 21 Z','paint','outline',2.5)
g=part(r,'sensor')
line(g,64,37,64,29,'outline',5)
rect(g,56,21,16,12,'body','outline',2,rx=5)
circle(g,64,26,3.7,'accent-light','outline',1.6)
circle(g,64,25,1.1,'white')
# Tools use opacity rather than display:none, so exported layers retain measurable bounds.
g=part(r,'gripper-base',opacity=0)
path(g,'M 91 83 L 98 92 L 105 100',None,'outline',7)
path(g,'M 91 83 L 98 92 L 105 100',None,'body-shade',3.5)
circle(g,98,92,3.3,'accent','outline',1.6)
g=part(r,'gripper-left',opacity=0)
path(g,'M 105 99 L 101 107 L 105 112',None,'outline',4)
path(g,'M 105 99 L 101 107 L 105 112',None,'paint',1.8)
g=part(r,'gripper-right',opacity=0)
path(g,'M 106 99 L 115 102 L 117 107',None,'outline',4)
path(g,'M 106 99 L 115 102 L 117 107',None,'paint',1.8)
g=part(r,'roller',opacity=0)
path(g,'M 88 84 L 94 94 L 107 94 L 107 101',None,'outline',4)
rect(g,92,99,29,11,'paint','outline',2.5,rx=4)
line(g,97,101,113,101,'paint-light',2)
rect(g,86,80,6,12,'accent','outline',1.8,rx=2,transform='rotate(-30 89 86)')
g=part(r,'eraser',opacity=0)
path(g,'M 89 85 L 102 100',None,'outline',5)
rect(g,98,96,22,15,'body','outline',2.5,rx=4,transform='rotate(-25 109 103.5)')
path(g,'M 100 110 L 119 102 L 119 108 L 103 115 Z','accent','outline',1.5)
save(r,'robot/robot.svg','A01','Timo robot',
     dict(pivot=[64,64],cargo=[64,92],probe_origin=[64,26],sensor_pivot=[64,64],tool_mount=[91,83],
          grip_contact=[109,107],paint_contact=[107,106],erase_contact=[109,106],
          cell_object=[111,109],badge_region=[99,115,27,12]))

r=doc('Crystal component')
g=part(r,'crystal')
path(g,'M 32 5 L 48 20 L 51 39 L 32 59 L 13 39 L 16 20 Z','crystal','outline',2.5)
path(g,'M 32 5 L 32 59 L 13 39 L 16 20 Z','crystal-light')
path(g,'M 32 5 L 39 26 L 51 39 L 32 59 Z','crystal-shade')
path(g,'M 16 20 L 25 26 L 32 5 M 13 39 L 25 26 L 32 59 M 25 26 L 39 26 L 48 20',None,'white',1.8)
path(g,'M 32 5 L 48 20 L 51 39 L 32 59 L 13 39 L 16 20 Z',None,'outline',2.5)
save(r,'world/crystal.svg','A02','Crystal',{'centre':[32,32],'grip':[32,16]})

r=doc('Paint coating for one cell',128,128)
g=part(r,'paint')
rect(g,3,3,122,122,'paint-light',rx=5)
rect(g,5,5,118,118,'paint',rx=4)
for y,x2 in [(18,94),(39,114),(61,103),(84,119),(107,87)]:
    line(g,10,y,x2,y,'paint-light',2.5,opacity='.38')
# An outlined rim is not a logical border: the host still draws the grid separately.
save(r,'world/paint.svg','A03','Paint layer',{'tile':[0,0,128,128]})

r=doc('Horizontal one-cell wall',128,24)
g=part(r,'wall-middle');rect(g,0,5,128,14,'outline',rx=0)
rect(g,0,7,128,8,'body-shade')
line(g,0,7,128,7,'body',1.5)
line(g,0,17,128,17,'frame',2)
g=part(r,'wall-detail')
for x in [12,116]: circle(g,x,11,2,'frame')
rect(g,56,8,16,5,'accent',rx=2)
save(r,'world/wall.svg','A04','Wall segment',{'start':[0,12],'end':[128,12],'middle':[16,5,96,14]})

r=doc('Wall junction',24,24)
g=part(r,'joint');rect(g,3,3,18,18,'body-shade','outline',2.5,rx=5)
circle(g,12,12,4,'accent','outline',1.5)
circle(g,12,12,1.4,'accent-light')
save(r,'world/wall-joint.svg','A05','Wall joint',{'pivot':[12,12]})

r=doc('Origin marker',128,128)
g=part(r,'marker')
circle(g,64,64,51,None,'white',5)
circle(g,64,64,51,None,'accent',2.5,stroke_dasharray='7 6')
path(g,'M 14 64 L 22 59 L 22 69 Z','accent')
path(g,'M 114 64 L 106 59 L 106 69 Z','accent')
save(r,'world/marker-start.svg','A06','Start marker',{'pivot':[64,64]})

r=doc('Docking finish marker',128,128)
g=part(r,'marker')
for d in ['M 31 10 H 14 Q 10 10 10 14 V 31','M 97 10 H 114 Q 118 10 118 14 V 31',
          'M 10 97 V 114 Q 10 118 14 118 H 31','M 97 118 H 114 Q 118 118 118 114 V 97']:
    path(g,d,None,'white',7);path(g,d,None,'frame',3)
for d in ['M 53 11 L 64 20 L 75 11','M 53 117 L 64 108 L 75 117']:
    path(g,d,None,'white',7);path(g,d,None,'frame',3)
save(r,'world/marker-finish.svg','A07','Finish marker',{'pivot':[64,64]})

r=doc('Target-cell annotation',128,128)
g=part(r,'marker')
for d in ['M 29 3 H 6 Q 3 3 3 6 V 29','M 99 3 H 122 Q 125 3 125 6 V 29',
          'M 3 99 V 122 Q 3 125 6 125 H 29','M 99 125 H 122 Q 125 125 125 122 V 99']:
    path(g,d,None,'white',5);path(g,d,None,'paint-shade',2.5)
for x,y in [(64,3),(125,64),(64,125),(3,64)]: circle(g,x,y,2,'paint-shade')
save(r,'world/marker-target.svg','A08','Target marker',{'pivot':[64,64]})

r=doc('Cargo bag')
g=part(r,'bag-base')
path(g,'M 23 17 V 12 Q 23 6 32 6 Q 41 6 41 12 V 17',None,'outline',4)
rect(g,10,17,44,40,'body','outline',2.5,rx=10)
path(g,'M 11 43 Q 32 50 53 43 V 48 Q 53 56 45 56 H 19 Q 11 56 11 48 Z','body-shade')
rect(g,8,30,8,19,'accent','outline',2,rx=3);rect(g,48,30,8,19,'accent','outline',2,rx=3)
g=part(r,'bag-contents',opacity=0)
path(g,'M 32 14 L 39 21 L 32 32 L 25 21 Z','crystal','outline',1.5)
g=part(r,'bag-lid')
path(g,'M 13 18 H 51 V 29 Q 32 40 13 29 Z','paint','outline',2.5)
path(g,'M 18 21 H 46',None,'paint-light',2)
rect(g,29,28,6,10,'accent','outline',1.5,rx=2)
g=part(r,'bag-indicator');rect(g,25,44,14,5,'frame',rx=2)
save(r,'hud/bag.svg','A09','Cargo bag',{'lid_pivot':[32,18],'contents':[32,23],'label':[32,48]})

r=doc('Compass without baked-in letters')
g=part(r,'compass-frame');circle(g,32,32,27,'body','outline',2.5)
circle(g,32,32,22,None,'body-shade',2)
for a in [0,90,180,270]: line(g,32,9,32,14,'frame',2.5,transform=f'rotate({a} 32 32)')
g=part(r,'compass-pointer')
path(g,'M 32 15 L 39 33 L 32 30 L 25 33 Z','paint','outline',1.8)
path(g,'M 32 49 L 38 33 L 32 35 L 26 33 Z','accent','outline',1.8)
circle(g,32,32,3.5,'body','outline',2)
save(r,'hud/compass.svg','A10','Compass',{'pivot':[32,32]})

r=doc('North-pointing direction arrow')
g=part(r,'arrow')
path(g,'M 32 7 L 53 30 H 41 V 55 H 23 V 30 H 11 Z','accent-light','outline',2.5)
path(g,'M 32 13 V 48',None,'white',2)
save(r,'hints/direction-arrow.svg','A11','Direction arrow',{'pivot':[32,32],'tail':[32,55],'tip':[32,7]})

r=doc('Short north-facing sensor pulse',64,64)
g=part(r,'pulse')
circle(g,32,54,3,'accent')
line(g,32,46,32,34,'accent',3)
path(g,'M 23 29 Q 32 22 41 29',None,'accent',3)
path(g,'M 16 20 Q 32 8 48 20',None,'accent',2.5)
path(g,'M 10 11 Q 32 -1 54 11',None,'accent-light',2)
save(r,'hints/sensor-pulse.svg','A12','Sensor pulse',{'origin':[32,54],'target':[32,5]})

r=doc('Open focus ring',128,128)
g=part(r,'focus')
for a in range(0,360,90):
    path(g,'M 18 38 A 53 53 0 0 1 38 18',None,'white',6,transform=f'rotate({a} 64 64)')
    path(g,'M 18 38 A 53 53 0 0 1 38 18',None,'accent',3,transform=f'rotate({a} 64 64)')
for x,y in [(64,10),(118,64),(64,118),(10,64)]: circle(g,x,y,2.5,'accent')
save(r,'hints/focus-ring.svg','A13','Focus ring',{'pivot':[64,64]})

r=doc('Boolean True — not a task verdict')
g=part(r,'badge');circle(g,32,32,24,'positive-light','positive',2.5)
g=part(r,'glyph');path(g,'M 19 32 L 28 41 L 45 23',None,'positive',5)
save(r,'status/boolean-true.svg','A14','Boolean True')

r=doc('Boolean False — normal sensor outcome')
g=part(r,'badge');circle(g,32,32,24,'negative-light','negative',2.5)
g=part(r,'glyph');line(g,22,22,42,42,'negative',4);line(g,42,22,22,42,'negative',4)
save(r,'status/boolean-false.svg','A15','Boolean False')

r=doc('Calm warning')
g=part(r,'badge')
path(g,'M 27 9 Q 32 2 37 9 L 58 47 Q 62 55 53 56 H 11 Q 2 55 6 47 Z','error-light','error',2.5)
g=part(r,'glyph');line(g,32,22,32,36,'error',4);circle(g,32,45,2.5,'error')
save(r,'status/error.svg','A16','Error')

r=doc('Program completed — neutral')
g=part(r,'badge');rect(g,8,8,48,48,'negative-light','outline',2.5,rx=15)
g=part(r,'glyph');rect(g,22,20,20,20,'frame',rx=4);line(g,23,47,41,47,'frame',3)
save(r,'status/completed.svg','A17','Program completed')

r=doc('Verified task success')
g=part(r,'badge')
path(g,'M 32 4 L 41 10 L 51 12 L 54 23 L 60 32 L 54 41 L 51 52 L 41 54 L 32 60 L 23 54 L 13 52 L 10 41 L 4 32 L 10 23 L 13 12 L 23 10 Z','paint-light','paint-shade',2.5)
circle(g,32,32,18,'body','paint-shade',2)
g=part(r,'glyph');path(g,'M 23 32 L 29 38 L 42 25',None,'paint-shade',4)
save(r,'status/success.svg','A18','Verified success')

r=doc('Keyboard input')
g=part(r,'keyboard');rect(g,4,17,56,35,'body-shade','outline',2.5,rx=8)
for yy in (23,32):
    for xx in (11,21,31,41): rect(g,xx,yy,7,6,'body',rx=1.5)
rect(g,51,23,4,15,'accent',rx=1.5)
rect(g,18,42,29,5,'body',rx=1.5)
line(g,28,9,28,12,'accent',2);line(g,36,9,36,12,'accent',2)
save(r,'input/keyboard.svg','A19','Keyboard input',{'label_region':[14,22,35,14]})

r=doc('Pointer or touch selection')
g=part(r,'pointer')
path(g,'M 22 18 L 49 36 L 36 39 L 31 52 Z','body','outline',2.5)
path(g,'M 36 40 L 43 54',None,'outline',3)
g=part(r,'click-rays')
for d in ['M 17 8 L 18 13','M 8 18 L 13 20','M 8 30 L 14 28','M 31 9 L 28 14']:
    path(g,d,None,'accent',2.5)
save(r,'input/pointer.svg','A20','Pointer input',{'tip':[22,18]})

r=doc('Timed wait clock')
g=part(r,'clock-frame');circle(g,32,34,24,'body','outline',2.5)
rect(g,26,3,12,7,'accent','outline',2,rx=2)
for a in (0,90,180,270): line(g,32,14,32,17,'frame',2,transform=f'rotate({a} 32 34)')
g=part(r,'clock-hand');path(g,'M 32 34 V 19',None,'accent',3)
g=part(r,'clock-hour');path(g,'M 32 34 L 42 40',None,'frame',3)
circle(r,32,34,2.5,'outline')
save(r,'input/clock.svg','A21','Timed wait',{'pivot':[32,34]})

# UI paths are drawn only once. The contact sheet and single-icon files use this geometry.
controls={}
def icon(name):
    g=E('g');controls[name]=g;return g
q=icon('play');path(q,'M 10 5 L 26 16 L 10 27 Z','accent','outline',1.5)
q=icon('pause');rect(q,7,5,6,22,'accent',rx=2);rect(q,19,5,6,22,'accent',rx=2)
q=icon('stop');rect(q,6,6,20,20,'frame',rx=4)
q=icon('step');path(q,'M 5 6 L 21 16 L 5 26 Z','accent','outline',1.5);line(q,26,6,26,26,'outline',3)
q=icon('reset');path(q,'M 25 11 A 10 10 0 1 0 26 21',None,'accent',3);path(q,'M 25 5 V 12 H 18',None,'accent',3)
q=icon('history-back');path(q,'M 23 7 L 12 16 L 23 25',None,'frame',3);line(q,6,7,6,25,'frame',3)
q=icon('history-forward');path(q,'M 9 7 L 20 16 L 9 25',None,'frame',3);line(q,26,7,26,25,'frame',3)
q=icon('speed');path(q,'M 6 25 A 12 12 0 1 1 26 25',None,'frame',2.5);line(q,16,18,24,10,'accent',3);circle(q,16,18,2.5,'accent')
for x,y in [(7,17),(11,9),(21,8)]:circle(q,x,y,1,'frame')
for name,plus in [('zoom-in',True),('zoom-out',False)]:
    q=icon(name);circle(q,14,14,9,None,'frame',2.5);line(q,21,21,28,28,'accent',4);line(q,10,14,18,14,'accent',2)
    if plus: line(q,14,10,14,18,'accent',2)
q=icon('fit')
for d in ['M 5 12 V 5 H 12','M 20 5 H 27 V 12','M 5 20 V 27 H 12','M 20 27 H 27 V 20']:path(q,d,None,'frame',2.5)
circle(q,16,16,3,'accent')
q=icon('settings')
path(q,'M 13 3 H 19 L 20 8 L 24 6 L 28 11 L 25 15 L 29 18 L 26 24 L 21 23 L 19 29 H 13 L 11 24 L 6 26 L 3 21 L 7 17 L 3 13 L 6 7 L 11 9 Z','body-shade','frame',1.8)
circle(q,16,16,5,'body','accent',2)

r=doc('Twelve interface controls — reusable SVG symbols',256,192)
d=add(r,'defs')
import copy
for name,q in controls.items():
    sym=add(d,'symbol',id=name,viewBox='0 0 32 32');sym.append(copy.deepcopy(q))
for i,name in enumerate(controls):
    x=(i%4)*64;y=(i//4)*64
    rect(r,x+5,y+5,54,54,'accent-pale',rx=14)
    u=add(r,'use',x=x+16,y=y+16,width=32,height=32)
    u.set('{%s}href'%XLINK,'#'+name)
save(r,'ui/controls.svg','A22','Interface controls',{'symbol_viewBox':[0,0,32,32]})
for name,q in controls.items():
    r=doc(name.replace('-',' ').capitalize(),32,32);r.append(copy.deepcopy(q))
    save(r,f'ui/icons/{name}.svg','derived-'+name,name,'',scope='derived-control')

r=doc('Reserve sliding gate — graphics only',128,64)
g=part(r,'gate-frame');rect(g,6,21,116,22,'outline',rx=3);rect(g,8,25,112,14,'body-shade',rx=1)
g=part(r,'gate-panel');rect(g,19,24,89,16,'accent-light','outline',2,rx=3)
for x in (28,47,66,85):path(g,f'M {x} 26 L {x+9} 38',None,'accent',3)
for x in (4,110):
    rect(r,x,15,14,34,'body','outline',2.5,rx=5);circle(r,x+7,22,2.5,'paint')
save(r,'reserve/gate.svg','X01','Sliding gate',{'slide_open':[-89,0],'edge_start':[11,32],'edge_end':[117,32]},scope='art-reserve')

r=doc('Reserve push button — graphics only')
g=part(r,'switch-base');circle(g,32,34,24,'body-shade','outline',2.5);circle(g,32,33,18,'outline')
g=part(r,'switch-cap');circle(g,32,29,16,'paint','outline',2.5);path(g,'M 23 20 Q 32 15 40 21',None,'paint-light',3)
circle(g,32,29,5,None,'paint-shade',2)
save(r,'reserve/switch.svg','X02','Push button',{'press_translation':[0,4]},scope='art-reserve')

r=doc('Reserve signal lamp — graphics only')
g=part(r,'lamp-frame');rect(g,12,9,40,46,'body','outline',2.5,rx=16)
line(g,24,49,40,49,'frame',3)
g=part(r,'lamp-off');circle(g,32,29,13,'body-shade','frame',2);line(g,27,29,37,29,'frame',2.5)
g=part(r,'lamp-on',opacity=0);circle(g,32,29,13,'paint','outline',2);circle(g,32,29,5,'paint-light')
for a in (0,90,180,270):line(g,32,13,32,16,'paint-shade',2,transform=f'rotate({a} 32 29)')
save(r,'reserve/lamp.svg','X03','Signal lamp',{'pivot':[32,29]},scope='art-reserve')

manifest={'format':'tlfrobot-art/1','theme':'workshop','character':'Timo',
          'revision':'1.0.0','design':'Original circular workshop caretaker; vector redraw, not a trace of the PNG concept sheets.',
          'palette':P,'coordinate_convention':'SVG: x right, y down; north is negative y; clockwise positive degrees.',
          'assets':assets,'required_count':22,'reserve_count':3,
          'robot':{'path':'robot/robot.svg','pivot':[64,64],'canonical_heading':'north',
                   'default_hidden':['gripper-base','gripper-left','gripper-right','roller','eraser','eyelids'],
                   'upright_parts':['eyes','eyelids','cargo-hatch'],
                   'heading_parts':['drive','body','heading'],
                   'sensor_independent':True,'safe_badge_region':[99,115,27,12]},
          'recolour':'Use data-fill-role and data-stroke-role attributes. SVG masters contain concrete palette colours for portability.',
          'mounting':'Namespace every id and local href/url reference on insertion. data-part values stay logical and are scoped to the instance.'}
(ROOT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(f'Wrote {len(assets)} SVG files: 22 core, 3 reserve, 12 derived controls.')
