from math import *

__all__ = [
        "_TILE_SIZE",
        "_get_coordinate",
        ]

_TILE_SIZE = 256

def _get_coordinate(lat, long, zoom):
    n = 2 ** zoom

    xtile = ((long + 180) / 360) * n

    lat_radians = radians(lat)
    ytile = (1 - (log(tan(lat_radians) + 1 / cos(lat_radians)) / pi)) / 2 * n

    return (round(xtile * _TILE_SIZE), round(ytile * _TILE_SIZE))

