"""Yeniden kullanılabilir Streamlit UI bileşenleri."""

import streamlit as st


def render_header():
    st.markdown(
        """
        <div class="app-header">
            <p class="app-title">&#x2756; Osmanlıca Metin Okuyucu &#x2756;</p>
            <p class="app-subtitle">Ottoman Script Recognition &amp; Transcription System</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_preprocess_settings() -> dict:
    """Sidebar'da ön işleme ayarlarını göster, seçimleri döndür."""
    st.sidebar.markdown(
        '<p style="color:#c9a84c;font-size:0.8rem;text-transform:uppercase;'
        'letter-spacing:0.1em;margin-bottom:0.5rem;">Görüntü Ön İşleme</p>',
        unsafe_allow_html=True,
    )
    grayscale = st.sidebar.checkbox("Gri Tonlama", value=True)
    denoise = st.sidebar.checkbox("Gürültü Azaltma", value=True)
    clahe = st.sidebar.checkbox("CLAHE Kontrast", value=True)
    sharpen = st.sidebar.checkbox("Keskinleştirme", value=False)
    deskew = st.sidebar.checkbox("Eğiklik Düzeltme", value=False)

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        '<p style="color:#c9a84c;font-size:0.8rem;text-transform:uppercase;'
        'letter-spacing:0.1em;margin-bottom:0.5rem;">Hakkında</p>',
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        '<p style="color:#8a7a5a;font-size:0.78rem;line-height:1.6;">'
        "Claude Vision API kullanılarak Osmanlıca (Arap alfabeli) matbu ve "
        "el yazısı metinleri analiz eder, modern Türkçeye aktarır.</p>",
        unsafe_allow_html=True,
    )

    return {
        "grayscale": grayscale,
        "denoise": denoise,
        "clahe": clahe,
        "sharpen": sharpen,
        "deskew": deskew,
    }


def render_image_preview(original, processed, page_num: int = 1):
    """Orijinal ve işlenmiş görüntüyü yan yana göster."""
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            f'<div class="card-title">Orijinal — Sayfa {page_num}</div>',
            unsafe_allow_html=True,
        )
        st.image(original, use_container_width=True)
    with col2:
        st.markdown(
            f'<div class="card-title">İşlenmiş — Sayfa {page_num}</div>',
            unsafe_allow_html=True,
        )
        st.image(processed, use_container_width=True)


def render_result(result_text: str, page_num: int = 1, total_pages: int = 1):
    """Analiz sonucunu styled bir kutuda göster."""
    header = f"Analiz Sonucu" if total_pages == 1 else f"Sayfa {page_num} / {total_pages}"
    st.markdown(f'<div class="card-title">{header}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="result-box">{result_text}</div>',
        unsafe_allow_html=True,
    )


def render_stats(page_results: list[dict]):
    """Özet istatistik kartları."""
    total_lines = sum(
        r["result"].count("Satır") for r in page_results
    )
    uncertain = sum(r["result"].count("[?]") for r in page_results)
    unreadable = sum(r["result"].count("[...]") for r in page_results)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Sayfa", len(page_results))
    with c2:
        st.metric("Satır (tahmini)", total_lines)
    with c3:
        st.metric("Belirsiz [?]", uncertain)
    with c4:
        st.metric("Okunamayan [...]", unreadable)
