import streamlit as st

APP_VERSION = "v6.0 (다각도 교차누끼 & TOP10 심층회의 & 포토샵/일러스트 레이어 패키지 & 모바일 완벽 최적화)"

# =====================================================================
# [1. 온라인 마케터 필수 상업용 무료 웹폰트 10종 탑재 (제목/본문 자유 선택)]
# =====================================================================
MARKETER_FONTS = {
    "1. 프리텐다드 (Pretendard - 토스/애플 스타일 깔끔한 표준 고딕)": {
        "css": "@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');",
        "family": "'Pretendard', sans-serif"
    },
    "2. 지마켓 산스 (Gmarket Sans - 쿠팡/특가 헤드라인 대표 굵은 고딕)": {
        "css": "@font-face { font-family: 'GmarketSansBold'; src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansBold.woff') format('woff'); }",
        "family": "'GmarketSansBold', sans-serif"
    },
    "3. 에스코어 드림 (S-Core Dream - 공구/기계/스펙표 신뢰감 1위 각진 고딕)": {
        "css": "@font-face { font-family: 'S-CoreDream-6Bold'; src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/noonfonts_six@1.2/S-CoreDream-6Bold.woff') format('woff'); }",
        "family": "'S-CoreDream-6Bold', sans-serif"
    },
    "4. 페이퍼로지 (Paperlogy - 요즘 디자이너들이 제일 많이 쓰는 세련된 타이틀체)": {
        "css": "@font-face { font-family: 'Paperlogy-8ExtraBold'; src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/2408-3@1.0/Paperlogy-8ExtraBold.woff2') format('woff2'); }",
        "family": "'Paperlogy-8ExtraBold', sans-serif"
    },
    "5. 나눔스퀘어 네오 (NanumSquare Neo - 네이버 스마트스토어 최적 깔끔체)": {
        "css": "@import url('https://hangeul.pstatic.net/hangeul_static/css/nanum-square-neo.css');",
        "family": "'NanumSquareNeo', sans-serif"
    },
    "6. 카페24 써라운드 (Cafe24 Ssurround - 시선이 확 꽂히는 둥근 강조체)": {
        "css": "@font-face { font-family: 'Cafe24Ssurround'; src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/noonfonts_2105_2@1.0/Cafe24Ssurround.woff') format('woff'); }",
        "family": "'Cafe24Ssurround', sans-serif"
    },
    "7. 쿠키런 볼드 (CookieRun - 친근하고 가독성 높은 포인트 폰트)": {
        "css": "@font-face { font-family: 'CookieRun-Regular'; src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/CookieRun-Regular.woff') format('woff'); }",
        "family": "'CookieRun-Regular', sans-serif"
    },
    "8. 코트라 볼드 (KOTRA Bold - 묵직하고 강렬한 하드웨어/공구 타겟 폰트)": {
        "css": "@font-face { font-family: 'KOTRA_BOLD-Bold'; src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/noonfonts_20-10-21@1.1/KOTRA_BOLD-Bold.woff') format('woff'); }",
        "family": "'KOTRA_BOLD-Bold', sans-serif"
    },
    "9. 마루 부리 (MaruBuri - 백화점/프리미엄 감성 고급 명조체)": {
        "css": "@font-face { font-family: 'MaruBuri'; src: url('https://hangeul.pstatic.net/hangeul_static/webfont/MaruBuri/MaruBuri-Regular.woff2') format('woff2'); }",
        "family": "'MaruBuri', serif"
    },
    "10. 조선일보 명조 (ChosunIlbo_myungjo - 신뢰감 있는 매거진/리포트 스타일)": {
        "css": "@font-face { font-family: 'Chosunilbo_myungjo'; src: url('https://fastly.jsdelivr.net/gh/projectnoonnu/noonfonts_one@1.0/Chosunilbo_myungjo.woff') format('woff'); }",
        "family": "'Chosunilbo_myungjo', serif"
    }
}

