"""Görüntü ön işleme — grayscale, CLAHE, denoise, sharpen."""

import io
import base64
from pathlib import Path
from typing import List

import cv2
import numpy as np
from PIL import Image, ImageEnhance

try:
    from pdf2image import convert_from_bytes
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False


def load_image(file_bytes: bytes, filename: str) -> List[Image.Image]:
    """Dosyayı yükle; PDF ise her sayfayı ayrı PIL Image olarak döndür."""
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        if not PDF_SUPPORT:
            raise RuntimeError(
                "PDF desteği için 'pdf2image' ve 'poppler' kurulmalı.\n"
                "macOS: brew install poppler\n"
                "Ubuntu: sudo apt install poppler-utils"
            )
        pages = convert_from_bytes(file_bytes, dpi=300)
        return pages
    else:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        return [img]


def preprocess(
    pil_image: Image.Image,
    grayscale: bool = True,
    denoise: bool = True,
    clahe: bool = True,
    sharpen: bool = False,
    deskew: bool = False,
) -> Image.Image:
    """Görüntüyü OCR için optimize et."""
    img = np.array(pil_image)

    # BGR → Gray
    if grayscale:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    # Gürültü azaltma
    if denoise:
        if grayscale:
            img = cv2.fastNlMeansDenoising(img, h=10)
        else:
            img = cv2.fastNlMeansDenoisingColored(img, h=10)

    # Adaptif kontrast iyileştirme (CLAHE)
    if clahe and grayscale:
        clahe_obj = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        img = clahe_obj.apply(img)

    # Keskinleştirme
    if sharpen:
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
        img = cv2.filter2D(img, -1, kernel)

    # Perspektif/eğiklik düzeltme (basit)
    if deskew and grayscale:
        img = _deskew(img)

    # PIL'e geri dön
    if grayscale:
        result = Image.fromarray(img, mode="L").convert("RGB")
    else:
        result = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

    return result


def _deskew(gray: np.ndarray) -> np.ndarray:
    """Metin eğikliğini tespit edip düzelt."""
    coords = np.column_stack(np.where(gray < 200))
    if len(coords) < 10:
        return gray
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5:
        return gray
    h, w = gray.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def image_to_base64(pil_image: Image.Image, quality: int = 95) -> str:
    """PIL Image → base64 string (JPEG)."""
    buffer = io.BytesIO()
    pil_image.save(buffer, format="JPEG", quality=quality)
    return base64.standard_b64encode(buffer.getvalue()).decode("utf-8")
