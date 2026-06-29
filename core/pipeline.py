"""
2 Aşamalı Osmanlıca OCR Pipeline
─────────────────────────────────
Aşama 1 → PaddleOCR  : görsel → Arap harfli metin
Aşama 2 → Kural motoru: Arap harfli metin → Latin transkripsiyon

app.py'deki analyze_image() ile aynı imzayı kullanır.
"""

from core.arabic_ocr import gorsel_b64_to_arapca
from core.ottoman_transliteration import satirlar_transkribe
from core.vowel_restore import metin_tamamla


def analyze_image_pipeline(
    image_b64: str,
    page_num: int = 1,
    total_pages: int = 1,
    arapca_da_goster: bool = False,
    sesli_tamamla: bool = True,
) -> str:
    """
    Tam pipeline: Base64 görsel → Latin transkripsiyon.

    Aşama 1 → EasyOCR      : görsel → Arap harfli satırlar
    Aşama 2 → Transliterasyon: Arap harfleri → Latin konsonant iskeleti
    Aşama 3 → Sesli tamamlama: iskelet → okunabilir kelimeler (opsiyonel)
    """
    # ── Aşama 1: OCR ──────────────────────────
    satirlar = gorsel_b64_to_arapca(image_b64)
    if not satirlar:
        return "(Metin tespit edilemedi)"

    # ── Aşama 2: Transliterasyon ──────────────
    latin_iskelet = satirlar_transkribe(satirlar)

    # ── Aşama 3: Sesli harf tamamlama ─────────
    latin_tam = metin_tamamla(latin_iskelet) if sesli_tamamla else latin_iskelet

    if arapca_da_goster:
        arapca_metin = "\n".join(satirlar)
        return (
            f"【Arap Harfleri】\n{arapca_metin}\n\n"
            f"【Konsonant İskeleti】\n{latin_iskelet}\n\n"
            f"【Latin Transkripsiyon】\n{latin_tam}"
        )

    return latin_tam if latin_tam.strip() else "(Transkripsiyon üretilemedi)"


def pipeline_hazir_mi() -> bool:
    """EasyOCR kurulu mu kontrol et."""
    try:
        import easyocr  # noqa: F401
        return True
    except ImportError:
        return False
