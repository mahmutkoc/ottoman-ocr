"""
Sesli harf tamamlama modülünün CER'ini ölçer.
Eğitim setinden örnek satırlar alır, sesli harfleri çıkarıp
(iskelet haline getirip) yeniden tamamlatır, orijinaliyle karşılaştırır.
"""

import random
import re
import sys
from pathlib import Path

import pandas as pd
from rapidfuzz.distance import Levenshtein

sys.path.insert(0, str(Path(__file__).parent))
from core.vowel_restore import metin_tamamla, _iskelet

random.seed(42)

XLSX = Path(__file__).parent / "osmanli_transkripsiyon.xlsx"
ORNEK_SAYISI = 200


def satiri_iskelete_cevir(satir: str) -> str:
    """Bir satırdaki her kelimeyi konsonant iskeletine çevir (simüle edilmiş OCR çıkışı)."""
    kelimeler = satir.split()
    iskelet_kelimeler = [_iskelet(re.sub(r"[^\w]", "", k)) or k for k in kelimeler]
    return " ".join(iskelet_kelimeler)


def cer(ref: str, hyp: str) -> float:
    if not ref:
        return 0.0
    return Levenshtein.distance(ref, hyp) / len(ref)


def main():
    df = pd.read_excel(XLSX)
    satirlar = df["text"].dropna().astype(str).tolist()
    random.shuffle(satirlar)
    ornekler = satirlar[:ORNEK_SAYISI]

    toplam_cer = 0.0
    tam_dogru = 0

    for orijinal in ornekler:
        iskelet = satiri_iskelete_cevir(orijinal)
        tamamlanmis = metin_tamamla(iskelet)
        c = cer(orijinal.lower(), tamamlanmis.lower())
        toplam_cer += c
        if tamamlanmis.lower().strip() == orijinal.lower().strip():
            tam_dogru += 1

    ortalama_cer = toplam_cer / len(ornekler)
    print(f"Örnek sayısı     : {len(ornekler)}")
    print(f"Ortalama CER     : {ortalama_cer*100:.2f}%")
    print(f"Tam doğru satır  : {tam_dogru}/{len(ornekler)} ({tam_dogru/len(ornekler)*100:.1f}%)")

    print("\nÖrnekler:")
    for orijinal in ornekler[:5]:
        iskelet = satiri_iskelete_cevir(orijinal)
        tamamlanmis = metin_tamamla(iskelet)
        print(f"  Orijinal : {orijinal}")
        print(f"  İskelet  : {iskelet}")
        print(f"  Tamamlanan: {tamamlanmis}")
        print()


if __name__ == "__main__":
    main()
