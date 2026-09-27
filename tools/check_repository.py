"""Check local Markdown links and accidental build/credential artifacts in Git."""
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote

root = Path(__file__).resolve().parents[1]
errors = []
for path in root.rglob('*.md'):
    if any(part.startswith('.') for part in path.relative_to(root).parts):
        continue
    for target in re.findall(r'\]\(([^)]+)\)', path.read_text()):
        target = target.split(' "')[0].strip('<>')
        if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
            continue
        target = unquote(target.split('#')[0])
        if target and not (path.parent / target).exists():
            errors.append(f'{path.relative_to(root)}: missing link {target}')
tracked = subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines()
for name in tracked:
    if any(part in {'.venv', '.pio', '__pycache__', '.pytest_cache'} for part in Path(name).parts):
        errors.append(f'Build/cache file tracked: {name}')
    if name.endswith('/secrets.h') or Path(name).name == '.env':
        errors.append(f'Credential configuration tracked: {name}')
    if name.startswith('simulation/models/') and Path(name).suffix.lower() in {'.lib', '.zip'}:
        errors.append(f'Non-redistributable vendor model tracked: {name}')
    item = root / name
    if item.is_file() and item.stat().st_size < 2_000_000:
        content = item.read_bytes()
        token_patterns = [rb'gh[pousr]_[A-Za-z0-9]{30,}', rb'github_pat_[A-Za-z0-9_]{40,}', rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----']
        if any(re.search(pattern, content) for pattern in token_patterns):
            errors.append(f'Possible credential content tracked: {name} (value withheld)')
if errors:
    print('\n'.join(errors))
    sys.exit(1)
print(f'PASS: Markdown links and {len(tracked)} tracked paths checked.')
