"""Independently check critical Rev A connectivity in KiCad XML netlist.

Usage: python tools/check_hardware_contract.py exported-netlist.xml
KiCad ERC cannot detect swapped but electrically compatible passive pins.
"""
from pathlib import Path
import sys
import re
import math
import xml.etree.ElementTree as ET


def check(path):
    root = ET.parse(path).getroot()
    components = {c.attrib['ref']: c for c in root.findall('./components/comp')}
    pins = {}
    for net in root.findall('./nets/net'):
        name = net.attrib['name'].lstrip('/')
        for node in net.findall('node'):
            pins[(node.attrib['ref'], node.attrib['pin'])] = name
    # Contract names (J_ESP32, JP_*, TP_*) are carried in the Value field so
    # references stay numerically annotated (J1, JP1..4, TP1..6).
    alias = {c.findtext('value', ''): ref for ref, c in components.items()
             if re.fullmatch(r'J_ESP32|JP_[A-Z0-9]+|TP_[A-Z0-9]+', c.findtext('value', ''))}
    components.update({name: components[ref] for name, ref in alias.items()})
    pins.update({(name, p): n for name, ref in alias.items() for (r, p), n in list(pins.items()) if r == ref})
    errors = []
    expected = {
        'U1': {'1':'TIA_OUT', '2':'SUM', '3':'VREF', '4':'GND', '6':'VREF', '7':'VREF', '8':'3V3A'},
        'U2': {'4':'GND', '7':'FILTER_OUT', '6':'FILTER_OUT', '8':'3V3A'},
        'U3': {'1':'VBUS_5V', '2':'GND', '3':'VBUS_5V', '5':'3V3A'},
        'D1': {'1':'3V3A', '2':'SUM'},
        'D2': {'1':'GND', '2':'3V3D', '3':'ADC_OUT'},
        'J_ESP32': {'1':'VBUS_5V','2':'GND','3':'3V3D','4':'GND','5':'ADC_LINK','6':'GND'},
    }
    for ref, mapping in expected.items():
        for pin, net in mapping.items():
            actual = pins.get((ref, pin))
            if actual != net:
                errors.append(f'{ref}.{pin}: expected {net}, got {actual}')
    for ref, substring in [('U1','OPA2320'),('U2','OPA2320'),('U3','TPS7A2033'),('D1','BPW34'),('D2','BAT54S')]:
        value = components[ref].findtext('value', '') if ref in components else ''
        if substring not in value:
            errors.append(f'{ref}: expected {substring}, got {value}')
    def nets(ref):
        return {n for (r,p),n in pins.items() if r == ref}
    if nets('JP_ADC') != {'ADC_OUT','ADC_LINK'}:
        errors.append('JP_ADC must isolate ADC_OUT from ADC_LINK')
    for ref in ['JP_G10K','JP_G100K','JP_G1M']:
        connected = nets(ref)
        if len(connected) != 2 or 'TIA_OUT' not in connected or 'SUM' in connected:
            errors.append(f'{ref}: selection link must be at output end of paired feedback branch: {connected}')
    def numeric(ref):
        value = components[ref].findtext('value', '').replace('Ω', '')
        match = re.match(r'([0-9.]+)\s*([pnuµmkKM]?)', value)
        if not match:
            return None
        scale = {'':1, 'p':1e-12, 'n':1e-9, 'u':1e-6, 'µ':1e-6, 'm':1e-3, 'k':1e3, 'K':1e3, 'M':1e6}
        return float(match[1]) * scale[match[2]]
    def require_part(prefix, endpoints, value, purpose):
        found = [ref for ref in components if ref.startswith(prefix) and nets(ref) == set(endpoints)
                 and numeric(ref) is not None and math.isclose(numeric(ref), value, rel_tol=1e-6)]
        if not found:
            errors.append(f'{purpose}: missing {prefix}={value:g} between {endpoints}')
    for link,resistance,capacitance in [('JP_G10K',1e4,1e-9),('JP_G100K',1e5,100e-12),('JP_G1M',1e6,10e-12)]:
        branch = nets(link) - {'TIA_OUT'}
        if len(branch) == 1:
            endpoints = ['SUM', next(iter(branch))]
            require_part('R', endpoints, resistance, link)
            require_part('C', endpoints, capacitance, link)
    for pin,pinout in [('3','1'),('5','7')]:
        node = pins.get(('U2',pin))
        source = 'TIA_OUT' if pin == '3' else pins.get(('U2','1'))
        require_part('R', [source,node], 3300, 'filter series resistor')
        require_part('C', [node,'GND'], 100e-9, 'filter shunt capacitor')
        inv = '2' if pin == '3' else '6'
        if pins.get(('U2',inv)) != pins.get(('U2',pinout)):
            errors.append(f'U2 follower feedback mismatch at pin {inv}')
    require_part('R', ['FILTER_OUT','ADC_OUT'], 1000, 'ADC series resistor')
    require_part('C', ['ADC_OUT','GND'], 10e-9, 'ADC reservoir')
    div = pins.get(('U1','5'))
    require_part('R', ['3V3A',div], 10000, 'reference upper divider')
    require_part('R', [div,'GND'], 10000, 'reference lower divider')
    require_part('C', [div,'GND'], 10e-6, 'reference reservoir')
    require_part('C', [div,'GND'], 100e-9, 'reference bypass')
    for ref in components:
        if ref.startswith('C') and nets(ref) == {'VREF','GND'}:
            errors.append('Capacitor directly on VREF buffer output: ' + ref)
    for suffix, net in [('3V3A','3V3A'),('VREF','VREF'),('TIA','TIA_OUT'),('FILTER','FILTER_OUT'),('ADC','ADC_OUT'),('GND','GND')]:
        ref = 'TP_' + suffix
        if nets(ref) != {net}:
            errors.append(f'{ref}: expected {net}, got {nets(ref)}')
    for ref,c in components.items():
        if not c.findtext('footprint') and not ref.startswith('#'):
            errors.append(f'{ref}: missing footprint')
    if errors:
        raise ValueError('\n'.join(errors))
    print(f'PASS: critical locked pin mappings, isolation links and footprints ({len(components)} components).')

if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    try:
        check(Path(sys.argv[1]))
    except (ValueError, ET.ParseError) as exc:
        sys.exit(str(exc))
