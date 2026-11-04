# İstanbul'un barajları uzaydan

**Site:** https://birtohum.github.io/barajlar-uzaydan/

İstanbul'un 10 içme suyu barajının (Ömerli, Darlık, Elmalı, Terkos, Alibey, Büyükçekmece, Sazlıdere,
Istrancalar, Kazandere, Pabuçdere) **su yüzeyi alanı**, 2017'den bugüne Sentinel-2 uydu görüntülerinden
birkaç günde bir ölçülür. GitHub Actions her sabah yeni görüntüleri arar, ölçer ve siteyi günceller.

## Yöntem

1. **Görüntü:** Copernicus Sentinel-2 L2A (yüzey yansıtımı), AWS açık veri kopyası.
   Arama: [Element84 Earth Search STAC](https://earth-search.aws.element84.com/v1), koleksiyon `sentinel-2-l2a`.
   Hesap/anahtar gerekmez. Yalnız barajın çevresindeki pencere okunur (COG aralık istekleri).
2. **Su:** NDWI = (B03 − B08) / (B03 + B08) > 0, 10 m çözünürlük.
3. **Bulut:** Sen2Cor sahne sınıflaması (SCL) 0, 1, 3, 8, 9, 10, 11 "görünmez" sayılır. Baraj çerçevesinin
   %3'ünden fazlası görünmezse ölçüm atılır; daha azsa görünmeyen kısım, görünen kısmın su oranıyla doldurulur.
4. **Sınır:** OpenStreetMap göl poligonu + 30 m tampon (`poligon.py`, `veri/barajlar.geojson`).
5. **Şüpheli ölçüm:** ±45 gün içinde zamanca en yakın 6 ölçümün medyanından %15'ten (Elmalı, Istrancalar, Kazandere, Pabuçdere için %25)
   fazla sapan değerler grafikten çıkarılır (çoğunlukla maskenin kaçırdığı ince bulut/pus).
6. **"En dolu":** 2017'den beri temiz ölçümlerin 98. yüzdeliği; resmî azami alan değildir.
7. **Karşılaştırma:** İBB Açık Veri Portalı "İstanbul Barajları Günlük Doluluk Oranları" (İSKİ; 2017 – Şubat 2024,
   sonrası yayımlanmadı). İSKİ'nin güncel API'si dışarıya kapalı olduğu için kullanılmıyor.

ESA 2022'den beri (işleme sürümü 04.00+) ham değerlere +1000 ekliyor; Earth Search bunu COG'larda zaten
geri aldığında (`earthsearch:boa_offset_applied`) meta verideki −0.1 ötelemesi ikinci kez uygulanmaz (`cek.py: bant`).

## Sınırlar

- **Alan ≠ hacim.** Yüzey alanı su miktarıyla aynı oranda değişmez; kıyılar sığ olduğu için alan, hacimden yavaş/farklı düşer.
- 10 m piksel: kıyı pikselleri karışık; küçük barajlarda (Elmalı ~0,9 km², Istrancalar ~0,8 km²) göreli hata büyük.
- Bulutlu kış aylarında haftalarca ölçüm olmayabilir; bulut maskesi her bulutu yakalamaz.
- Bulanık ya da yosunla kaplı su NDWI'da kara gibi görünebilir.
- OSM çizgisinin 30 m ötesine taşan su sayılmaz.
- Yeşilçay bir regülatör sistemi (göl yüzeyi yok), dahil değil. Istrancalar'da Büyükdere bendi OSM'de göl olarak çizili değil.

## Çalıştırma

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt pytest
python -m pytest -q          # alan hesabı testleri
python cek.py                # tüm arşiv (ilk sefer ~1 saat); --gun 20 yalnız son 20 gün
python uret.py               # site/veri/*.json ve site/gorsel/*
python -m http.server -d site
```

Dosyalar: `barajlar.py` (liste), `poligon.py` (OSM → poligon), `olcum.py` (alan hesabı, saf numpy),
`cek.py` (STAC + ölçüm → `veri/olcumler.csv`), `uret.py` (site verisi + görseller), `site/` (statik site).

## Lisans ve kaynaklar

Kod: Apache-2.0. Uydu verisi: Copernicus Sentinel-2 (ESA), değiştirilerek kullanıldı.
Baraj sınırları: © OpenStreetMap katkıcıları (ODbL). Doluluk oranları: İBB Açık Veri Portalı (İBB Açık Veri Lisansı).
