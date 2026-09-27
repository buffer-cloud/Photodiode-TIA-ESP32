"""Deterministic native KiCad 9 schematic authoring; writes only schematic/library files."""
from pathlib import Path
import uuid,re,json,math,os,argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument("--symbol-library",type=Path,default=None)
parser.add_argument("--overwrite",action="store_true",help="Replace schematic and local symbol library; discard manual edits")
args=parser.parse_args()
P=Path(__file__).resolve().parent
if (P/'photodiode-tia-esp32.kicad_sch').exists() and not args.overwrite:
 raise SystemExit('Schematic exists. Native schematic is source of truth; use --overwrite only to deliberately discard manual edits.')
candidates=[args.symbol_library,Path(os.environ['KICAD_SYMBOL_DIR']) if os.environ.get('KICAD_SYMBOL_DIR') else None,Path('/usr/share/kicad/symbols'),Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols'),Path('C:/Program Files/KiCad/9.0/share/kicad/symbols')]
LIB=next((p for p in candidates if p and (p/'Device.kicad_sym').exists()),None)
if LIB is None:raise SystemExit('Pass --symbol-library PATH or set KICAD_SYMBOL_DIR to KiCad 9 symbol library.')
def uid(s): return str(uuid.uuid5(uuid.NAMESPACE_URL,'photodiode-tia-reva/'+s))
def q(s):return json.dumps(str(s),ensure_ascii=False)
def eff(sz=1.27):return f'(effects (font (size {sz} {sz})))'
def block(text,start):
 i=start;d=0;quoted=False;esc=False
 for j in range(start,len(text)):
  c=text[j]
  if c=='"' and not esc:quoted=not quoted
  if not quoted:
   if c=='(':d+=1
   elif c==')':
    d-=1
    if d==0:return text[start:j+1]
  esc=c=='\\' and not esc
symbols={};pins={}
def standard(lib,name):
 t=(LIB/(lib+'.kicad_sym')).read_text(); b=block(t,t.index('(symbol "'+name+'"'))
 symbols[name]=b
 pp=[]
 for m in re.finditer(r'\(pin (\w+) (\w+)\s',b):
  p=block(b,m.start()); at=re.search(r'\(at ([\d.-]+) ([\d.-]+) ([\d.-]+)\)',p);n=re.search(r'\(number "([^"]+)"',p)
  pp.append((n[1],float(at[1]),float(at[2]),float(at[3])))
 pins[name]={1:pp};return name
for l,n in [('Device','R'),('Device','C'),('Sensor_Optical','BPW34'),('Diode','BAT54S'),('Connector_Generic','Conn_01x06'),('Connector_Generic','Conn_01x02'),('Connector','TestPoint'),('power','PWR_FLAG')]:standard(l,n)
def pin(n,name,x,y,a,t='passive'):
 return f'(pin {t} line (at {x} {y} {a})(length 2.54)(name {q(name)} {eff()})(number {q(n)} {eff()}))'
def custom(name,units,graphics,ref='U'):
 b=f'(symbol "{name}" (pin_names (offset 0.508))(in_bom yes)(on_board yes)(property "Reference" "{ref}" (at 0 10 0) {eff()})(property "Value" "{name}" (at 0 7 0) {eff()})'
 pins[name]={}
 for u,ps in units.items():
  b+=f'(symbol "{name}_{u}_1" '+graphics[u]+''.join(pin(*p) for p in ps)+')'
  pins[name][u]=[(str(p[0]),p[2],p[3],p[4]) for p in ps]
 symbols[name]=b+')'
tri='(polyline (pts (xy -5.08 5.08)(xy 5.08 0)(xy -5.08 -5.08)(xy -5.08 5.08))(stroke (width 0.254)(type default))(fill (type background)))'
rect='(rectangle (start -5.08 5.08)(end 5.08 -5.08)(stroke (width 0.254)(type default))(fill (type background)))'
custom('OPA2320',{1:[(3,'+',-7.62,2.54,0,'input'),(2,'−',-7.62,-2.54,0,'input'),(1,'OUT',7.62,0,180,'output')],2:[(5,'+',-7.62,2.54,0,'input'),(6,'−',-7.62,-2.54,0,'input'),(7,'OUT',7.62,0,180,'output')],3:[(8,'V+',0,7.62,270,'power_in'),(4,'V−',0,-7.62,90,'power_in')]},{1:tri,2:tri,3:rect})
custom('TPS7A2033PDBVR',{1:[(1,'IN',-7.62,2.54,0,'power_in'),(3,'EN',-7.62,-2.54,0,'input'),(5,'OUT',7.62,2.54,180,'power_out'),(4,'NC',7.62,-2.54,180,'no_connect'),(2,'GND',0,-7.62,90,'power_in')]},{1:rect})
root=uid('root');items=[];manifest=[]
def wire(a,b):items.append(f'(wire (pts (xy {a[0]} {a[1]})(xy {b[0]} {b[1]}))(stroke (width 0)(type default))(uuid {q(uid("wire"+str((a,b))))}))')
def label(net,x,y):items.append(f'(label {q(net)} (at {x} {y} 0) {eff(1.1)} (uuid {q(uid("label"+str((net,x,y))))}))')
def note(s,x,y,size=1.5):items.append(f'(text {q(s)} (at {x} {y} 0)(effects (font (size {size} {size}))(justify left))(uuid {q(uid("note"+s))}))')
def add(name,ref,val,x,y,nets,fp='',unit=1,angle=0,autolabel=True):
 inst=uid(ref+str(unit));a=math.radians(angle)
 b=f'(symbol (lib_id "Photodiode:{name}")(at {x} {y} {angle})(unit {unit})(in_bom yes)(on_board yes)(dnp no)(uuid {q(inst)})'
 tx,ty=(x+8.89,y-1.27) if name in ['R','C'] and angle==0 else (x+3.81,y-8.89)
 b+=f'(property "Reference" {q(ref)} (at {tx} {ty} {angle}) {eff()})'
 b+=f'(property "Value" {q(val)} (at {tx} {ty+2.54} {angle}) {eff(1.1)})'
 b+=f'(property "Footprint" {q(fp)} (at {x} {y} 0)(effects (font(size 1.27 1.27))(hide yes)))'
 coords={}
 for n,px,py,pa in pins[name][unit]:
  X=round(x+px*math.cos(a)-py*math.sin(a),4);Y=round(y-px*math.sin(a)-py*math.cos(a),4);coords[n]=(X,Y)
  b+=f'(pin {q(n)} (uuid {q(uid(ref+"pin"+n))}))'
  net=nets.get(n)
  if net is None:continue  # U3 NC is explicitly a no_connect electrical pin
  if autolabel:
   aa=math.radians(pa+angle);ex=round(X-5.08*math.cos(aa),4);ey=round(Y+5.08*math.sin(aa),4)
   wire((X,Y),(ex,ey));label(net,ex,ey)
 b+=f'(instances (project "photodiode-tia-esp32" (path "/{root}" (reference {q(ref)})(unit {unit})))))';items.append(b)
 if unit==1:manifest.append({'ref':ref,'value':val,'footprint':fp})
 return coords
R='Resistor_SMD:R_0603_1608Metric';C='Capacitor_SMD:C_0603_1608Metric';SO='Package_SO:SOIC-8_3.9x4.9mm_P1.27mm';H='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical'
def passive(kind,ref,val,x,y,n1,n2,angle=0):return add(kind,ref,val,x,y,{'1':n1,'2':n2},R if kind=='R' else C,angle=angle)
note('PHOTODIODE TIA / ESP32     |     REV A · ENGINEERING PROTOTYPE',20,15,2.5)
note('01  USB supply and quiet analog rail',20,27,1.8)
add('Conn_01x06','J1','J_ESP32',35.56,53.34,dict(zip(map(str,range(1,7)),['VBUS_5V','GND','3V3D','GND','ADC_LINK','GND'])),'Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical')
add('TPS7A2033PDBVR','U3','TPS7A2033PDBVR',88.9,50.8,{'1':'VBUS_5V','2':'GND','3':'VBUS_5V','4':None,'5':'3V3A'},'Package_TO_SOT_SMD:SOT-23-5')
passive('C','C1','1u X7R',58.42,80.01,'VBUS_5V','GND');passive('C','C2','1u X7R',111.76,80.01,'3V3A','GND')
for i,(net,x) in enumerate([('VBUS_5V',25.4),('GND',38.1),('3V3D',50.8)]):add('PWR_FLAG','#FLG0'+str(i+1),'PWR_FLAG',x,90.17,{'1':net})
note('02  1.65 V reference · no output capacitor',147,27,1.8)
passive('R','R4','10k 0.1%',157.48,48.26,'3V3A','VREF_DIV');passive('R','R5','10k 0.1%',157.48,78.74,'VREF_DIV','GND')
passive('C','C6','10u X7R',185.42,78.74,'VREF_DIV','GND');passive('C','C7','100n X7R',210.82,78.74,'VREF_DIV','GND')
add('OPA2320','U1','OPA2320',226.06,48.26,{'5':'VREF_DIV','6':'VREF','7':'VREF'},SO,unit=2)
note('03  Local amplifier bypass · place at pins 8 / 4',275,27,1.8)
for ref,x in [('U1',284.48),('U2',347.98)]:add('OPA2320',ref,'OPA2320',x,53.34,{'8':'3V3A','4':'GND'},SO,unit=3)
for ref,v,x in [('C8','100n X7R',279.4),('C9','1u X7R',307.34),('C10','100n X7R',342.9),('C11','1u X7R',370.84)]:passive('C',ref,v,x,86.36,'3V3A','GND')
note('04  Reverse-biased detector and transimpedance amplifier',20,112,1.8)
add('BPW34','D1','BPW34',38.1,144.78,{'1':'3V3A','2':'SUM'},'Photodiode:Vishay_BPW34_THT')
add('OPA2320','U1','OPA2320',91.44,144.78,{'3':'VREF','2':'SUM','1':'TIA_OUT'},SO)
note('VOUT = VREF − IPHOTO × RF\nDark ≈ 1.65 V; useful full scale 0.25 V\nDo not probe SUM with a conventional scope probe.',20,173,1.3)
note('05  Paired gain selection · links are at the OUTPUT ends',145,112,1.8)
# Actual parallel branches, each isolated at output by link.
for i,(ref,val,cv,x) in enumerate([('10K','10k 0.1%','1n C0G',170.18),('100K','100k 0.1%','100p C0G',248.92),('1M','1M 0.1%','10p C0G',327.66)],1):
 p=add('R','R'+str(i),val,x,134.62,{'1':'SUM','2':'GAIN_'+ref},R,angle=90,autolabel=False)
 c=add('C','C'+str(i+2),cv,x,152.4,{'1':'SUM','2':'GAIN_'+ref},C,angle=90,autolabel=False)
 left=x-12.7;right=x+12.7
 for z in [p,c]:wire(z['1'],(right,z['1'][1]));wire(z['2'],(left,z['2'][1]))
 # Rotation 90: pin1 right, pin2 left. SUM at left would reverse passive nets only; label explicit.
 wire((left,134.62),(left,152.4));wire((right,134.62),(right,152.4));label('SUM',left,134.62);label('GAIN_'+ref,right,152.4)
 add('Conn_01x02','JP'+str(i+1),'JP_G'+ref,x+25.4,173.99,{'1':'GAIN_'+ref,'2':'TIA_OUT'},H)
note('POWER OFF to change gain. Fit exactly ONE shunt. Never operate without feedback.',145,189,1.35)
note('06  Two buffered low-pass sections · 482 Hz each · science band DC–100 Hz',20,203,1.8)
passive('R','R6','3.3k 1%',38.1,228.6,'TIA_OUT','LP1',90);passive('C','C12','100n X7R',66.04,248.92,'LP1','GND')
add('OPA2320','U2','OPA2320',99.06,228.6,{'3':'LP1','2':'BUF1','1':'BUF1'},SO)
passive('R','R7','3.3k 1%',139.7,228.6,'BUF1','LP2',90);passive('C','C13','100n X7R',167.64,248.92,'LP2','GND')
add('OPA2320','U2','OPA2320',198.12,228.6,{'5':'LP2','6':'FILTER_OUT','7':'FILTER_OUT'},SO,unit=2)
passive('R','R8','1k 1%',243.84,228.6,'FILTER_OUT','ADC_OUT',90);passive('C','C14','10n X7R',274.32,248.92,'ADC_OUT','GND')
add('BAT54S','D2','BAT54S',304.8,226.06,{'1':'GND','2':'3V3D','3':'ADC_OUT'},'Package_TO_SOT_SMD:SOT-23')
add('Conn_01x02','JP1','JP_ADC',358.14,228.6,{'1':'ADC_OUT','2':'ADC_LINK'},H)
note('JP_ADC: open before independent powering. No hot plugging.\nClamps do not provide powered-off isolation. Verify rail ramps.',292,247,1.2)
for n,(name,x) in enumerate(zip(['3V3A','VREF','TIA','FILTER','ADC','GND'],[30.48,71.12,111.76,152.4,193.04,233.68]),1):
 net={'TIA':'TIA_OUT','FILTER':'FILTER_OUT','ADC':'ADC_OUT'}.get(name,name)
 add('TestPoint','TP'+str(n),'TP_'+name,x,276.86,{'1':net},'TestPoint:TestPoint_Pad_D1.5mm')
# Cache and local library share byte-identical symbol definitions.
(P/'Photodiode.kicad_sym').write_text('(kicad_symbol_lib (version 20241209)(generator "kicad_symbol_editor")\n'+'\n'.join(symbols.values())+'\n)')
(P/'sym-lib-table').write_text('(sym_lib_table (version 7)(lib (name "Photodiode")(type "KiCad")(uri "${KIPRJMOD}/Photodiode.kicad_sym")(options "")(descr "Project symbols with verified pin maps")))')
(P/'fp-lib-table').write_text('(fp_lib_table (version 7)(lib(name "Photodiode")(type "KiCad")(uri "${KIPRJMOD}/Photodiode.pretty")(options "")(descr "Vishay BPW34")))')
cache='\n'.join(s.replace('(symbol "'+n+'"','(symbol "Photodiode:'+n+'"',1) for n,s in symbols.items())
sch=f'(kicad_sch (version 20250114)(generator "eeschema")(uuid "{root}")(paper "A3")(title_block(title "Photodiode TIA / ESP32")(date "2026-09-27")(rev "A")(company "Engineering prototype — not fabrication released"))(lib_symbols {cache})\n'+ '\n'.join(items)+ '\n(embedded_fonts no))'
(P/'photodiode-tia-esp32.kicad_sch').write_text(sch)
if not (P/'photodiode-tia-esp32.kicad_pro').exists():(P/'photodiode-tia-esp32.kicad_pro').write_text(json.dumps({'meta':{'filename':'photodiode-tia-esp32.kicad_pro','version':1}},indent=2))
(P/'verification/component-manifest.json').write_text(json.dumps(manifest,indent=2))
