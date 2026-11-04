"""veri/osm_ham.json'daki OSM geometrilerinden baraj poligonlarını kurar -> veri/barajlar.geojson

OSM çoklu poligonlarında dış/iç halkalar parça parça yollar halinde gelir; burada
birleştirilip (linemerge + polygonize) dış halkalardan iç halkalar çıkarılır.
"""
import json, warnings
import shapely.ops
warnings.filterwarnings("ignore", category=DeprecationWarning)
from shapely.geometry import LineString, Polygon, MultiPolygon, mapping, shape
from shapely.ops import linemerge, polygonize, unary_union, transform
from pyproj import Transformer

from barajlar import BARAJLAR

UTM = Transformer.from_crs(4326, 32635, always_xy=True)


def _cizgi(geom):
    return LineString([(p["lon"], p["lat"]) for p in geom])


def eleman_poligonu(e):
    if e["type"] == "way":
        return Polygon([(p["lon"], p["lat"]) for p in e["geometry"]])
    dis = [_cizgi(m["geometry"]) for m in e["members"] if m["type"] == "way" and m.get("role", "outer") in ("outer", "")]
    ic = [_cizgi(m["geometry"]) for m in e["members"] if m["type"] == "way" and m.get("role") == "inner"]
    d = unary_union(list(polygonize(linemerge(dis))))
    if ic:
        d = d.difference(unary_union(list(polygonize(linemerge(ic)))))
    return d


def utm(g):
    return shapely.ops.transform(UTM.transform, g)


def kur(ham_yolu="veri/osm_ham.json", cikti="veri/barajlar.geojson"):
    ham = json.load(open(ham_yolu, encoding="utf8"))
    dizin = {(e["type"], e["id"]): e for e in ham["elements"]}
    ozellikler = []
    for b in BARAJLAR:
        parcalar = [eleman_poligonu(dizin[k]) for k in b["osm"]]
        g = unary_union(parcalar).buffer(0)
        alan = utm(g).area / 1e6
        ozellikler.append({"type": "Feature", "geometry": mapping(g),
                           "properties": {"kod": b["kod"], "ad": b["ad"], "osm_alan_km2": round(alan, 3)}})
        print(f"{b['ad']:14s} OSM alanı {alan:7.2f} km²  ({g.geom_type})")
    json.dump({"type": "FeatureCollection", "features": ozellikler}, open(cikti, "w", encoding="utf8"), ensure_ascii=False)


if __name__ == "__main__":
    kur()
