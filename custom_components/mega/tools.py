def make_ints(d: dict):
    for x in d:
        try:
            d[x] = float(d[x])
        except ValueError:
            pass
    if 'm' not in d:
        d['m'] = 0
    if 'click' not in d:
        d['click'] = 0