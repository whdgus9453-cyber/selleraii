import os
import io
import json
import copy
import zipfile
from datetime import datetime
from pathlib import Path
import streamlit as st
from ui_styles import MARKETER_FONTS

# =====================================================================
# [core_storage.py] 프로젝트 JSON/설정 영구 저장, 백업 관리, 기본 데이터 스키마
# =====================================================================
DEFAULT_HUB_DIR = Path(__file__).resolve().parent / "seller_hub_data"


def init_storage():
    """seller_hub_data 폴더 및 config.json 초기화 및 불러오기"""
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
        "photoroom_key": "",
        "removebg_key": "",
        "hub_path": str(hub),
        "key_status": {},
        "brand_preset": {
            "store_name": "",
            "slogan": "",
            "shipping_fee": "",
            "exchange_notice": "",
            "target_margin_pct": 35,
            "title_font": "",
            "body_font": "",
        },
        "image_defaults": {
            "detail_width": 860,
            "save_format": "PNG",
            "jpeg_quality": 92,
            "keep_png_alpha": True,
            "shadow_strength": 18,
        },
    }
    if not config_file.exists():
        config_file.write_text(json.dumps(default_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return default_cfg
    try:
        loaded = json.loads(config_file.read_text(encoding="utf-8"))
        changed = _merge_missing(loaded, default_cfg)
        loaded["hub_path"] = str(hub)
        if changed:
            try:
                config_file.write_text(json.dumps(loaded, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception:
                pass
        return loaded
    except Exception:
        return default_cfg


def _merge_missing(dst, src):
    """없는 키만 채웁니다. 이미 저장된 API 키와 프로젝트 값은 건드리지 않습니다."""
    changed = False
    for k, v in src.items():
        if k not in dst:
            dst[k] = v
            changed = True
        elif isinstance(v, dict) and isinstance(dst.get(k), dict):
            if _merge_missing(dst[k], v):
                changed = True
    return changed


def save_config(cfg):
    """설정값(API 키 등)을 seller_hub_data/config.json에 영구 저장"""
    hub = Path(cfg.get("hub_path", st.session_state.get("hub_path", str(DEFAULT_HUB_DIR))))
    hub.mkdir(parents=True, exist_ok=True)
    (hub / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def get_default_9steps(msize="", kw="제품"):
    """
    소비자 궁금증 흐름 9단계 공식 기본 데이터 (인위적인 번역투/AI투 전면 배제, 실전 커머스 카피)
    """
    kw_str = str(kw or "제품").strip()
    size_str = f"실측 {msize}" if msize else f"{kw_str} 상세 규격"

    is_mount = any(w in kw_str for w in ["거치", "마운트", "홀더", "오토바이", "바이크", "자전거", "차량", "암"])

    if is_mount:
        return [
            {
                "step": 1,
                "role": "CHECK POINT 01",
                "subtitle": "주행 중 시야 방해 없는 안정적인 피팅",
                "main_title": f"어떤 노면에서도 흔들림 없는 {kw_str}",
                "body": "덜컹거리는 요철이나 고속 주행에서도 폰이 이탈할 걱정이 없습니다.<>단단하게 맞물리는 결착 구조로 안심하고 주행에만 집중하세요."
            },
            {
                "step": 2,
                "role": "CHECK POINT 02",
                "subtitle": "타협 없는 실사용 마감 퀄리티",
                "main_title": "미세한 유격까지 꽉 잡아주는 정밀 설계",
                "body": "헐겁게 겉돌던 저가형 마운트의 유격과 진동 스트레스를 완전히 잡았습니다.<>볼 조인트와 고정 나사의 완벽한 밀착으로 원하는 위치를 견고하게 지탱합니다."
            },
            {
                "step": 3,
                "role": "KEY FEATURES",
                "subtitle": "라이더의 눈높이에 맞춘 디테일",
                "main_title": "자유로운 360도 각도 조절 & 탄탄한 지지력",
                "body": "내비게이션 시야에 맞추어 가로·세로 어떤 각도로든 손쉽게 세팅할 수 있습니다.<>주행 중 고개가 꺾이지 않는 튼튼한 고정 텐션을 제공합니다."
            },
            {
                "step": 4,
                "role": "MATERIAL & DURABILITY",
                "subtitle": "비바람과 자외선에도 변함없는",
                "main_title": "고강도 합금 바디 & 내후성 표면 마감",
                "body": "햇볕에 바래고 부서지는 저가 플라스틱이 아닙니다.<>외부 충격과 야외 기후 환경을 거뜬히 견뎌내는 프리미엄 강화 소재를 적용했습니다."
            },
            {
                "step": 5,
                "role": "SPECIFICATION",
                "subtitle": "실측 규격 가이드",
                "main_title": f"실측 규격 및 설치 안내 ({size_str})",
                "body": "핸들바나 미러 마운트 위치에 군더더기 없이 슬림하게 장착됩니다.<>바이크 본연의 멋을 해치지 않는 컴팩트한 디자인입니다."
            },
            {
                "step": 6,
                "role": "COMPATIBILITY",
                "subtitle": "다양한 기종 완벽 호환",
                "main_title": "표준 규격으로 어디든 손쉬운 호환",
                "body": "다양한 스마트폰 기종과 표준 바이크 규격에 유연하게 호환됩니다.<>별도의 복잡한 가공 없이 간편하게 설치하여 즉시 사용하실 수 있습니다."
            },
            {
                "step": 7,
                "role": "DELIVERY",
                "subtitle": "기다림 없는 빠른 안심 발송",
                "main_title": "평일 오후 2시 이전 주문 시 당일 출고",
                "body": "출고 전 꼼꼼한 전수 검수 후 충격 방지 에어캡으로 안전하게 포장하여 발송합니다.<>영업일 기준 1~2일 내 신속하게 수령하실 수 있습니다."
            },
            {
                "step": 8,
                "role": "USER GUIDE",
                "subtitle": "안전한 사용을 위한 팁",
                "main_title": "올바른 장착 요령 및 주의사항",
                "body": "장착 볼트를 대각선 방향으로 균일하게 조여주시면 체결력이 한층 더 강화됩니다.<>주행 전 결착 상태를 가볍게 점검해 주시면 더욱 안전합니다."
            },
            {
                "step": 9,
                "role": "Q&A & WARRANTY",
                "subtitle": "구매 전 확인 & 100% 고객 안심 케어",
                "main_title": "초기 불량 시 100% 무상 교환 보장",
                "body": "전자상거래법 기준에 따라 수령 후 7일 이내 교환·반품이 가능합니다.<>제품에 이상이 있거나 장착에 문의가 있으시면 언제든 신속하게 도와드립니다."
            }
        ]

    return [
        {
            "step": 1,
            "role": "CHECK POINT 01",
            "subtitle": "일상의 퀄리티를 높여주는 감각적인 선택",
            "main_title": f"만족도 높은 완성도, {kw_str}",
            "body": "작은 디테일까지 신경 쓴 완성도로 오래도록 기분 좋게 사용할 수 있습니다.<>군더더기 없는 디자인과 실용적인 편의성을 담았습니다."
        },
        {
            "step": 2,
            "role": "CHECK POINT 02",
            "subtitle": "직접 써보면 느껴지는 차이",
            "main_title": "기본기에 충실한 디테일과 마감",
            "body": "쉽게 닳고 망가지는 일반 제품과 직접 비교해 보세요.<>탄탄한 밸런스와 정밀한 가공으로 실사용 만족감을 높였습니다."
        },
        {
            "step": 3,
            "role": "KEY FEATURES",
            "subtitle": "실사용자를 고려한 3가지 핵심 설계",
            "main_title": "직관적인 사용감 & 탄탄한 내구성",
            "body": "복잡한 과정 없이 누구나 쉽고 편리하게 활용할 수 있도록 최적화했습니다.<>변함없는 사용감을 선사하는 실용적 구조입니다."
        },
        {
            "step": 4,
            "role": "MATERIAL & QUALITY",
            "subtitle": "오랜 시간 함께할 수 있도록",
            "main_title": "엄선된 소재와 깔끔한 마감 처리",
            "body": "충격과 반복 사용에도 거뜬한 내구성 높은 자재를 적용했습니다.<>손에 닿는 감촉부터 튼튼함까지 디테일하게 신경 썼습니다."
        },
        {
            "step": 5,
            "role": "SPECIFICATION",
            "subtitle": "실측 규격 가이드",
            "main_title": f"실측 사이즈 안내 ({size_str})",
            "body": "실제 측정 기준의 정밀한 규격으로 오차 없이 만족스럽게 피팅됩니다.<>불필요한 부피를 줄인 컴팩트한 설계입니다."
        },
        {
            "step": 6,
            "role": "VERSATILITY",
            "subtitle": "언제 어디서나 폭넓은 실용성",
            "main_title": "다양한 환경에 유연하게 어우러지는 호환성",
            "body": "어느 공간, 어떤 상황에서도 자연스럽게 매치됩니다.<>일상 속 다양한 순간에 편리함을 더해드립니다."
        },
        {
            "step": 7,
            "role": "DELIVERY",
            "subtitle": "기다림 없는 빠른 안심 발송",
            "main_title": "평일 오후 2시 이전 주문 시 당일 출고",
            "body": "꼼꼼한 사전 검수 후 안전 완충 포장으로 발송해 드립니다.<>영업일 기준 1~2일 내 빠르게 받아보실 수 있습니다."
        },
        {
            "step": 8,
            "role": "CARE GUIDE",
            "subtitle": "오래도록 깔끔하게 사용하는 팁",
            "main_title": "손쉬운 관리 요령 및 주의사항",
            "body": "사용 후 가볍게 닦아 보관해 주시면 제품 본연의 컨디션을 오래 유지할 수 있습니다.<>안전 가이드를 준수하여 쾌적하게 사용해 주세요."
        },
        {
            "step": 9,
            "role": "Q&A & WARRANTY",
            "subtitle": "구매 전 확인 & 100% 고객 안심 케어",
            "main_title": "초기 불량 시 100% 무상 교환 보장",
            "body": "전자상거래법 기준에 따라 수령 후 7일 이내 교환·반품이 가능합니다.<>초기 불량이나 이상 발생 시 신속하고 친절하게 케어해 드립니다."
        }
    ]


def blank_9steps():
    """새 프로젝트용 9단계. 역할만 두고 다른 제품 문장은 넣지 않습니다."""
    steps = get_default_9steps()
    for step in steps:
        step["subtitle"] = ""
        step["main_title"] = ""
        step["body"] = ""
    return steps


def get_default_project_data():
    """새 프로젝트 생성 시 기본 스키마 (기존 데이터와 100% 호환)"""
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
        "cutout_v": "v7.0_clean_isolated",
        "marketer_v": "v6.0_clean_copy",
        "photo_ai_report": {
            "engine_used": "아직 보정 전입니다.",
            "process_steps": [],
            "api_diagnosis": ""
        },
        "spec_qa": {},
        "product_specs": [
            {"label": "품명 및 모델명", "value": "", "항목": "품명 및 모델명", "내용": ""},
            {"label": "실측 사이즈 / 중량", "value": "", "항목": "실측 사이즈 / 중량", "내용": ""},
            {"label": "재질", "value": "", "항목": "재질", "내용": ""},
            {"label": "핵심 기능", "value": "", "항목": "핵심 기능", "내용": ""},
            {"label": "주요 사용처", "value": "", "항목": "주요 사용처", "내용": ""}
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
            "caution_note": ""
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
        "slot1_media": {"type": "", "data": "", "caption": ""},
        "slot2_media": {"type": "", "data": "", "caption": ""},
        "slot3_media": {"type": "", "data": "", "caption": ""},
        "title_font": font_keys[1] if len(font_keys) > 1 else "Pretendard",
        "body_font": font_keys[0] if len(font_keys) > 0 else "Pretendard",
        "nine_steps": blank_9steps(),
        "six_agents_research": {},
        "page_blocks": {
            "hook_badge": "",
            "hook_title": "",
            "hook_sub": "",
            "keywords": [],
            "point1_title": "",
            "point1_desc": "",
            "point2_title": "",
            "point2_desc": "",
            "point3_title": "",
            "point3_desc": "",
            "price_origin": "",
            "price_sale": "",
            "price_reason": "",
            "photo_requests": []
        },
        "draft_html": ""
    }


def list_projects():
    """모든 프로젝트 목록 불러오기 (최신 수정순)"""
    hub = Path(st.session_state.get("hub_path", str(DEFAULT_HUB_DIR)))
    proj_dir = hub / "projects"
    proj_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(proj_dir.glob("*.json"), key=os.path.getmtime, reverse=True)
    res = []
    def_d = get_default_project_data()
    for f in files:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            for k, v in def_d.items():
                if k not in d:
                    d[k] = copy.deepcopy(v)
            res.append((f.stem, d))
        except Exception:
            pass
    return res


def save_project(proj_id, data):
    """프로젝트 데이터를 seller_hub_data/projects/<proj_id>.json 에 영구 저장"""
    hub = Path(st.session_state.get("hub_path", str(DEFAULT_HUB_DIR)))
    proj_dir = hub / "projects"
    proj_dir.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (proj_dir / f"{proj_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def duplicate_project(proj_id):
    """기존 프로젝트 100% 복제"""
    hub = Path(st.session_state.get("hub_path", str(DEFAULT_HUB_DIR)))
    proj_dir = hub / "projects"
    src_file = proj_dir / f"{proj_id}.json"
    if not src_file.exists():
        return None, None
    data = json.loads(src_file.read_text(encoding="utf-8"))
    new_id = f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}_copy"
    data["title"] = f"{data.get('title', '프로젝트')} (복제본)"
    save_project(new_id, data)
    return new_id, data


def delete_project(proj_id):
    """프로젝트 파일 삭제"""
    hub = Path(st.session_state.get("hub_path", str(DEFAULT_HUB_DIR)))
    f = hub / "projects" / f"{proj_id}.json"
    if f.exists():
        f.unlink()


def create_hub_backup_zip():
    """전체 데이터(설정 + 프로젝트들) ZIP 백업 생성"""
    hub = Path(st.session_state.get("hub_path", str(DEFAULT_HUB_DIR)))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file_path in hub.rglob("*"):
            if file_path.is_file():
                arcname = f"seller_hub_data/{file_path.relative_to(hub).as_posix()}"
                zf.write(file_path, arcname=arcname)
    buf.seek(0)
    return buf.getvalue()


def restore_hub_backup_zip(file_bytes):
    """ZIP 백업을 현재 작업 폴더에 복원합니다. 경로 탈출은 허용하지 않습니다."""
    hub = Path(st.session_state.get("hub_path", str(DEFAULT_HUB_DIR))).resolve()
    hub.mkdir(parents=True, exist_ok=True)
    restored = 0
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if name.startswith("seller_hub_data/"):
                name = name[len("seller_hub_data/"):]
            parts = [p for p in name.split("/") if p and p != "."]
            if not parts or any(p == ".." for p in parts):
                continue
            dest = (hub.joinpath(*parts)).resolve()
            if not str(dest).startswith(str(hub)):
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(info))
            restored += 1
    return restored
