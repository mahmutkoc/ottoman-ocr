"""
Sesli harf tamamlama modülü (bağlam-duyarlı).

Strateji:
  1. Eğitim verisinden çıkarılan sözlükte iskelet için birden fazla
     aday kelime tutulur (frekanslarıyla birlikte).
  2. Konsonant iskeleti eşleşmesi dene (direkt veya semi-vokal kaldırılmış).
  3. Birden fazla aday varsa, önceki kelimeyle bigram modelinden
     bağlamsal skor hesaplanır — sadece en sık kelime değil, bağlama
     en uygun kelime seçilir.
  4. İskelet eşleşmezse fuzzy edit-distance ile en yakın kelimeleri bul,
     yine bağlama göre sırala.
  5. Hiçbiri başarısız olursa kelimeyi olduğu gibi bırak.
"""

import json
import re
from functools import lru_cache
from pathlib import Path

DICT_PATH   = Path(__file__).parent / "vowel_dict.json"
BIGRAM_PATH = Path(__file__).parent / "bigram_model.json"

SEMIVOKAL = set("yv")
SESLI_TR  = set("aeıioöuüâîû")


def _kelime_temizle(kelime: str) -> str:
    return re.sub(r"[^\w]", "", kelime.lower())


def _iskelet(kelime: str, semi_de_kaldir: bool = False) -> str:
    """
    ç→c normalize edilir: Osmanlıca'da ج (cim) harfi hem "c" hem "ç" sesini
    karşılayabildiğinden OCR çıkışı genelde "ç" yerine "c" üretir. Bu
    normalizasyon, build_vowel_dict.py'deki sözlük anahtarlarıyla hizalı
    kalmak için sorgu tarafında da uygulanır.
    """
    kaldir = SESLI_TR | (SEMIVOKAL if semi_de_kaldir else set())
    isk = "".join(c for c in kelime.lower() if c.isalpha() and c not in kaldir)
    return isk.replace("ç", "c")


@lru_cache(maxsize=1)
def _yukle_sozluk():
    """Sözlüğü yükle: {iskelet: [[kelime, frekans], ...]}"""
    if not DICT_PATH.exists():
        return {}, [], {}

    raw = json.loads(DICT_PATH.read_text(encoding="utf-8"))

    # Eski format desteği: {iskelet: "kelime"} → yeni formata çevir
    if raw and isinstance(next(iter(raw.values())), str):
        raw = {isk: [[kelime, 1]] for isk, kelime in raw.items()}

    iskelet_dict = raw
    tum_kelimeler = sorted({kelime for adaylar in raw.values() for kelime, _ in adaylar})

    # Semi-vokal kaldırılmış agresif iskelete göre indeks
    agresif_dict = {}
    for isk, adaylar in raw.items():
        for kelime, frekans in adaylar:
            agr = _iskelet(kelime, semi_de_kaldir=True)
            if not agr:
                continue
            agresif_dict.setdefault(agr, []).append([kelime, frekans])

    return iskelet_dict, tum_kelimeler, agresif_dict


@lru_cache(maxsize=1)
def _yukle_bigram():
    """Bigram modelini yükle: {onceki: {sonraki: frekans}}"""
    if not BIGRAM_PATH.exists():
        return {}
    return json.loads(BIGRAM_PATH.read_text(encoding="utf-8"))


def _bigram_skor(onceki_kelime: str, aday: str) -> int:
    """onceki_kelime → aday geçiş frekansı (geriye bağlam skoru)."""
    bigram = _yukle_bigram()
    return bigram.get(onceki_kelime, {}).get(aday, 0)


def _ileri_bigram_skor(aday: str, sonraki_iskelet: str | None) -> int:
    """
    aday → sonraki_iskelet ile eşleşen bir kelimeye geçiş frekansı (ileriye bağlam).
    Sonraki kelime henüz tamamlanmamış (sadece iskeleti bilinir), bu yüzden
    aday'ın bigram tablosundaki olası devamları arasında iskeleti eşleşen
    olup olmadığına bakılır. Örn: "kaç" → "dakika" geçişi var mı?
    """
    if not sonraki_iskelet:
        return 0
    bigram = _yukle_bigram()
    devamlar = bigram.get(aday, {})
    en_iyi = 0
    for devam_kelime, frekans in devamlar.items():
        if _iskelet(devam_kelime) == sonraki_iskelet and frekans > en_iyi:
            en_iyi = frekans
    return en_iyi


def _en_iyi_aday(adaylar: list, onceki_kelime: str | None, sonraki_iskelet: str | None = None) -> str:
    """
    Aday listesinden (kelime, frekans) bağlama göre en iyisini seç.
    Geri + ileri bağlam skorları toplanır; en yüksek toplam skora sahip
    aday seçilir. Hiçbir bağlam sinyali yoksa en sık geçen kelime alınır.
    """
    if not adaylar:
        return ""
    if len(adaylar) == 1:
        return adaylar[0][0]

    bağlamlı = []
    for kelime, frekans in adaylar:
        geri  = _bigram_skor(onceki_kelime, kelime) if onceki_kelime else 0
        ileri = _ileri_bigram_skor(kelime, sonraki_iskelet)
        bağlamlı.append((kelime, geri + ileri, frekans))

    en_iyi_bağlam = max(bağlamlı, key=lambda x: x[1])
    if en_iyi_bağlam[1] > 0:
        return en_iyi_bağlam[0]

    # Bağlam yoksa en sık geçen (liste zaten frekansa göre sıralı geliyor)
    return max(adaylar, key=lambda kv: kv[1])[0]


