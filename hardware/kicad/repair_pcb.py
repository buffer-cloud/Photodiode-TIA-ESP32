#!/usr/bin/env python3
"""Clearance-aware repair of existing Rev A placement. Writes a separate candidate.
Run with KiCad bundled Python. Never changes the source PCB or schematic.
"""
from pathlib import Path
import argparse
import pcbnew as p, xml.etree.ElementTree as ET, heapq, math
H=Path(__file__).resolve().parent
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--output',type=Path,required=True,help='New candidate path; refuses existing files')
a=ap.parse_args()
out=a.output.resolve()
if out.exists():ap.error('Output already exists; choose a new candidate path.')
b=p.LoadBoard(str(H/'photodiode-tia-esp32.kicad_pcb'))
fps={f.GetReference():f for f in b.GetFootprints()}
M=p.FromMM
for t in list(b.GetTracks()): b.RemoveNative(t)
for z in list(b.Zones()): b.RemoveNative(z)
# Retain the existing flow, outline, components and mounting arrangement.
placements={'D1':(10.3,22.5,0),'R1':(11,11.2,90),'C3':(12.8,11.2,90),'R2':(11,14.4,90),'C4':(12.8,14.4,90),'R3':(11,17.6,90),'C5':(12.8,17.6,90),'C8':(21.5,17,0),'C9':(25,17,0),'C10':(40.5,16.5,0),'C11':(44,16.5,0),'C14':(46,29.5,90),'JP1':(49,24,0),'TP1':(9,38,0),'TP6':(53,37,0)}
for r,(x,y,a) in placements.items():
 f=fps[r];f.SetPosition(p.VECTOR2I(M(x),M(y)));f.SetOrientationDegrees(a)
root=ET.parse(H/'verification/schematic.xml').getroot()
for c in root.findall('./components/comp'):
 f=fps[c.attrib['ref']];f.SetPath(p.KIID_PATH('/'+c.findtext('tstamps')));f.SetFPID(p.LIB_ID(*c.findtext('footprint').split(':',1)));f.SetAttributes(f.GetAttributes() & ~p.FP_EXCLUDE_FROM_BOM)
# Retain schematic names including leading slash, for parity.
for n in root.findall('./nets/net'):
 name=n.attrib['name'];old=name.lstrip('/')
 for f in fps.values():
  for pad in f.Pads():
   if pad.GetNetname()==old:pad.GetNet().SetNetname(name)
netmap={q.GetNetname():q.GetNet() for f in fps.values() for q in f.Pads() if q.GetNetname()}
for f in fps.values():
 f.Reference().SetVisible(True);f.Reference().SetLayer(p.F_Fab);f.Reference().SetPosition(f.GetPosition());f.Reference().SetTextSize(p.VECTOR2I(M(.6),M(.6)));f.Reference().SetTextThickness(M(.1))
 f.Value().SetVisible(False)
for d in list(b.GetDrawings()):
 if d.GetLayer()==p.F_SilkS:b.RemoveNative(d)
S=.125; W=481;Y=361;N=W*Y
shapes=[]
holes=[]
pad_boxes=[]
def rect(layer,net,x1,y1,x2,y2):
 shapes.append((layer,net,max(0,int(math.floor(x1/S))),max(0,int(math.floor(y1/S))),min(W-1,int(math.ceil(x2/S))),min(Y-1,int(math.ceil(y2/S)))))
pads={}
for f in fps.values():
 for q in f.Pads():
  pt=q.GetPosition();x=p.ToMM(pt.x);y=p.ToMM(pt.y);net=q.GetNetname(); bb=q.GetBoundingBox();
  pad_boxes.append((p.ToMM(bb.GetLeft())-.52,p.ToMM(bb.GetTop())-.52,p.ToMM(bb.GetRight())+.52,p.ToMM(bb.GetBottom())+.52))
  layers=[0,1] if q.GetAttribute()!=p.PAD_ATTRIB_SMD else [0]
  for l in layers:rect(l,net,p.ToMM(bb.GetLeft())-.35,p.ToMM(bb.GetTop())-.35,p.ToMM(bb.GetRight())+.35,p.ToMM(bb.GetBottom())+.35)
  if q.GetAttribute()!=p.PAD_ATTRIB_SMD:holes.append((x,y,p.ToMM(q.GetDrillSize().x)/2))
  if net:pads.setdefault(net,[]).append((round(x/S),round(y/S),layers,(x,y),f.GetReference(),q.GetNumber()))