CUSTOM_CSS = """
<style>
    /* 다크모드에서도 절대 글씨가 하얗게 날아가지 않도록 배경색과 글자색을 1:1로 강제 고정 */
    .dark-safe-card {
        background-color: #1e293b !important;
        color: #f8fafc !important;
        border: 1px solid #334155 !important;
        border-radius: 12px;
        padding: 18px 20px;
        margin: 10px 0;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        word-break: keep-all;
        overflow-wrap: break-word;
    }
    .dark-safe-card h3, .dark-safe-card h4, .dark-safe-card b, .dark-safe-card strong {
        color: #38bdf8 !important;
    }
    .dark-safe-card p, .dark-safe-card li, .dark-safe-card div, .dark-safe-card span {
        color: #e2e8f0 !important;
        line-height: 1.65;
    }
    .price-highlight-red { color: #f87171 !important; font-weight: 800; font-size: 1.15em; }
    .price-highlight-blue { color: #60a5fa !important; font-weight: 800; font-size: 1.15em; }
    .price-highlight-green { color: #4ade80 !important; font-weight: 800; font-size: 1.15em; }
    
    .ai-log-box {
        background-color: #0f172a !important;
        color: #a7f3d0 !important;
        border-left: 4px solid #10b981 !important;
        border-radius: 8px;
        padding: 16px;
        margin-top: 12px;
        font-size: 0.9em;
        word-break: keep-all;
    }
    .ai-log-box b { color: #34d399 !important; }
    
    .director-req-box {
        background-color: #1e1b4b !important;
        color: #e0e7ff !important;
        border: 1px solid #4f46e5 !important;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        word-break: keep-all;
    }
    .director-req-box b { color: #a5b4fc !important; }

    .key-ok { background: #064e3b !important; color: #6ee7b7 !important; padding: 7px 10px; border-radius: 6px; font-size: 0.82em; margin-top: -8px; margin-bottom: 12px; border: 1px solid #059669; font-weight: 600; }
    .key-err { background: #7f1d1d !important; color: #fca5a5 !important; padding: 7px 10px; border-radius: 6px; font-size: 0.82em; margin-top: -8px; margin-bottom: 12px; border: 1px solid #dc2626; font-weight: 600; }
    .key-empty { background: #1e293b !important; color: #cbd5e1 !important; padding: 7px 10px; border-radius: 6px; font-size: 0.82em; margin-top: -8px; margin-bottom: 12px; border: 1px solid #475569; }

    /* 클릭 가능한 스마트스토어 TOP 10 테이블 스타일 */
    .top10-table-wrap {
        width: 100%;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        border-radius: 12px;
        border: 1px solid #334155;
        margin: 10px 0 18px 0;
    }
    .top10-table {
        width: 100%;
        border-collapse: collapse;
        background: #0f172a;
        color: #f8fafc;
        font-size: 0.9em;
        min-width: 680px;
    }
    .top10-table th {
        background: #1e293b;
        color: #38bdf8;
        padding: 11px 12px;
        text-align: left;
        border-bottom: 2px solid #334155;
        font-weight: 800;
        white-space: nowrap;
    }
    .top10-table td {
        padding: 10px 12px;
        border-bottom: 1px solid #1e293b;
        color: #e2e8f0;
        vertical-align: middle;
    }
    .top10-table tr:hover td {
        background: rgba(56, 189, 248, 0.08);
    }
    .top10-link-btn {
        display: inline-block;
        background: #2563eb;
        color: #ffffff !important;
        padding: 5px 11px;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.85em;
        text-decoration: none !important;
        white-space: nowrap;
    }
    .top10-link-btn:hover {
        background: #1d4ed8;
    }

    /* =====================================================================
       📱 모바일 / 스마트폰 접속 UI 완벽 최적화 (@media max-width: 768px)
       ===================================================================== */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1.8rem !important;
            padding-left: 0.7rem !important;
            padding-right: 0.7rem !important;
            padding-bottom: 2.5rem !important;
            max-width: 100% !important;
        }
        /* 모바일에서 가로 컬럼들을 100% 세로 스택으로 정렬 */
        div[data-testid="stHorizontalBlock"] {
            flex-direction: column !important;
            gap: 0.65rem !important;
        }
        div[data-testid="column"], div[data-testid="stColumn"] {
            width: 100% !important;
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }
        /* 모바일 터치 친화적 버튼 높이 및 글자 크기 */
        .stButton > button, .stDownloadButton > button {
            min-height: 46px !important;
            font-size: 0.95rem !important;
            font-weight: 800 !important;
            border-radius: 10px !important;
            padding: 0.5rem 0.9rem !important;
            width: 100% !important;
        }
        /* 탭 버튼 가로 스크롤 및 터치 영역 확대 */
        div[data-baseweb="tab-list"] {
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
            -webkit-overflow-scrolling: touch !important;
            gap: 4px !important;
            padding-bottom: 4px !important;
        }
        button[data-baseweb="tab"] {
            white-space: nowrap !important;
            padding: 10px 14px !important;
            font-size: 0.88rem !important;
            font-weight: 800 !important;
        }
        .dark-safe-card {
            padding: 14px !important;
            margin: 8px 0 !important;
            font-size: 0.92rem !important;
        }
        h1 { font-size: 1.4rem !important; }
        h2 { font-size: 1.22rem !important; line-height: 1.35 !important; }
        h3 { font-size: 1.08rem !important; }
    }
</style>
"""

def apply_ui_styles():
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

def render_live_badge(status, msg):
    cls = "key-ok" if status == "ok" else ("key-err" if status == "err" else "key-empty")
    st.markdown(f'<div class="{cls}">{msg}</div>', unsafe_allow_html=True)
