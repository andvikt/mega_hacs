from dataclasses import dataclass, field
from bs4 import BeautifulSoup


@dataclass(frozen=True, eq=True)
class Config:
    pty: str = None
    m: str = None
    gr: str = None
    d: str = None
    inta: str = field(compare=False, hash=False, default=None)
    ety: str = None
    misc: str = field(compare=False, hash=False, default=None)


def parse_config(page: str):
    page = BeautifulSoup(page, features="lxml")
    ret = {}
    for x in [
        'pty',
        'm',
        'gr',
        'd',
        'ety',
    ]:
        v = page.find('select', attrs={'name': x})
        if v is None:
            continue
        else:
            v = v.find(selected=True)
            if v:
                v = v['value']
                ret[x] = v
    v = page.find('input', attrs={'name': 'inta'})
    if v:
        ret['inta'] = v['value']
    v = page.find('input', attrs={'name': 'misc'})
    if v:
        ret['misc'] = v.get('checked', False)
    return Config(**ret)


DIGITAL_IN = Config(pty="0")
RELAY_OUT = Config(pty="1", m="0")
PWM_OUT = Config(pty="1", m="1")
DS2413 = Config(pty="1", m="2")
MCP230 = Config(pty="4", m="1", gr="3", d="20")
MCP230_OUT = Config(ety="1")
MCP230_IN = Config(ety="0")
PCA9685 = Config(pty="4", m="1", gr="3", d="21")
OWIRE_BUS = Config(pty="3", d="5")

