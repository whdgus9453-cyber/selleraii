import os
import io
import json
import zipfile
import base64
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
import streamlit as st
from ui_styles import MARKETER_FONTS

# =====================================================================
# [2. 데이터 저장소 및 미디어(사진/움짤/MP4영상) AI 자동 후가공 변환기]
# =====================================================================
DEFAULT_HUB_DIR = Path(__file__).resolve().parent / "seller_hub_data"


def pil_to_base64_url(pil_img, max_w=860, fmt="JPEG"):
    if pil_img is None:
        return ""
    w, h = pil_img.size
    if w > max_w:
        ratio = max_w / float(w)
        pil_img = pil_img.resize((max_w, int(h * ratio)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    if fmt.upper() == "PNG":
        pil_img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    pil_img.convert("RGB").save(buf, format="JPEG", quality=93)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def polish_uploaded_image(pil_img, max_w=820):
    """
    [사진/움짤 자동 후가공 엔진]
    사용자가 올린 사진을 원본 그대로 투박하게 넣지 않고,
    1) 불필요한 단색 여백 자동 정리
    2) 조도(밝기)·대비·광학 선명도 자동 보정
    3) 프로 디자이너 스타일 스튜디오 톤 & 깔끔한 마운팅 후가공을 수행합니다.
    """
    if pil_img is None:
        return None
    rgb = pil_img.convert("RGB")
    arr = np.array(rgb, dtype=np.float32)
    h, w, _ = arr.shape
    # 가장자리 배경 색상 대비 여백 자동 트리밍 (너무 과도하게 잘리지 않도록 최대 8% 이내만 정리)
    if h > 120 and w > 120:
        border_pixels = np.concatenate([
            arr[0, :, :], arr[-1, :, :], arr[:, 0, :], arr[:, -1, :]
        ], axis=0)
        bg_med = np.median(border_pixels, axis=0)
        diff = np.linalg.norm(arr - bg_med, axis=2)
        ys, xs = np.where(diff > 18.0)
        if len(xs) > 100:
            x1 = max(0, min(int(w * 0.08), int(xs.min()) - 14))
            y1 = max(0, min(int(h * 0.08), int(ys.min()) - 14))
            x2 = min(w, max(int(w * 0.92), int(xs.max()) + 14))
            y2 = min(h, max(int(h * 0.92), int(ys.max()) + 14))
            if (x2 - x1) > w * 0.6 and (y2 - y1) > h * 0.6:
                rgb = rgb.crop((x1, y1, x2, y2))

    # 조도·대비·채도·광학 선명도 프로페셔널 보정
    rgb = ImageEnhance.Brightness(rgb).enhance(1.03)
    rgb = ImageEnhance.Contrast(rgb).enhance(1.10)
    rgb = ImageEnhance.Color(rgb).enhance(1.04)
    rgb = rgb.filter(ImageFilter.UnsharpMask(radius=1.4, percent=125, threshold=3))

    if rgb.width > max_w:
        ratio = max_w / float(rgb.width)
        rgb = rgb.resize((max_w, int(rgb.height * ratio)), Image.Resampling.LANCZOS)
    return rgb


def file_to_media_data_url(uploaded_file, auto_polish=True):
    """
    사용자가 올린 사진, 움짤(GIF), 동영상(MP4/WEBM)을
    자동 후가공(여백 크롭, 조도/대비/선명도 보정)을 거쳐 데이터 URL로 변환합니다.
    """
    if uploaded_file is None:
        return None, None
    raw_bytes = uploaded_file.getvalue()
    fname = uploaded_file.name.lower()
    if fname.endswith(".mp4") or fname.endswith(".webm") or fname.endswith(".mov"):
        b64 = base64.b64encode(raw_bytes).decode("utf-8")
        return "video", f"data:video/mp4;base64,{b64}"
    elif fname.endswith(".gif"):
        b64 = base64.b64encode(raw_bytes).decode("utf-8")
        return "gif", f"data:image/gif;base64,{b64}"
    else:
        pil_img = Image.open(io.BytesIO(raw_bytes))
        if auto_polish:
            pil_img = polish_uploaded_image(pil_img, max_w=820)
        return "image", pil_to_base64_url(pil_img, max_w=820)


def base64_url_to_pil(data_url):
    try:
        if not data_url or "," not in data_url:
            return None
        b64 = data_url.split(",", 1)[1]
        return Image.open(io.BytesIO(base64.b64decode(b64)))
    except Exception:
        return None


def init_storage():
    if "hub_path" not in st.session_state:
        st.session_state.hub_path = str(DEFAULT_HUB_DIR)
    hub = Path(st.session_state.hub_path)
    (hub / "projects").mkdir(parents=True, exist_ok=True)
    (hub / "exports").mkdir(parents=True, exist_ok=True)

    config_file = hub / "config.json"
    default_cfg = {
        "gemini_key": "",
        "naver_id": "",
        "naver_secret": "",
        "clipdrop_key": "",
        "fal_key": "",
        "bria_key": "",
        "drap_art_key": "",
        "flair_ai_key": "",
        "hookle_key": "",
        "hub_path": str(hub)
    }
    if not config_file.exists():
        config_file.write_text(json.dumps(default_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return default_cfg
    try:
        loaded = json.loads(config_file.read_text(encoding="utf-8"))
        for k, v in default_cfg.items():
            if k not in loaded:
                loaded[k] = v
        loaded["hub_path"] = str(hub)
        return loaded
    except Exception:
        return default_cfg


def save_config(cfg):
    hub = Path(cfg.get("hub_path", st.session_state.hub_path))
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def get_default_9steps(msize="총 길이 약 105mm (10.5cm) / 최대 두께 약 9.5mm (100원 동전 24mm 비교 실측)"):
    """
    소비자 궁금증 흐름 9단계 공식 기본 데이터
    - 상위권 실제 판매 워딩과 호흡을 학습한 자연스러운 한국어 카피
    - 표시광고법 준수 (허위·과장 표현 배제) 및 불필요한 STEP 번호 표시 제거
    """
    return [
        {
            "step": 1,
            "role": "첫인상 · 메인 헤드카피 (공감 & 핵심 가치)",
            "subtitle": "헐거워진 안경다리, 멈춰버린 시계 건전지",
            "main_title": "집에서 3초 만에 조이는 초정밀 자석 드라이버",
            "body": "안경점이나 시계방까지 번거롭게 찾아갈 필요 없습니다.<>서랍 속에 하나만 준비해 두면 풀린 미세 나사를 언제든 손쉽게 조일 수 있습니다."
        },
        {
            "step": 2,
            "role": "차별화 · 핵심 비교 포인트 (왜 이 제품인가)",
            "subtitle": "일반 저가형 미니 드라이버와 직접 비교해보세요",
            "main_title": "자석 흡착 헤드 × 360도 부드러운 회전캡",
            "body": "눈으로 집기도 힘든 1~2mm 미세 나사가 드라이버 끝에 착 붙어 분실 걱정을 줄여줍니다.<>윗면 회전캡을 검지로 지그시 누른 채 손가락만으로 부드럽게 돌려 작업하세요."
        },
        {
            "step": 3,
            "role": "상품 특징 · 3대 핵심 설계",
            "subtitle": "작지만 디테일하게 설계된 3가지 핵심 포인트",
            "main_title": "자석 내장 비트 · 상단 회전캡 · 미끄럼 방지 그립",
            "body": "미세 나사를 안정적으로 잡아주는 자화 처리 헤드와<>손목의 피로를 덜어주는 상단 회전캡, 손땀에도 미끄러지지 않는 그립부를 적용했습니다."
        },
        {
            "step": 4,
            "role": "제조 · 소재 · 내구성 검증",
            "subtitle": "한두 번 돌리면 마모되는 무른 철재가 아닙니다",
            "main_title": "단단한 합금강 비트 & 정밀 가공 바디",
            "body": "열처리된 고강도 합금강 헤드를 적용해 나사산과 드라이버 팁의 마모를 줄였으며<>가볍고 견고한 바디 밸런스로 오랫동안 변형 없이 사용할 수 있습니다."
        },
        {
            "step": 5,
            "role": "실물 규격 · 100원 동전 비교 실측 · 상세 스펙",
            "subtitle": "100원 동전(24mm) 비교 AI 자동 실측 완료",
            "main_title": "총 길이 약 105mm · 한 손에 안정감 있게 잡히는 규격",
            "body": f"{msize}<>펜꽂이나 공구 파우치에 쏙 들어가며 성인 손으로 정밀 작업을 하기에 알맞은 크기입니다."
        },
        {
            "step": 6,
            "role": "상황별 활용 · 호환 가이드",
            "subtitle": "가정과 사무실 어디서나 폭넓게 쓰이는 실용성",
            "main_title": "안경 · 손목시계 · 노트북 하판 · 아이 장난감까지",
            "body": "헐거워진 안경·선글라스 나사 조임부터 손목시계 배터리 커버 개봉,<>노트북·보조배터리·소형 전자기기와 아이 장난감 건전지 덮개 나사까지 폭넓게 호환됩니다."
        },
        {
            "step": 7,
            "role": "출고 · 배송 · 포장 안내",
            "subtitle": "기다림 없이 빠르게 받아보실 수 있도록",
            "main_title": "평일 오후 2시 이전 주문 시 당일 출고",
            "body": "전 상품 국내 검수 후 안전 완충 포장으로 발송되며 출고 후 영업일 기준 평균 1~2일 내 수령 가능합니다.<>여러 개 묶음 주문 시 배송비 한 번으로 합포장 출고됩니다."
        },
        {
            "step": 8,
            "role": "올바른 사용법 · 보관 및 관리 팁",
            "subtitle": "나사산 손상 없이 안전하게 작업하는 요령",
            "main_title": "드라이버를 수직으로 세워 지그시 눌러 돌려주세요",
            "body": "미세 나사 특성상 비스듬히 힘을 주면 나사 머리가 마모될 수 있습니다.<>윗면 회전캡을 검지로 수직으로 누른 상태에서 손가락으로 천천히 회전시켜 주세요."
        },
        {
            "step": 9,
            "role": "자주 묻는 질문(FAQ) & 전자상거래법 기준 교환·환불 보장",
            "subtitle": "구매 전 많이 물어보시는 질문과 안심 고객 케어",
            "main_title": "제품 불량 및 오배송 시 100% 무상 교환·환불 보장",
            "body": "전자상거래 등에서의 소비자보호에 관한 법률에 따라 수령 후 7일 이내 교환·반품이 가능합니다.<>초기 불량이나 파손 확인 시 판매자 부담으로 신속하게 교환 및 환불 처리를 도와드립니다."
        }
    ]


def get_default_project_data():
    font_keys = list(MARKETER_FONTS.keys())
    return {
        "title": "새 제품 기획",
        "status": "💬 기획중",
        "keyword": "",
        "cost_price": "",
        "brief_desc": "",
        "manual_size": "",
        "target_platform": "1. 가로 860px (대표썸네일 1000×1000px) — 적합 플랫폼: 네이버 스마트스토어 · G마켓 · 옥션 · 11번가",
        "ref_urls": [],
        "ref_items": [],
        "price_stats": {},
        "chat_history": [],
        "page_feedback_history": [],
        "orig_img_b64": "",
        "edited_img_b64": "",
        "fg_cutout_b64": "",
        "multi_images": [],
        "photo_ai_report": {
            "engine_used": "아직 보정 전입니다.",
            "process_steps": [],
            "api_diagnosis": ""
        },
        "spec_qa": {},
        "product_specs": [
            {"label": "품명 및 모델명", "value": "초정밀 자석 시계·안경 드라이버", "항목": "품명 및 모델명", "내용": "초정밀 자석 시계·안경 드라이버"},
            {"label": "실측 사이즈 / 중량", "value": "총 길이 약 105mm (10.5cm) / 최대 두께 약 9.5mm (초경량)", "항목": "실측 사이즈 / 중량", "내용": "총 길이 약 105mm (10.5cm) / 최대 두께 약 9.5mm (초경량)"},
            {"label": "재질 (헤드 / 바디)", "value": "고경도 크롬바나듐 합금강(자석 내장) / 논슬립 메탈 그립", "항목": "재질 (헤드 / 바디)", "내용": "고경도 크롬바나듐 합금강(자석 내장) / 논슬립 메탈 그립"},
            {"label": "핵심 기능", "value": "미세 나사 자석 흡착 + 윗면 360도 무저항 회전캡", "항목": "핵심 기능", "내용": "미세 나사 자석 흡착 + 윗면 360도 무저항 회전캡"},
            {"label": "주요 사용처", "value": "손목시계 배터리·줄 수리, 안경·선글라스 나사 조임, 소형 전자기기/장난감 분해", "항목": "주요 사용처", "내용": "손목시계 배터리·줄 수리, 안경·선글라스 나사 조임, 소형 전자기기/장난감 분해"}
        ],
        "shipping_info": {
            "courier": "CJ대한통운 / 한진택배 (안심 안전포장 발송)",
            "cutoff": "평일 오후 2시(14:00) 이전 결제 완료 시 당일 출고 (주말·공휴일 제외)",
            "cutoff_time": "평일 오후 2시(14:00) 이전 결제 완료 시 당일 출고 (주말·공휴일 제외)",
            "eta": "출고 후 영업일 기준 평균 1~2일 이내 수령 (도서·산간 지역 2~3일 소요)",
            "delivery_days": "출고 후 영업일 기준 평균 1~2일 이내 수령 (도서·산간 지역 2~3일 소요)",
            "fee": "기본 배송비 3,000원 (제주·도서산간 추가 배송비 별도 / 묶음 구매 시 배송비 절약)",
            "shipping_fee": "기본 배송비 3,000원 (제주·도서산간 추가 배송비 별도 / 묶음 구매 시 배송비 절약)",
            "exchange": "전자상거래법 준수: 수령 후 7일 이내 교환/반품 가능 (단순 변심 시 왕복 배송비 구매자 부담 / 제품 불량·오배송 시 100% 판매자 부담)",
            "exchange_info": "전자상거래법 준수: 수령 후 7일 이내 교환/반품 가능 (단순 변심 시 왕복 배송비 구매자 부담 / 제품 불량·오배송 시 100% 판매자 부담)",
            "caution_note": "정밀 공구 특성상 나사 규격에 맞지 않는 무리한 힘 가압 시 나사산이 마모될 수 있으니 수직으로 눌러 돌려주세요."
        },
        "typo_settings": {
            "title_size": 34,
            "body_size": 16,
            "title_weight": "900",
            "body_weight": "500",
            "title_italic": False,
            "body_italic": False,
            "title_color": "#0F172A",
            "body_color": "#0F172A",
            "page_bg": "#FFFFFF"
        },
        "theme_color": "1. 스타벅스 딥그린 & 민트 크림 (#00704A)",
        "slot1_media": {"type": "", "data": "", "caption": "나사가 자석에 착! 붙는 실제 작동 장면"},
        "slot2_media": {"type": "", "data": "", "caption": "핵심 기능 1 (나사 자석 흡착 / 헤드 디테일 근접컷)"},
        "slot3_media": {"type": "", "data": "", "caption": "핵심 기능 2 (한 손 360도 회전캡 그립 / 실사용컷)"},
        "title_font": font_keys[1],  # 기본 제목: 지마켓 산스
        "body_font": font_keys[0],   # 기본 본문: 프리텐다드
        "nine_steps": get_default_9steps(),
        "six_agents_research": {},
        "page_blocks": {
            "hook_badge": "초정밀 자석 드라이버",
            "hook_title": "헛도는 작은 나사, 집에서 3초면 해결!",
            "hook_sub": "#자석흡착헤드  #360도회전캡  #미끄럼방지그립",
            "keywords": ["자석 흡착 헤드", "한 손 회전캡", "합금강 정밀 비트", "100원 동전 비교 실측"],
            "point1_title": "미세 나사 자석 고정",
            "point1_desc": "작은 나사도 끝에 착 붙어 분실 걱정 감소",
            "point2_title": "윗면 360도 회전캡",
            "point2_desc": "손목 돌릴 필요 없이 손가락만으로 부드러운 회전",
            "point3_title": "실측 사이즈 & 그립감",
            "point3_desc": "100원 동전(24mm) 대비 한눈에 보이는 정밀 규격",
            "price_origin": "6,900원",
            "price_sale": "3,900원",
            "price_reason": "직수입 원가 절감 반영 · 1+1 실속 세트 구성 시 추가 혜택",
            "photo_requests": [
                "🎬 [슬롯 1 - 상단 첫인상 3초 훅 배치용] 드라이버 끝에 나사가 자석으로 착! 붙거나 윗부분 회전캡을 부드럽게 돌리는 3초 짧은 영상(MP4/GIF) 또는 근접 사진",
                "📸 [슬롯 2 - 핵심 기능 섹션 삽입용] 드라이버 헤드 끝에 작은 나사가 매달려 있는 클로즈업 사진 (자석 성능 증명용)",
                "📸 [슬롯 3 - 실사용 시나리오 섹션 삽입용] 성인 손으로 쥐었을 때 크기가 체감되는 그립 컷 또는 안경/시계에 직접 대고 있는 실사용 사진"
            ]
        },
        "draft_html": ""
    }


def list_projects():
    proj_dir = Path(st.session_state.hub_path) / "projects"
    proj_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(proj_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
    res = []
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            def_d = get_default_project_data()
            for k, v in def_d.items():
                if k not in d:
                    d[k] = v
            res.append((f.stem, d))
        except Exception:
            pass
    return res


def save_project(proj_id, data):
    proj_dir = Path(st.session_state.hub_path) / "projects"
    proj_dir.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (proj_dir / f"{proj_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def duplicate_project(proj_id):
    """기존 프로젝트를 100% 복제하여 새 프로젝트 ID로 저장합니다."""
    proj_dir = Path(st.session_state.hub_path) / "projects"
    src_file = proj_dir / f"{proj_id}.json"
    if not src_file.exists():
        return None, None
    data = json.loads(src_file.read_text(encoding="utf-8"))
    new_id = f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}_copy"
    data["title"] = f"{data.get('title', '프로젝트')} (복제본)"
    save_project(new_id, data)
    return new_id, data


def delete_project(proj_id):
    f = Path(st.session_state.hub_path) / "projects" / f"{proj_id}.json"
    if f.exists():
        f.unlink()


def create_hub_backup_zip():
    """PC 이사용 전체 데이터(config.json + 모든 프로젝트 JSON)를 ZIP 바이트로 압축해 반환합니다."""
    hub = Path(st.session_state.hub_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in hub.rglob("*"):
            if file_path.is_file():
                arcname = f"seller_hub_data/{file_path.relative_to(hub).as_posix()}"
                zf.write(file_path, arcname=arcname)
    buf.seek(0)
    return buf.getvalue()
