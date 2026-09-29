#!/usr/bin/env python3
"""Re-export the reviewed Rev A only. Never edits KiCad sources or refills zones."""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'hardware/manufacturing/rev-a'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
lock=json.loads((OUT/'source-lock.json').read_text())
for name,digest in lock.items():
    if sha(ROOT/name)!=digest: raise SystemExit('Source changed; independent review and new source-lock required: '+name)
cli=os.environ.get('KICAD_CLI') or shutil.which('kicad-cli')
if not cli:
    candidate=Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
    if candidate.is_file(): cli=str(candidate)
if not cli: raise SystemExit('Install KiCad 9 CLI or set KICAD_CLI')
board='hardware/kicad/photodiode-tia-esp32.kicad_pcb'
sch='hardware/kicad/photodiode-tia-esp32.kicad_sch'
def run(*args): subprocess.run([cli,*map(str,args)],cwd=ROOT,check=True)
with tempfile.TemporaryDirectory(prefix='tia-fab-') as d:
    stage=Path(d)
    run('pcb','drc','--severity-all','--schematic-parity','--exit-code-violations','-o',stage/'drc.rpt',board)
    run('sch','erc','--severity-all','--exit-code-violations','-o',stage/'erc.rpt',sch)
    run('pcb','export','gerbers','--layers','F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts','--subtract-soldermask','-o',str(stage)+'/',board)
    run('pcb','export','drill','--format','excellon','--excellon-units','mm','--excellon-separate-th','--generate-map','--map-format','svg','-o',str(stage)+'/',board)
    run('pcb','export','svg','--layers','F.Fab,Edge.Cuts','--sketch-pads-on-fab-layers','--exclude-drawing-sheet','--page-size-mode','2','--mode-single','--black-and-white','-o',stage/'assembly-top.svg',board)
    for p in stage.glob('*.svg'):
        s=p.read_text()
        if p.name=='assembly-top.svg':
            s=re.sub(r'width="[^"]+" height="[^"]+"', 'width="180mm" height="135mm"',s,count=1)
            s=re.sub(r'viewBox="[^"]+"','viewBox="0 0 60 45"',s,count=1)
            s=s.replace('</desc>', '</desc>\n<rect x="0" y="0" width="60" height="45" fill="white"/>',1)
        p.write_text('\n'.join(l.rstrip() for l in s.splitlines())+'\n')
    required=['F_Cu.gtl','B_Cu.gbl','F_Mask.gts','B_Mask.gbs','F_Silkscreen.gto','B_Silkscreen.gbo','Edge_Cuts.gm1']
    for suffix in required:
        if not any(p.name.endswith(suffix) for p in stage.iterdir()): raise SystemExit('Missing Gerber '+suffix)
    drill_report={}
    for kind,expected in [('PTH',41),('NPTH',4)]:
        p=stage/f'photodiode-tia-esp32-{kind}.drl'
        s=p.read_text(); points=re.findall(r'^X(-?[\d.]+)Y(-?[\d.]+)$',s,re.M)
        if len(points)!=expected: raise SystemExit(f'{kind}: expected {expected} hits, found {len(points)}')
        xy=[(float(x),float(y)) for x,y in points]
        if not all(0<=x<=60 and -45<=y<=0 for x,y in xy): raise SystemExit('Drill outside board')
        drill_report[kind]={'hits':len(xy),'tools':re.findall(r'^T\d+C[\d.]+$',s,re.M),'extent_mm':[min(x for x,y in xy),min(y for x,y in xy),max(x for x,y in xy),max(y for x,y in xy)]}
    # A clean export directory prevents leftover layers from an earlier release.
    dest=OUT/'exports'
    if dest.exists(): shutil.rmtree(dest)
    shutil.copytree(stage,dest)
    (OUT/'export-check.json').write_text(json.dumps({'board_mm':[60,45],'drills':drill_report,'gerber_layers':7,'note':'Excellon absolute origin; negative Y follows KiCad export convention. 25 vias +16 component PTH; 4 NPTH.'},indent=2)+'\n')
manifest={'source_sha256':lock,'kicad_cli_version':subprocess.check_output([cli,'version'],text=True).strip(),'outputs_sha256':{str(p.relative_to(ROOT)):sha(p) for p in sorted(list(OUT.rglob('*'))+list((ROOT/'hardware/bom').glob('*'))+[Path(__file__).resolve()]) if p.is_file() and p.name!='manifest.json'}}
(OUT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Exported reviewed Rev A; all source checks and drill checks passed.')