def track(a,c,l,net):
 if a==c:return
 t=p.PCB_TRACK(b);t.SetStart(p.VECTOR2I(M(a[0]),M(a[1])));t.SetEnd(p.VECTOR2I(M(c[0]),M(c[1])));t.SetLayer(p.F_Cu if l==0 else p.B_Cu);t.SetWidth(M(.25));t.SetNet(netmap[net]);b.Add(t)
 # Rasterize small sections rather than block a diagonal bounding rectangle.
 count=max(1,math.ceil(math.dist(a,c)/S))
 for i in range(count+1):
  x=a[0]+(c[0]-a[0])*i/count;y=a[1]+(c[1]-a[1])*i/count
  rect(l,net,x-.47,y-.47,x+.47,y+.47)
def via(x,y,net):
 v=p.PCB_VIA(b);v.SetPosition(p.VECTOR2I(M(x),M(y)));v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(p.F_Cu,M(.6));v.SetDrill(M(.3));v.SetNet(netmap[net]);b.Add(v)
 for l in (0,1):rect(l,net,x-.65,y-.65,x+.65,y+.65)
def blocked(net):
 z=[bytearray(N),bytearray(N)]
 for l,n,x1,y1,x2,y2 in shapes:
  if n==net:continue
  row=b'\1'*(x2-x1+1)
  for y in range(y1,y2+1):z[l][y*W+x1:y*W+x2+1]=row
 for l in (0,1):
  for y in range(Y):
   if y<7 or y>=Y-7:z[l][y*W:(y+1)*W]=b'\1'*W
   else:z[l][y*W:y*W+7]=b'\1'*7;z[l][(y+1)*W-7:(y+1)*W]=b'\1'*7
 return z
