order ='brg'
rgb = 'rgb'

map_to_order = [rgb.index(x) for x in order]
map_from_order = [order.index(x) for x in rgb]


_rgb = [
        rgb[x] for x in map_to_order
    ]
_order = [
        _rgb[x] for x in map_from_order
    ]

print(_rgb, _order)