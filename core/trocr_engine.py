"""Fine-tune edilmiş TrOCR modeli ile Osmanlıca OCR — otomatik satır bölme dahil."""

import base64
import io
from pathlib import Path
from functools import lru_cache

import numpy as np
import torch
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

MODEL_DIR = Path(r"C:\Users\user\ottoman-ocr\model_output\best_model")
IMG_SIZE  = (384, 384)   # modelin beklediği boyut (tek satır için)


@lru_cache(maxsize=1)
def _load_model():
    device    = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    processor = TrOCRProcessor.from_pretrained(str(MODEL_DIR))
    model     = VisionEncoderDecoderModel.from_pretrained(str(MODEL_DIR)).to(device)
    model.eval()
    return processor, model, device


def _satir_bол(image: Image.Image, min_satir_yuksekligi: int = 20) -> list[Image.Image]:
    """
    Görüntüyü yatay projeksiyon profili ile satırlara böler.
    Osmanlıca sağdan sola yazı için de çalışır (yalnızca yatay bölünme).
    """
    gray  = np.array(image.convert("L"))
    # Beyaz zemin varsay: koyu piksel = yazı
    binary = (gray < 200).astype(np.uint8)

    # Her satır için yatay toplam (yazı yoğunluğu)
    row_sum = binary.sum(axis=1)

    # Yazı olan / olmayan satırları bul
    threshold   = max(1, row_sum.max() * 0.05)
    in_text     = row_sum > threshold
    satırlar    = []
    baslangic   = None

    for i, val in enumerate(in_text):
        if val and baslangic is None:
            baslangic = i
        elif not val and baslangic is not None:
            yukseklik = i - baslangic
            if yukseklik >= min_satir_yuksekligi:
                # Küçük bir padding ekle
                y1 = max(0, baslangic - 4)
                y2 = min(gray.shape[0], i + 4)
                satırlar.append(image.crop((0, y1, image.width, y2)))
            baslangic = None

    # Son satır dosya sonuna kadar uzanıyorsa
    if baslangic is not None:
        yukseklik = len(in_text) - baslangic
        if yukseklik >= min_satir_yuksekligi:
            y1 = max(0, baslangic - 4)
            satırlar.append(image.crop((0, y1, image.width, image.height)))

    return satırlar if satırlar else [image]


def _satir_oku(satir: Image.Image, processor, model, device) -> str:
    """Tek bir satır görselini modele ver."""
    satir_rgb    = satir.convert("RGB").resize(IMG_SIZE, Image.LANCZOS)
    pixel_values = processor(images=satir_rgb, return_tensors="pt").pixel_values.to(device)

    with torch.no_grad():
        ids = model.generate(
            pixel_values,
            max_new_tokens=128,
            num_beams=4,
            early_stopping=True,
        )
    return processor.batch_decode(ids, skip_special_tokens=True)[0]


def analyze_image_trocr(image_b64: str, page_num: int = 1, total_pages: int = 1) -> str:
    """
    Base64 görüntüyü satırlara bölerek TrOCR ile okur.
    Çok satırlı belgeler için otomatik line segmentation yapar.
    """
    processor, model, device = _load_model()

    img_bytes = base64.b64decode(image_b64)
    image     = Image.open(io.BytesIO(img_bytes)).convert("RGB")

    satırlar  = _satir_bол(image)
    sonuclar  = []

    for i, satir in enumerate(satırlar, 1):
        metin = _satir_oku(satir, processor, model, device).strip()
        if metin:
            sonuclar.append(metin)

    if not sonuclar:
        return "(Metin okunamadı)"

    return "\n".join(sonuclar)


def model_yuklu_mu() -> bool:
    return MODEL_DIR.exists()
