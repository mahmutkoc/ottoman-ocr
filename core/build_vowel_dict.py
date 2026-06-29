"""
Eğitim verisindeki Latin transkripsiyonlardan
konsonant_iskelet → tam_kelime sözlüğü oluşturur.
Çıktı: core/vowel_dict.json
"""

import json
import re
import unicodedata
from pathlib import Path
import pandas as pd

# Türkçe sesli harfler (kısa + uzun)
SESLI = set("aeıioöuüâîûAEIİOÖUÜÂÎÛ")

NORMALIZASYON = str.maketrans(
    "âîû",
    "aiu"
)


def konsonant_iskelet(kelime: str) -> str:
    """
    Kelimeden sesli harfleri çıkar → konsonant iskeleti döndür.
    ç→c normalize edilir: Osmanlıca'da ج (cim) harfi hem "c" hem "ç" sesini
    karşılayabildiğinden, OCR çıkışı genelde "ç" yerine "c" üretir. Bu
    normalize işlemi sözlük anahtarını OCR'ın gerçek çıkışıyla hizalar.
    """
    iskelet = "".join(c for c in kelime.lower() if c not in SESLI and c.isalpha())
    return iskelet.replace("ç", "c")


def normalize(kelime: str) -> str:
    """Uzun ünlü işaretlerini kısalt, küçük harfe çevir."""
    return kelime.lower().translate(NORMALIZASYON)


def sozluk_olustur(xlsx_yolu: str, max_aday: int = 5) -> dict:
    df = pd.read_excel(xlsx_yolu)
    sozluk = {}  # konsonant_iskelet → {tam_kelime: frekans}

    for metin in df["text"].dropna():
        kelimeler = str(metin).split()
        for kelime in kelimeler:
            # Noktalama temizle
            temiz = re.sub(r"[^\w''\-âîûÂÎÛ]", "", kelime, flags=re.UNICODE)
            temiz = temiz.strip("'-")
            if len(temiz) < 2:
                continue

            norm = normalize(temiz)
            iskelet = konsonant_iskelet(norm)

            if not iskelet:
                continue

            if iskelet not in sozluk:
                sozluk[iskelet] = {}
            sozluk[iskelet][norm] = sozluk[iskelet].get(norm, 0) + 1

    # Her iskelet için en sık geçen max_aday kelimeyi (kelime, frekans) olarak tut
    sonuc = {}
    for iskelet, adaylar in sozluk.items():
        sirali = sorted(adaylar.items(), key=lambda kv: -kv[1])[:max_aday]
        sonuc[iskelet] = [[kelime, frekans] for kelime, frekans in sirali]

    return sonuc


if __name__ == "__main__":
    xlsx = Path(r"C:\Users\user\ottoman-ocr\osmanli_transkripsiyon.xlsx")
    cikti = Path(r"C:\Users\user\ottoman-ocr\core\vowel_dict.json")

    print("Sözlük oluşturuluyor...")
    sozluk = sozluk_olustur(str(xlsx))
    print(f"  {len(sozluk)} konsonant iskeleti → tam kelime eşlemesi")

    # Örnekler
    ornekler = ["vsayr", "drtyvzkdr", "afraddr", "klhrk", "rvslr", "hcvmdh"]
    print("\nÖrnek eşlemeler (aday listesi):")
    for isk in ornekler:
        print(f"  {isk} → {sozluk.get(isk, '(bulunamadı)')}")

    cikti.write_text(json.dumps(sozluk, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSözlük kaydedildi: {cikti}")
