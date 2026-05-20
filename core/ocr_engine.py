"""Claude Vision API ile Osmanlıca OCR."""

import anthropic
from config import ANTHROPIC_API_KEY, MODEL_NAME, MAX_TOKENS, SYSTEM_PROMPT


def _get_client() -> anthropic.Anthropic:
    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY bulunamadı. Lütfen .env dosyanızı kontrol edin.")
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


def analyze_image(image_b64: str, page_num: int = 1, total_pages: int = 1) -> str:
    """
    Base64 görüntüyü Claude Vision ile analiz et.
    Çok sayfalı belgelerde sayfa numarası bağlamı prompta eklenir.
    """
    client = _get_client()

    page_context = ""
    if total_pages > 1:
        page_context = f"\n\nNOT: Bu belge {total_pages} sayfalıdır. Şu an {page_num}. sayfa analiz edilmektedir."

    user_message = (
        "Lütfen bu görüntüdeki Osmanlıca metni analiz et ve belirtilen formatta çıktı ver."
        + page_context
    )

    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_message},
                ],
            }
        ],
    )

    return response.content[0].text


def analyze_pages(images_b64: list[str]) -> list[dict]:
    """
    Birden fazla sayfa için sırayla analiz yap.
    Her sayfa için {'page': int, 'result': str} döndürür.
    """
    total = len(images_b64)
    results = []
    for i, b64 in enumerate(images_b64, start=1):
        text = analyze_image(b64, page_num=i, total_pages=total)
        results.append({"page": i, "result": text})
    return results
