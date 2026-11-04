(function () {
  "use strict";
  const AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"];
  const sayi = (x, b = 1) => x.toLocaleString("tr-TR", { minimumFractionDigits: b, maximumFractionDigits: b });
  const tarihYaz = (t) => { const [y, a, g] = t.split("-").map(Number); return `${g} ${AYLAR[a - 1]} ${y}`; };
  // Yılın okunuşuna göre bulunma eki: 2019'da, 2021'de, 2023'te, 2026'da
  const BIRLER = ["", "de", "de", "te", "te", "te", "da", "de", "de", "da"];
  const ONLAR = ["de", "da", "de", "da", "ta", "de", "ta", "te", "de", "da"];
  const ekDe = (t) => { const y = Number(t.slice(0, 4)); return (y % 10 ? BIRLER[y % 10] : ONLAR[Math.floor(y / 10) % 10]); };
  const tarihDe = (t) => `${tarihYaz(t)}'${ekDe(t)}`;
  const $ = (s) => document.querySelector(s);
  const ns = "http://www.w3.org/2000/svg";
  const el = (ad, ozel = {}, ebeveyn) => { const e = document.createElementNS(ns, ad); for (const k in ozel) e.setAttribute(k, ozel[k]); if (ebeveyn) ebeveyn.appendChild(e); return e; };
  const gun = (t) => Date.parse(t + "T00:00:00Z");

  let ozet, secili = null, aralik = 1, detayVeri = {};

  fetch("veri/ozet.json").then((r) => r.json()).then((o) => {
    ozet = o;
    const t = o.toplam;
    $("#manset .manset-yazi").innerHTML =
      `<span class="buyuk">%${sayi(t.yuzde, 0)}</span>` +
      `İstanbul'un ${o.barajlar.length} barajında suyla kaplı alan, en dolu zamanlarına göre yüzde ${sayi(t.yuzde, 0)} seviyesinde ` +
      `(${sayi(t.son_km2, 1)} km² / ${sayi(t.dolu_km2, 1)} km²). <span style="font-weight:400;font-size:.95rem;color:#c9d6ea">Her baraj için son bulutsuz uydu görüntüsü kullanıldı.</span>`;
    requestAnimationFrame(() => { $("#manset-cubuk").style.width = Math.min(100, t.yuzde) + "%"; });
    $("#guncelleme").textContent = "Son güncelleme: " + new Date(o.guncelleme).toLocaleString("tr-TR", { dateStyle: "long", timeStyle: "short" }) +
      ". Her gün yeni uydu görüntüsü aranır; bulutlu günler atlanır.";
    kartlar();
    const ilk = (location.hash || "").slice(1);
    if (o.barajlar.some((b) => b.kod === ilk)) sec(ilk, false);
  }).catch(() => { $("#manset .manset-yazi").textContent = "Veri yüklenemedi."; });

  function degisimYaz(b) {
    if (!b.gecen_yil) return "";
    const f = b.son.yuzde - b.gecen_yil.yuzde;
    if (Math.abs(f) < 1) return "geçen yılla aynı";
    return f < 0 ? `<span class="ok-asagi">▼ ${sayi(-f, 0)} puan</span> geçen yıla göre` : `<span class="ok-yukari">▲ ${sayi(f, 0)} puan</span> geçen yıla göre`;
  }

  function kartlar() {
    const kap = $("#kartlar");
    kap.innerHTML = "";
    for (const b of ozet.barajlar) {
      const k = document.createElement("button");
      k.className = "kart"; k.dataset.kod = b.kod;
      k.innerHTML = `<div class="siluet"><img src="gorsel/${b.kod}_siluet.png" alt="${b.ad} barajının uydudan su haritası" loading="lazy"></div>
        <div><div class="ad">${b.ad}</div><div class="yaka">${b.yaka} yakası</div></div>
        <div class="yuzde">%${sayi(b.son.yuzde, 0)} <small>dolu yüzey</small></div>
        <div class="degisim">${degisimYaz(b)}</div>
        <div class="kucuk">son temiz görüntü: ${tarihYaz(b.son.tarih)}</div>`;
      k.addEventListener("click", () => sec(b.kod, true));
      kap.appendChild(k);
    }
  }

  function sec(kod, kaydir) {
    secili = kod;
    history.replaceState(null, "", "#" + kod);
    document.querySelectorAll(".kart").forEach((k) => k.classList.toggle("secili", k.dataset.kod === kod));
    const getir = detayVeri[kod] ? Promise.resolve(detayVeri[kod]) : fetch(`veri/${kod}.json`).then((r) => r.json()).then((d) => (detayVeri[kod] = d));
    getir.then((d) => {
      ciz(d);
      if (kaydir) $("#detay").scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function ciz(d) {
    $("#detay").hidden = false;
    $("#d-ad").textContent = d.ad + (d.not ? "" : "");
    const fark = 100 * (d.son.km2 - d.once.km2) / d.once.km2;
    const yon = fark < 0 ? `yüzde ${sayi(-fark, 0)} küçüldü` : `yüzde ${sayi(fark, 0)} büyüdü`;
    let cumle = `${tarihDe(d.once.tarih)} su <b>${sayi(d.once.km2, 1)} km²</b> yer kaplıyordu. ` +
      `${tarihDe(d.son.tarih)} <b>${sayi(d.son.km2, 1)} km²</b>. Yani su yüzeyi ${Math.abs(fark) < 1 ? "neredeyse hiç değişmedi" : yon}.`;
    cumle += ` <span class="kucuk">(1 km² ≈ 140 futbol sahası)</span>`;
    if (d.not) cumle += `<br><span class="kucuk">${d.not}</span>`;
    $("#d-cumle").innerHTML = cumle;
    $("#d-once").src = `gorsel/${d.kod}_once.jpg`; $("#d-once").alt = `${d.ad}, ${tarihYaz(d.once.tarih)} uydu görüntüsü`;
    $("#d-simdi").src = `gorsel/${d.kod}_simdi.jpg`; $("#d-simdi").alt = `${d.ad}, ${tarihYaz(d.son.tarih)} uydu görüntüsü`;
    $("#d-once-et").textContent = tarihYaz(d.once.tarih);
    $("#d-simdi-et").textContent = tarihYaz(d.son.tarih);
    kaydirici(50);
    $("#d-grafik-not").textContent = `${d.olcum_sayisi} temiz ölçüm (${tarihYaz(d.ilk_tarih)} tarihinden beri). ` +
      `Kesikli çizgi "en dolu" seviyesi: ${sayi(d.dolu_km2, 2)} km². Bulut maskesinin kaçırdığı düşünülen ${d.supheli_sayisi} ölçüm grafiğe alınmadı.`;
    grafik($("#grafik"), d.seri, { dolu: d.dolu_km2, birim: "km²", ondalik: 2 });
    const iskiKap = $("#d-iski");
    if (d.iski_seri) {
      iskiKap.hidden = false;
      grafik($("#grafik-iski"), d.iski_seri, { birim: "%", ondalik: 0, iski: true, ymin: 0, ymax: 100, tumu: true });
      const r = d.iski.spearman;
      const guc = r > 0.8 ? "çok güçlü" : r > 0.6 ? "güçlü" : r > 0.4 ? "orta" : "zayıf";
      $("#d-iski-not").textContent = `İBB Açık Veri'de yayımlanan son değer Şubat 2024'e ait. 2017–2024 arasında aynı güne denk gelen ${d.iski.n} ölçümde ` +
        `uydudan ölçülen alan ile İSKİ doluluğu arasındaki sıra korelasyonu ${sayi(r, 2)} (${guc}). Bu grafik her zaman 2017'den bugüne kadar olan aralığı gösterir; üstte "Tümü" seçilince iki grafik hizalanır.`;
    } else iskiKap.hidden = true;
    const tb = $("#d-tablo tbody"); tb.innerHTML = "";
    for (const [t, a] of d.seri.slice().reverse()) { const tr = document.createElement("tr"); tr.innerHTML = `<td>${t}</td><td>${sayi(a, 2)}</td>`; tb.appendChild(tr); }
  }

  // ---- önce/şimdi sürgüsü ----
  function kaydirici(v) {
    $("#d-ust-kat").style.width = v + "%";
    $("#d-ayrac").style.left = v + "%";
    const alt = $("#d-simdi");
    $("#d-once").style.width = alt.clientWidth + "px";
    $("#d-once").style.height = "auto";
  }
  $("#d-kaydir").addEventListener("input", (e) => kaydirici(e.target.value));
  window.addEventListener("resize", () => secili && kaydirici($("#d-kaydir").value));
  $("#d-simdi").addEventListener("load", () => kaydirici($("#d-kaydir").value));

  document.querySelectorAll(".dugmeler button").forEach((b) => b.addEventListener("click", () => {
    aralik = Number(b.dataset.aralik);
    document.querySelectorAll(".dugmeler button").forEach((x) => x.classList.toggle("secili", x === b));
    if (secili && detayVeri[secili]) ciz(detayVeri[secili]);
  }));

  // ---- zaman grafiği (tek seri, imleç + ipucu) ----
  function yuruyenMedyan(seri, gunPencere) {
    const t = seri.map((x) => gun(x[0])), w = gunPencere * 864e5, out = [];
    let a = 0, b = 0;
    for (let i = 0; i < seri.length; i++) {
      while (t[a] < t[i] - w) a++;
      while (b < seri.length && t[b] <= t[i] + w) b++;
      const v = seri.slice(a, b).map((x) => x[1]).sort((p, q) => p - q);
      out.push([seri[i][0], v[Math.floor(v.length / 2)]]);
    }
    return out;
  }

  function grafik(kap, tumSeri, o) {
    kap.innerHTML = "";
    if (!tumSeri.length) return;
    const ana = detayVeri[secili].seri;
    const sonT = gun(ana[ana.length - 1][0]);
    const basT = (aralik >= 99 || o.tumu) ? gun(detayVeri[secili].seri[0][0]) : sonT - aralik * 365.25 * 864e5;
    const seri = tumSeri.filter((x) => gun(x[0]) >= basT && gun(x[0]) <= sonT);
    const W = kap.clientWidth, H = kap.clientHeight, m = { l: 44, r: 12, t: 14, b: 26 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": o.iski ? "İSKİ doluluk oranı grafiği" : "Su yüzeyi alanı grafiği" }, kap);
    if (!seri.length) { el("text", { x: W / 2, y: H / 2, "text-anchor": "middle", class: "dolu-yazi" }, svg).textContent = "Bu aralıkta veri yok"; return; }
    const degerler = seri.map((x) => x[1]).concat(o.dolu ? [o.dolu] : []);
    let ymin = o.ymin ?? Math.min(...degerler), ymax = o.ymax ?? Math.max(...degerler);
    if (o.ymin == null) { const p = (ymax - ymin) * 0.12 || ymax * 0.1; ymin = Math.max(0, ymin - p); ymax += p; }
    const x = (t) => m.l + (gun(t) - basT) / (sonT - basT) * (W - m.l - m.r);
    const y = (v) => m.t + (1 - (v - ymin) / (ymax - ymin)) * (H - m.t - m.b);
    // ızgara + y ekseni
    const g = el("g", { class: "izgara eksen" }, svg);
    const adim = guzelAdim((ymax - ymin) / 4);
    for (let v = Math.ceil(ymin / adim) * adim; v <= ymax; v += adim) {
      el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v) }, g);
      el("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }, g).textContent = sayi(v, adim < 1 ? 1 : 0);
    }
    // x ekseni: yıllar veya aylar
    const ex = el("g", { class: "eksen" }, svg);
    const bas = new Date(basT), son = new Date(sonT);
    if ((sonT - basT) / 864e5 > 800) {
      for (let yil = bas.getUTCFullYear() + 1; yil <= son.getUTCFullYear(); yil++) {
        const t = `${yil}-01-01`; el("line", { x1: x(t), x2: x(t), y1: H - m.b, y2: H - m.b + 4, stroke: "currentColor" }, ex);
        el("text", { x: x(t), y: H - 6, "text-anchor": "middle" }, ex).textContent = (W < 500 && yil % 2) ? "" : yil;
      }
    } else {
      const d = new Date(Date.UTC(bas.getUTCFullYear(), bas.getUTCMonth() + 1, 1));
      let i = 0;
      while (d <= son) {
        const t = d.toISOString().slice(0, 10);
        if (i % (W < 500 ? 3 : 2) === 0) el("text", { x: x(t), y: H - 6, "text-anchor": "middle" }, ex).textContent =
          AYLAR[d.getUTCMonth()].slice(0, 3) + (d.getUTCMonth() === 0 ? " " + d.getUTCFullYear() : "");
        d.setUTCMonth(d.getUTCMonth() + 1); i++;
      }
    }
    if (o.dolu) {
      el("line", { x1: m.l, x2: W - m.r, y1: y(o.dolu), y2: y(o.dolu), class: "dolu-cizgi" }, svg);
      el("text", { x: W - m.r, y: y(o.dolu) - 6, "text-anchor": "end", class: "dolu-yazi" }, svg).textContent = "en dolu";
    }
    if (!o.iski) for (const p of seri) el("circle", { cx: x(p[0]), cy: y(p[1]), r: 2.5, class: "nokta" }, svg);
    const cizSeri = o.iski ? seri : yuruyenMedyan(seri, 10);
    // 45 günden uzun boşlukları çizgiyle birleştirme (bulutlu kış haftaları)
    let dd = "", onceki = null;
    for (const p of cizSeri) {
      const kop = onceki && (gun(p[0]) - gun(onceki[0])) / 864e5 > 45;
      dd += (dd && !kop ? "L" : "M") + x(p[0]).toFixed(1) + "," + y(p[1]).toFixed(1);
      onceki = p;
    }
    el("path", { d: dd, class: "cizgi" + (o.iski ? " iski" : "") }, svg);
    // imleç
    const imlec = el("line", { y1: m.t, y2: H - m.b, class: "imlec", visibility: "hidden" }, svg);
    const nokta = el("circle", { r: 5, class: "imlec-nokta", visibility: "hidden" }, svg);
    if (o.iski) nokta.style.fill = "var(--kum-koyu)";
    const kutu = document.createElement("div"); kutu.className = "ipucu-kutu"; kutu.hidden = true; kap.appendChild(kutu);
    const yakala = el("rect", { x: m.l, y: 0, width: W - m.l - m.r, height: H, fill: "transparent" }, svg);
    const goster = (ev) => {
      const r = svg.getBoundingClientRect();
      const px = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
      let en = seri[0], ef = Infinity;
      for (const p of seri) { const f = Math.abs(x(p[0]) - px); if (f < ef) { ef = f; en = p; } }
      imlec.setAttribute("x1", x(en[0])); imlec.setAttribute("x2", x(en[0])); imlec.setAttribute("visibility", "visible");
      nokta.setAttribute("cx", x(en[0])); nokta.setAttribute("cy", y(en[1])); nokta.setAttribute("visibility", "visible");
      kutu.hidden = false;
      kutu.innerHTML = `<b>${o.birim === "%" ? "%" + sayi(en[1], 0) : sayi(en[1], o.ondalik) + " " + o.birim}</b> · ${tarihYaz(en[0])}`;
      kutu.style.left = Math.min(Math.max(x(en[0]), 80), W - 80) + "px"; kutu.style.top = y(en[1]) + "px";
    };
    const gizle = () => { imlec.setAttribute("visibility", "hidden"); nokta.setAttribute("visibility", "hidden"); kutu.hidden = true; };
    yakala.addEventListener("pointermove", goster); yakala.addEventListener("pointerdown", goster);
    yakala.addEventListener("pointerleave", gizle);
  }

  function guzelAdim(x) {
    const u = Math.pow(10, Math.floor(Math.log10(x))), f = x / u;
    return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * u;
  }
  window.addEventListener("resize", () => { if (secili && detayVeri[secili]) { grafik($("#grafik"), detayVeri[secili].seri, { dolu: detayVeri[secili].dolu_km2, birim: "km²", ondalik: 2 }); } });
})();
