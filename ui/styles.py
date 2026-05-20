"""Kurumsal Osmanlı arşivi temalı CSS."""

CUSTOM_CSS = """
<style>
/* ── Genel zemin ── */
[data-testid="stAppViewContainer"] {
    background: #0f0e0b;
}
[data-testid="stSidebar"] {
    background: #1a1814;
    border-right: 1px solid #3d3526;
}

/* ── Başlık ── */
.app-header {
    text-align: center;
    padding: 2rem 0 1rem;
    border-bottom: 1px solid #3d3526;
    margin-bottom: 2rem;
}
.app-title {
    font-family: 'Georgia', serif;
    font-size: 2.2rem;
    font-weight: 700;
    color: #c9a84c;
    letter-spacing: 0.05em;
    margin: 0;
}
.app-subtitle {
    color: #8a7a5a;
    font-size: 0.95rem;
    margin-top: 0.4rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

/* ── Kart ── */
.card {
    background: #1a1814;
    border: 1px solid #3d3526;
    border-radius: 8px;
    padding: 1.5rem;
    margin-bottom: 1.2rem;
}
.card-title {
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: #c9a84c;
    margin-bottom: 0.8rem;
    border-bottom: 1px solid #3d3526;
    padding-bottom: 0.5rem;
}

/* ── Sonuç metin alanı ── */
.result-box {
    background: #12110e;
    border: 1px solid #3d3526;
    border-radius: 6px;
    padding: 1.2rem 1.5rem;
    font-family: 'Courier New', monospace;
    font-size: 0.88rem;
    line-height: 1.8;
    color: #d4c5a0;
    white-space: pre-wrap;
    max-height: 520px;
    overflow-y: auto;
    direction: ltr;
}

/* ── Durum rozeti ── */
.badge {
    display: inline-block;
    padding: 0.2rem 0.7rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.06em;
}
.badge-success { background: #1a3320; color: #4caf7d; border: 1px solid #2a5030; }
.badge-warning { background: #332a10; color: #c9a84c; border: 1px solid #4d3d18; }
.badge-info    { background: #102030; color: #4a9fc8; border: 1px solid #1a3040; }

/* ── Dosya yükleme alanı ── */
[data-testid="stFileUploader"] {
    border: 2px dashed #3d3526 !important;
    border-radius: 8px !important;
    background: #12110e !important;
}

/* ── Butonlar ── */
.stButton > button {
    background: linear-gradient(135deg, #c9a84c, #a07830) !important;
    color: #0f0e0b !important;
    border: none !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    border-radius: 6px !important;
    padding: 0.6rem 2rem !important;
    transition: opacity 0.2s !important;
}
.stButton > button:hover { opacity: 0.88 !important; }

/* ── İndirme butonu ── */
[data-testid="stDownloadButton"] > button {
    background: #1a1814 !important;
    color: #c9a84c !important;
    border: 1px solid #c9a84c !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}

/* ── Slider & checkbox ── */
[data-testid="stCheckbox"] label { color: #d4c5a0 !important; }
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background-color: #c9a84c !important;
}

/* ── Ayırıcı ── */
hr { border-color: #3d3526 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #1a1814; }
::-webkit-scrollbar-thumb { background: #3d3526; border-radius: 3px; }
</style>
"""