def search(start,targets,z,no_vias=False):
 tx=[s%W for s in targets];ty=[(s%N)//W for s in targets];xmin,xmax=min(tx),max(tx);ymin,ymax=min(ty),max(ty)
 def heur(s):
  x=s%W;y=(s%N)//W;return max(xmin-x,0,x-xmax)+max(ymin-y,0,y-ymax)
 heap=[(heur(start),0,start)];cost={start:0};prev={};end=None
 while heap:
  _,g,s=heapq.heappop(heap)
  if cost.get(s)!=g:continue
  if s in targets:end=s;break
  l=s//N;i=s%N;x=i%W;y=i//W
  for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
   j=i+dx+dy*W
   if not (1<=x+dx<W-1 and 1<=y+dy<Y-1) or z[l][j]:continue
   if dx and dy and (z[l][i+dx] or z[l][i+dy*W]):continue
   ns=l*N+j;ng=g+(1.42 if dx and dy else 1)
   if ng<cost.get(ns,1e30):cost[ns]=ng;prev[ns]=s;heapq.heappush(heap,(ng+heur(ns),ng,ns))
  if not no_vias and 3<x<W-3 and 3<y<Y-3:
   ok=not any(x1<=x*S<=x2 and y1<=y*S<=y2 for x1,y1,x2,y2 in pad_boxes) and all(math.hypot(x*S-hx,y*S-hy)>hr+.45 for hx,hy,hr in holes)
   for ll in (0,1):
    for yy in range(y-2,y+3):
     if any(z[ll][yy*W+x-2:yy*W+x+3]):ok=False;break
    if not ok:break
   ns=(1-l)*N+i;ng=g+24
   if ok and ng<cost.get(ns,1e30):cost[ns]=ng;prev[ns]=s;heapq.heappush(heap,(ng+heur(ns),ng,ns))
 if end is None:raise RuntimeError('route failed')
 path=[end]
 while path[-1]!=start:path.append(prev[path[-1]])
 return path[::-1]
def xy(s):return ((s%N)%W*S,(s%N)//W*S)
# Reserve off-pad ground fanouts before signal routing.
gnd=next(n for n in pads if n.lstrip('/')=='GND')
for q in pads[gnd]:
 if len(q[2])!=1:continue
 x,y=q[3];z=blocked(gnd);found=False
 candidates=[]
 for ix in range(-20,21):
  for iy in range(-20,21):
   xx=round(x/S)*S+ix*S;yy=round(y/S)*S+iy*S;distance=math.hypot(xx-x,yy-y)
   if .9<=distance<=2.5:candidates.append((distance,xx,yy))
 for _,xx,yy in sorted(candidates):
  if any(a<=xx<=c and d<=yy<=e for a,d,c,e in pad_boxes):continue
  gx,gy=round(xx/S),round(yy/S)
  if any(any(z[l][j*W+gx-2:j*W+gx+3]) for l in (0,1) for j in range(gy-2,gy+3)):continue
  steps=max(1,math.ceil(math.hypot(xx-x,yy-y)/S))
  if any(z[0][round((y+(yy-y)*i/steps)/S)*W+round((x+(xx-x)*i/steps)/S)] for i in range(steps+1)):continue
  track((x,y),(xx,yy),0,gnd);via(xx,yy,gnd);found=True;break
 if not found:raise RuntimeError('No off-pad ground escape for '+q[4])
order=['SUM','GAIN_10K','GAIN_100K','GAIN_1M','VREF','VREF_DIV','TIA_OUT','LP1','BUF1','LP2','FILTER_OUT','ADC_OUT','ADC_LINK','VBUS_5V','3V3D','3V3A']
for short in order:
 net=next(n for n in pads if n.lstrip('/')==short);ps=pads[net];ps.sort(key=lambda q:0 if q[4]=='U1' else 1)
 first=ps.pop(0);tree={l*N+first[1]*W+first[0] for l in first[2]};track(first[3],(first[0]*S,first[1]*S),0,net)
 while ps:
  q=min(ps,key=lambda q:min(abs(q[0]-t%W)+abs(q[1]-(t%N)//W) for t in tree));ps.remove(q)
  z=blocked(net);start=q[2][0]*N+q[1]*W+q[0]
  print('connect',short,q[4],q[5],flush=True);path=search(start,tree,z,short=='SUM');track(q[3],xy(start),q[2][0],net)
  begin=path[0];last=begin;direction=None
  for s in path[1:]:
   if s//N!=last//N:
    track(xy(begin),xy(last),last//N,net);via(*xy(last),net);begin=s;direction=None
   else:
    d=s-last
    if direction is not None and d!=direction:track(xy(begin),xy(last),last//N,net);begin=last
    direction=d
   last=s
  track(xy(begin),xy(last),last//N,net);tree.update(path);tree.update(l*N+q[1]*W+q[0] for l in q[2])
 print('routed',short,flush=True)
# Ground plane and short SMD-pad vias; copper no-pour under detector feedback.
net=next(n for n in pads if n.lstrip('/')=='GND')
def poly(z,coords):
 o=z.Outline();o.NewOutline()
 for x,y in coords:o.Append(M(x),M(y))
for l in (p.F_Cu,p.B_Cu):
 z=p.ZONE(b);z.SetLayer(l);z.SetNet(netmap[net]);z.SetLocalClearance(M(.25));z.SetPadConnection(p.ZONE_CONNECTION_FULL);poly(z,[(.5,.5),(59.5,.5),(59.5,44.5),(.5,44.5)]);b.Add(z)
z=p.ZONE(b);z.SetIsRuleArea(True);z.SetDoNotAllowCopperPour(True);z.SetDoNotAllowTracks(False);z.SetDoNotAllowVias(False);z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False);ls=p.LSET();ls.addLayer(p.F_Cu);ls.addLayer(p.B_Cu);z.SetLayerSet(ls);z.SetZoneName('SUM_FEEDBACK_NO_POUR');poly(z,[(9.5,9.8),(14,9.8),(14,19.8),(16.8,19.8),(16.8,21),(14,21),(14,23.5),(11.7,23.5),(11.7,19.8),(9.5,19.8)]);b.Add(z)
# Explicit readable assembly labels in the open lower area.
def text(x,y,s,size=.8):
 size=max(size,.8)
 t=p.PCB_TEXT(b);t.SetText(s);t.SetPosition(p.VECTOR2I(M(x),M(y)));t.SetLayer(p.F_SilkS);t.SetTextSize(p.VECTOR2I(M(size),M(size)));t.SetTextThickness(M(.12));b.Add(t)
text(30,43,'PHOTODIODE TIA REV A',1.2);text(30,1.5,'ONE GAIN LINK ONLY - POWER OFF TO CHANGE');text(32,33,'OPEN JP_ADC FOR INDEPENDENT POWER')
for r,x in [('JP2',13),('JP3',17),('JP4',21)]:text(x,8.7+(x-13)*.6,fps[r].GetValue(),.8)
for r in ['TP1','TP2','TP3','TP4','TP5','TP6']:
 pos=fps[r].GetPosition();text(p.ToMM(pos.x),p.ToMM(pos.y)-2,fps[r].GetValue(),.7)
text(54,31,'J_ESP32',.8);text(51,29.8,'JP_ADC',.8)
b.SetCopperLayerCount(2);b.GetDesignSettings().SetBoardThickness(M(1.6))
p.SaveBoard(str(out),b);b=p.LoadBoard(str(out));p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(out),b)
print(out)