def kelime_tamamla(
    kelime: str,
    onceki_kelime: str | None = None,
    sonraki_kelime_ham: str | None = None,
    esik: float = 0.72,
) -> str:
    """
    Tek kelimeyi sesli harflerle tamamlamaya çalışır.
    onceki_kelime     : bağlam için önceki tamamlanmış kelime (varsa).
    sonraki_kelime_ham: bağlam için sonraki kelimenin henüz tamamlanmamış hali.
    """
    if not kelime or not kelime.strip():
        return kelime

    temiz = _kelime_temizle(kelime)
    if len(temiz) < 2:
        return kelime

    iskelet_dict, tum_kelimeler, agresif_dict = _yukle_sozluk()
    if not iskelet_dict:
        return kelime

    sonraki_iskelet = _iskelet(_kelime_temizle(sonraki_kelime_ham)) if sonraki_kelime_ham else None

    # 1. Direkt iskelet eşleşmesi (v/y konsonant olarak tutulur)
    isk = _iskelet(temiz)
    if isk in iskelet_dict:
        return _en_iyi_aday(iskelet_dict[isk], onceki_kelime, sonraki_iskelet)

    # 2. Semi-vokal dahil iskelet (v/y de çıkarılır) — sadece direkt eşleşme
    # yoksa denenir; "hava" gibi v'nin gerçek konsonant olduğu kelimelerde
    # direkt eşleşme zaten doğru sonucu verdiğinden buraya düşmez.
    agr = _iskelet(temiz, semi_de_kaldir=True)
    if agr in agresif_dict:
        return _en_iyi_aday(agresif_dict[agr], onceki_kelime, sonraki_iskelet)

    # 3. Fuzzy eşleşme
    hedef_uzunluk = len(temiz)
    adaylar = [k for k in tum_kelimeler if abs(len(k) - hedef_uzunluk) <= 3]

    if adaylar:
        try:
            from rapidfuzz import process, fuzz
            sonuclar = process.extract(
                temiz, adaylar,
                scorer=fuzz.ratio,
                score_cutoff=esik * 100,
                limit=5,
            )
            if sonuclar:
                fuzzy_adaylar = [[kelime_eslesen, skor] for kelime_eslesen, skor, _ in sonuclar]
                return _en_iyi_aday(fuzzy_adaylar, onceki_kelime, sonraki_iskelet)
        except ImportError:
            pass

    # 4. Bulunamadı
    return kelime


def metin_tamamla(latin_metin: str) -> str:
    """
    Latin konsonant transkripsiyon metnini kelime kelime, geri+ileri
    bağlamı takip ederek tamamlar. Noktalama ve boşlukları korur.
    """
    if not latin_metin.strip():
        return latin_metin

    parcalar = re.split(r"(\s+)", latin_metin)

    # Her parçayı (on, kelime, son) olarak ayrıştır, kelime parçalarının
    # indekslerini tut ki sonraki kelimeye ileri bakış yapılabilsin.
    ayristirilmis = []  # [(parca, on, kelime, son) | (parca, None, None, None) boşluk için]
    for parca in parcalar:
        if parca.strip() == "":
            ayristirilmis.append((parca, None, None, None))
            continue
        on_nok = re.match(r"^([^\w]*)(.*?)([^\w]*)$", parca, re.DOTALL)
        if on_nok:
            on, kelime, son = on_nok.groups()
            ayristirilmis.append((parca, on, kelime, son))
        else:
            ayristirilmis.append((parca, "", parca, ""))

    kelime_indeksleri = [i for i, (_, _, kelime, _) in enumerate(ayristirilmis) if kelime]

    sonuc = [None] * len(ayristirilmis)
    onceki_kelime = None

    for pos, i in enumerate(kelime_indeksleri):
        _, on, kelime, son = ayristirilmis[i]

        sonraki_ham = None
        if pos + 1 < len(kelime_indeksleri):
            sonraki_ham = ayristirilmis[kelime_indeksleri[pos + 1]][2]

        tamamlanmis = kelime_tamamla(kelime, onceki_kelime, sonraki_ham)
        onceki_kelime = tamamlanmis.lower()
        sonuc[i] = (on or "") + tamamlanmis + (son or "")

    # Boşluk/işaret parçalarını olduğu gibi yerine koy
    for i, (parca, on, kelime, son) in enumerate(ayristirilmis):
        if sonuc[i] is None:
            sonuc[i] = parca

    return "".join(sonuc)


# ── Hızlı test ─────────────────────────────────
if __name__ == "__main__":
    ornekler = [
        "vsayr drtyvzkdr afra addr",
        "klhrk rvslr avzrynh hcvmdh sbrszlk kvstryyvrd",
        "ak thfmh kydn ş kvrkvnc brsvrtdh",
    ]
    for ornek in ornekler:
        print(f"Giriş  : {ornek}")
        print(f"Çıkış  : {metin_tamamla(ornek)}")
        print()
