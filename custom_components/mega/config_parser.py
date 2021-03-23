from dataclasses import dataclass, field
from bs4 import BeautifulSoup

inputs = [
    'eact',
    'inta',
    'misc',
]
selectors = [
    'pty',
    'm',
    'gr',
    'd',
    'ety',
]


@dataclass(frozen=True, eq=True)
class Config:
    pty: str = None
    m: str = None
    gr: str = None
    d: str = None
    ety: str = None
    inta: str = field(compare=False, hash=False, default=None)
    misc: str = field(compare=False, hash=False, default=None)
    eact: str = field(compare=False, hash=False, default=None)
    src: BeautifulSoup = field(compare=False, hash=False, default=None)


def parse_config(page: str):
    page = BeautifulSoup(page, features="lxml")
    ret = {}
    for x in selectors:
        v = page.find('select', attrs={'name': x})
        if v is None:
            continue
        else:
            v = v.find(selected=True)
            if v:
                v = v['value']
                ret[x] = v
    for x in inputs:
        v = page.find('input', attrs={'name': x})
        if v:
            ret[x] = v['value']
    smooth = page.find('input', attrs={'name': 'misc'})
    if smooth is None or smooth.get('checked') is None:
        ret['misc'] = None
    return Config(**ret, src=page)


DIGITAL_IN = Config(pty="0")
RELAY_OUT = Config(pty="1", m="0")
PWM_OUT = Config(pty="1", m="1")
DS2413 = Config(pty="1", m="2")
MCP230 = Config(pty="4", m="1", gr="3", d="20")
MCP230_OUT = Config(ety="1")
MCP230_IN = Config(ety="0")
PCA9685 = Config(pty="4", m="1", gr="3", d="21")
OWIRE_BUS = Config(pty="3", d="5")

