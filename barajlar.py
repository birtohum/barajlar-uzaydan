"""Ölçülen barajlar: OSM kimlikleri ve hangi Sentinel-2 karesinden okunacakları."""

# osm: (tür, kimlik) listesi; birden çok parça birleştirilir.
BARAJLAR = [
    {"kod": "omerli", "ad": "Ömerli", "yaka": "Anadolu", "kare": "35TPF",
     "osm": [("relation", 1175859)]},
    {"kod": "darlik", "ad": "Darlık", "yaka": "Anadolu", "kare": "35TQF",
     "osm": [("relation", 2173850)]},
    {"kod": "elmali", "ad": "Elmalı", "yaka": "Anadolu", "kare": "35TPF",
     "osm": [("relation", 2935606), ("relation", 20218068)],
     "not": "Elmalı-1 ve Elmalı-2 gölleri birlikte."},
    {"kod": "terkos", "ad": "Terkos", "yaka": "Avrupa", "kare": "35TPF",
     "osm": [("relation", 16915457)], "not": "Durusu (Terkos) Gölü."},
    {"kod": "alibey", "ad": "Alibey", "yaka": "Avrupa", "kare": "35TPF",
     "osm": [("relation", 2920345)]},
    {"kod": "buyukcekmece", "ad": "Büyükçekmece", "yaka": "Avrupa", "kare": "35TPF",
     "osm": [("relation", 2296756)]},
    {"kod": "sazlidere", "ad": "Sazlıdere", "yaka": "Avrupa", "kare": "35TPF",
     "osm": [("relation", 2920346)]},
    {"kod": "istrancalar", "ad": "Istrancalar", "yaka": "Avrupa", "kare": "35TNG",
     "osm": [("way", 214660324), ("way", 214660207), ("way", 180136929), ("way", 126794481)],
     "not": "Düzdere, Kuzuludere, Elmalıdere ve Sultanbahçedere gölleri birlikte. "
            "Büyükdere bendi OSM'de göl olarak çizili olmadığı için dahil değil."},
    {"kod": "kazandere", "ad": "Kazandere", "yaka": "Avrupa", "kare": "35TNG",
     "osm": [("relation", 2403691)]},
    {"kod": "pabucdere", "ad": "Pabuçdere", "yaka": "Avrupa", "kare": "35TNG",
     "osm": [("way", 214685189)]},
]
