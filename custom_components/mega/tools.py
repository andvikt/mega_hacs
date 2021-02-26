_params = ['m', 'click', 'cnt', 'pt']


def make_ints(d: dict):
    for x in _params:
        try:
            d[x] = int(d.get(x, 0))
        except (ValueError, TypeError):
            pass
    if 'm' not in d:
        d['m'] = 0
    if 'click' not in d:
        d['click'] = 0


def int_ignore(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return x