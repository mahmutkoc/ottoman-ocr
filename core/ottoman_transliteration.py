"""
Aşama 2: Arap harfli metin → Latin harfli Türkçe transkripsiyon
Kural tabanlı, deterministik, tamamen offline.

Sistem: İslam Ansiklopedisi / DİA transliterasyon standardına yakın,
        pratik okunabilirlik öncelikli basitleştirilmiş versiyon.

Sınır: Arap yazısı sesli harf taşımaz (abjad). Bu nedenle:
  - Sesli harfler büyük ölçüde bağlam/sözlük gerektirdiğinden yazılmaz.
  - Uzun ünlüler (hareke olmadığında) kısa okunur.
  - Çıktı "iskelet" transkripsiyon: konsonantlar + uzun ünlüler.
"""

# ──────────────────────────────────────────────
# Harf-harf çeviri tablosu
# ──────────────────────────────────────────────
HARF_TABLOSU: dict[str, str] = {
    # Elif grubu
    "ا": "a",   # elif (kelime başı ünlü taşıyıcı)
    "أ": "a",
    "إ": "i",
    "آ": "â",   # uzun a
    "ٱ": "a",   # vasıl elifı

    # Be grubu
    "ب": "b",
    "پ": "p",   # Osmanlıya özgü

    # Te grubu
    "ت": "t",
    "ث": "s",   # se (Türkçede s)
    "ة": "t",   # ta merbuta (izafet eki)

    # Cim grubu
    "ج": "c",
    "چ": "ç",   # Osmanlıya özgü
    "ح": "h",   # he-i huttî
    "خ": "h",   # hı (Türkçede h)

    # Dal grubu
    "د": "d",
    "ذ": "z",   # zel (Türkçede z)

    # Re grubu
    "ر": "r",
    "ز": "z",
    "ژ": "j",   # Osmanlıya özgü (je)

    # Sin grubu
    "س": "s",
    "ش": "ş",
    "ص": "s",   # sad (Türkçede s)
    "ض": "d",   # dat (Türkçede d)

    # Tı grubu
    "ط": "t",   # tı (Türkçede t)
    "ظ": "z",   # zı (Türkçede z)

    # Ayn grubu
    "ع": "",    # ayın (Türkçede sessiz, görmezden gel)
    "غ": "ğ",

    # Fe grubu
    "ف": "f",
    "ق": "k",   # kaf (Türkçede k/ḳ)

    # Kef grubu
    "ك": "k",
    "ک": "k",
    "گ": "g",   # Osmanlıya özgü
    "ڭ": "ñ",   # sağır kef (Osmanlı n-g)

    # Lam / Mim / Nun
    "ل": "l",
    "م": "m",
    "ن": "n",

    # Vav
    "و": "v",   # konsonant olarak v; ünlü bağlamda u/ü/o/ö
    "ؤ": "v",

    # He
    "ه": "h",
    "ھ": "h",
    "ح": "h",

    # Ye
    "ي": "y",   # konsonant olarak y; ünlü bağlamda i/ı/î
    "ی": "y",
    "ئ": "y",

    # Hemze
    "ء": "",    # hemze (görmezden gel)
    "ٔ": "",

    # Ligature (özel birleşimler)
    "لا": "lâ",
    "لأ": "lâ",
    "لآ": "lâ",
    "لإ": "li",

    # Hareke (sesli harf işaretleri — varsa)
    "َ": "a",   # fetha
    "ِ": "i",   # kesre
    "ُ": "u",   # damme
    "ً": "an",  # tenvin fetha
    "ٍ": "in",  # tenvin kesre
    "ٌ": "un",  # tenvin damme
    "ّ": "",    # şedde (konsonant iki kez yazılmaz, boş bırak)
    "ْ": "",    # sükun
    "ٰ": "â",   # elif maksurenin üstündeki işaret
}

# Noktalama / sayılar — olduğu gibi aktar
GECERLI_KARAKTERLER = set(" \t\n.,;:!?()[]{}'\"-–—/\\0123456789٠١٢٣٤٥٦٧٨٩")

# Hareke işaretleri: kelime sonu tespiti yaparken "harf" sayılmaz, atlanır
HAREKELER = set("ًٌٍَُِّْٰ")

# Kelime sonu He: Osmanlıca'da kelime sonundaki ه/ھ çoğunlukla sessiz/sesli
# harf işaretidir (örn. "ايسه" → "ise", "ايله" → "ile"), konsonant "h" değil.
KELIME_SONU_HE = {"ه", "ھ"}


def _kelime_sonu_mu(metin: str, i: int) -> bool:
    """i konumundaki harfin, harekeler hariç, kelimenin son harfi olup olmadığını kontrol eder."""
    j = i + 1
    while j < len(metin):
        ch = metin[j]
        if ch.isspace():
            return True
        if ch in HAREKELER:
            j += 1
            continue
        return False
    return True


def harf_cevir(harf: str) -> str:
    """Tek bir Arap harfini Latin karşılığına çevir."""
    return HARF_TABLOSU.get(harf, harf if harf in GECERLI_KARAKTERLER else "")


def metin_transkribe(arapca_metin: str) -> str:
    """
    Arap harfli metni Latin harfli transkripsiyona çevir.

    Özellikler:
    - Ligature'ları önce kontrol eder (لا → lâ)
    - Bilinmeyen karakterleri siler
    - Çift boşlukları temizler
    """
    if not arapca_metin:
        return ""

    sonuc = []
    i = 0
    metin = arapca_metin

    while i < len(metin):
        # Önce 2 karakterlik ligature dene
        if i + 1 < len(metin):
            iki_harf = metin[i:i+2]
            if iki_harf in HARF_TABLOSU:
                sonuc.append(HARF_TABLOSU[iki_harf])
                i += 2
                continue

        # Kelime sonu He: sessiz/sesli harf işareti → "h" değil "e"
        if metin[i] in KELIME_SONU_HE and _kelime_sonu_mu(metin, i):
            sonuc.append("e")
            i += 1
            continue

        # Tek harf
        sonuc.append(harf_cevir(metin[i]))
        i += 1

    # Temizle: çift boşluk, baş/son boşluk
    cikti = "".join(sonuc)
    cikti = " ".join(cikti.split())
    return cikti


def satirlar_transkribe(satirlar: list[str]) -> str:
    """
    Arapça satır listesini transkribe edip tek metin olarak birleştir.
    Her satır yeni satıra yazılır.
    """
    sonuclar = []
    for satir in satirlar:
        latin = metin_transkribe(satir)
        if latin.strip():
            sonuclar.append(latin)
    return "\n".join(sonuclar)


# ──────────────────────────────────────────────
# Hızlı test
# ──────────────────────────────────────────────
if __name__ == "__main__":
    ornekler = [
        "وسائر دورت يوز قدر افراددر",
        "همايون قاضبسي ولدان زاده",
        "فرض ايده لم ديار كفاري غارت",
    ]
    for ornek in ornekler:
        print(f"Arapça : {ornek}")
        print(f"Latin  : {metin_transkribe(ornek)}")
        print()
