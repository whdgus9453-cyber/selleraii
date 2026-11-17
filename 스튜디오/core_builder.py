import io
import re
import json
import struct
import zipfile
import base64
from html import escape
from PIL import Image
from ui_styles import MARKETER_FONTS
from core_storage import get_default_project_data, get_default_9steps
from core_media import pil_to_base64_url, base64_url_to_pil, get_platform_spec
# get_platform_spec imported from core_media

# =====================================================================
# [상세페이지 전체 톤 & 배경 테마 10종 프리셋]
# =====================================================================
BRAND_THEMES = {
    "1. 스타벅스 딥그린 & 민트 크림 (#00704A)": {
        "primary": "#00704A", "dark": "#004E34", "light_bg": "#ECFDF5", "sec_bg": "#F4FBF7",
        "light_border": "#6EE7B7", "badge_bg": "#00704A", "accent_text": "#FACC15", "page_bg": "#FFFFFF"
    },
    "2. 토스/애플 클린 화이트 & 네이비 (#1D4ED8)": {
        "primary": "#1D4ED8", "dark": "#0F172A", "light_bg": "#EFF6FF", "sec_bg": "#F8FAFC",
        "light_border": "#93C5FD", "badge_bg": "#DC2626", "accent_text": "#FACC15", "page_bg": "#FFFFFF"
    },
    "3. 보쉬/밀워키 엔지니어링 다크 메탈 (#0F172A)": {
        "primary": "#0F172A", "dark": "#020617", "light_bg": "#E2E8F0", "sec_bg": "#F1F5F9",
        "light_border": "#64748B", "badge_bg": "#DC2626", "accent_text": "#38BDF8", "page_bg": "#F8FAFC"
    },
    "4. 무신사/블랙라벨 매트 블랙 & 실버 (#18181B)": {
        "primary": "#18181B", "dark": "#09090B", "light_bg": "#F4F4F5", "sec_bg": "#FAFAFA",
        "light_border": "#A1A1AA", "badge_bg": "#18181B", "accent_text": "#FDE047", "page_bg": "#FFFFFF"
    },
    "5. 쿠팡/특가 비비드 레드 & 옐로우 (#DC2626)": {
        "primary": "#DC2626", "dark": "#450A0A", "light_bg": "#FEF2F2", "sec_bg": "#FFF5F5",
        "light_border": "#FCA5A5", "badge_bg": "#DC2626", "accent_text": "#FDE047", "page_bg": "#FFFFFF"
    },
    "6. 디월트 인더스트리얼 옐로우 & 차콜 (#CA8A04)": {
        "primary": "#B45309", "dark": "#1C1917", "light_bg": "#FEFCE8", "sec_bg": "#FAF9F5",
        "light_border": "#FDE047", "badge_bg": "#1C1917", "accent_text": "#FACC15", "page_bg": "#FFFFFF"
    },
    "7. 이케아 노르딕 웜그레이 & 블루 (#0369A1)": {
        "primary": "#0369A1", "dark": "#0C4A6E", "light_bg": "#F0F9FF", "sec_bg": "#F5F5F4",
        "light_border": "#7DD3FC", "badge_bg": "#0284C7", "accent_text": "#FDE047", "page_bg": "#FAFAF9"
    },
    "8. 무인양품 내추럴 우드 & 베이지 (#92400E)": {
        "primary": "#78350F", "dark": "#451A03", "light_bg": "#FEF3C7", "sec_bg": "#FAF6F0",
        "light_border": "#D97706", "badge_bg": "#78350F", "accent_text": "#FDE68A", "page_bg": "#FFFDF9"
    },
    "9. 백화점 명품관 골드 & 딥차콜 (#B45309)": {
        "primary": "#92400E", "dark": "#1E1B18", "light_bg": "#FFFBEB", "sec_bg": "#F9F6F0",
        "light_border": "#F59E0B", "badge_bg": "#1E1B18", "accent_text": "#FBBF24", "page_bg": "#FFFFFF"
    },
    "10. 생활밀착 워커스 오렌지 & 크림 (#EA580C)": {
        "primary": "#EA580C", "dark": "#431407", "light_bg": "#FFF7ED", "sec_bg": "#FFFBF7",
        "light_border": "#FDBA74", "badge_bg": "#EA580C", "accent_text": "#FDE047", "page_bg": "#FFFFFF"
    }
}

DEFAULT_SHIPPING_INFO = {
    "courier": "CJ대한통운 / 한진택배 (안심 안전포장 발송)",
    "cutoff": "평일 오후 2시(14:00) 이전 결제 완료 시 당일 출고 (주말·공휴일 제외)",
    "eta": "출고 후 영업일 기준 평균 1~2일 이내 수령 (택배사 물량에 따라 일부 변동 가능)",
    "fee": "기본 배송비 3,000원 (묶음배송 가능 / 제주 및 도서·산간 지역 추가 배송비 별도)",
    "exchange": "전자상거래법 준수: 상품 수령 후 7일 이내 교환/반품 가능 (제품 불량·오배송 시 배송비 판매자 100% 부담)"
}

DEFAULT_PRODUCT_SPECS = [
    {"항목": "품명 및 모델명", "내용": "프리미엄 정밀 호환 제품"},
    {"항목": "실측 규격 / 사이즈", "내용": "상세페이지 내 실측 규격 안내 참조 (오차범위 ±1~2mm)"},
    {"항목": "재질 및 사양", "내용": "고강도 내구성 복합 소재 + 정밀 가공 표면 마감"},
    {"항목": "주요 사용 용도", "내용": "안정적인 고정 및 장착, 편의성 향상"},
    {"항목": "제조국 / 품질보증", "내용": "OEM (국내 검수 후 출고) / 전자상거래법 기준 초기 불량 100% 무상 교환 보장"}
]


def _clean_step_prefix(text):
    """불필요한 'STEP 01', 'step 9', 'STEP 1 ·' 등의 번호 표기를 깔끔하게 제거합니다."""
    if not text:
        return ""
    cleaned = re.sub(r"^(?:STEP|step|Step)\s*0?\d+\s*[·\-\:\.]*\s*", "", str(text).strip())
    return cleaned


def _format_step_body(text):
    """<> 문단 여백 마커와 개행을 깔끔한 HTML로 변환합니다."""
    if not text:
        return ""
    s = _clean_step_prefix(str(text)).replace("\r", "")
    s = s.replace("<>", '<span style="display:block; height:14px;"></span>')
    s = s.replace("\n", "<br>")
    return s


def render_media_tag(media_dict, max_w=680):
    if not media_dict or not media_dict.get("data"):
        return ""
    mtype = media_dict.get("type", "image")
    durl = media_dict.get("data", "")
    cap = _clean_step_prefix(media_dict.get("caption", ""))

    if mtype == "video":
        inner = (
            f'<div style="max-width:{max_w}px; margin:0 auto; padding:8px; background:#ffffff; border-radius:20px; '
            f'border:1px solid #cbd5e1; box-shadow:0 12px 28px rgba(15,23,42,0.12);">'
            f'<video src="{durl}" autoplay loop muted playsinline style="width:100%; border-radius:14px; display:block;"></video>'
            f'</div>'
        )
    else:
        inner = (
            f'<div style="max-width:{max_w}px; margin:0 auto; padding:8px; background:#ffffff; border-radius:20px; '
            f'border:1px solid #cbd5e1; box-shadow:0 12px 28px rgba(15,23,42,0.10);">'
            f'<img src="{durl}" style="width:100%; border-radius:14px; display:block;" />'
            f'</div>'
        )

    cap_html = f'<div contenteditable="true" style="text-align:center; font-size:14px; color:#475569; font-weight:700; margin-top:10px;">▲ {cap}</div>' if cap else ""
    return f'<div style="margin:24px auto; text-align:center;">{inner}{cap_html}</div>'


def render_structured_detail_html(pdata, studio_cfg=None):
    """
    1) 마우스 우클릭(ContextMenu) 시 MS 워드처럼 '한 글자씩' 폰트(10종)·크기(px)·두께·기울기·밑줄·색상·형광펜을 바꾸는 플로팅 에디터 탑재!
    2) 가로 사이즈 우선 선택 규격(860px / 780px / 750px / 970px / 800px 등) 및 적합 플랫폼 자동 반영!
    3) 어색한 `STEP 01` ~ `STEP 09` 번호 배지를 모두 제거하고, 상위권 셀러들의 자연스러운 판매 워딩과 문장 호흡으로 구성!
    """
    def_data = get_default_project_data()
    b = pdata.get("page_blocks", def_data["page_blocks"])
    kw_now = (pdata.get("keyword") or "").strip()
    hook_now = (b.get("hook_title") or "").strip()
    steps_now = pdata.get("nine_steps") or []
    has_copy = any(
        (s.get("body") or "").strip() or (s.get("main_title") or "").strip()
        for s in steps_now if isinstance(s, dict)
    )
    if not kw_now and not hook_now and not has_copy:
        ship = pdata.get("shipping_info") or {}
        exchange = ship.get("exchange") or ship.get("exchange_info") or ""
        return (
            '<div style="max-width:860px;margin:24px auto;padding:28px;background:#ffffff;color:#0f172a;font-family:sans-serif;">'
            "<h2 style=\"margin:0 0 8px;\">새 제품 상세페이지</h2>"
            "<p>이 프로젝트에는 아직 이 제품의 문장과 사진이 없습니다. 1번 탭에 저장한 내용만 여기에 채워집니다.</p>"
            + (f'<p style="font-size:13px;color:#475569;">{exchange}</p>' if exchange else "")
            + "</div>"
        )
    t_font = MARKETER_FONTS.get(pdata.get("title_font"), list(MARKETER_FONTS.values())[1])
    b_font = MARKETER_FONTS.get(pdata.get("body_font"), list(MARKETER_FONTS.values())[0])

    all_fonts_css = "\n".join([f_obj["css"] for f_obj in MARKETER_FONTS.values()])
    font_options_html = "".join([
        f'<option value="{f_obj["family"].replace(chr(34), "&quot;")}">{f_label.split("(")[0].strip()}</option>'
        for f_label, f_obj in MARKETER_FONTS.items()
    ])

    plat_key = pdata.get("target_platform", def_data["target_platform"])
    plat_spec = get_platform_spec(plat_key)
    detail_w = int(plat_spec.get("detail_width", 860))
    thumb_w, thumb_h = plat_spec.get("thumb_size", (1000, 1000))
    plat_name = plat_spec.get("name", "가로 860px 표준")
    rec_plats = plat_spec.get("recommended_platforms", "네이버 스마트스토어 · G마켓 · 옥션 · 11번가")

    theme_key = pdata.get("theme_color", "")
    if not theme_key or theme_key not in BRAND_THEMES:
        matched = next((k for k in BRAND_THEMES if ("스타벅스" in theme_key and "스타벅스" in k) or ("네이비" in theme_key and "네이비" in k)), None)
        theme_key = matched or "1. 스타벅스 딥그린 & 민트 크림 (#00704A)"
    theme = BRAND_THEMES[theme_key]

    typo = pdata.get("typo_settings", {})
    title_size = int(typo.get("title_size", 36))
    sub_size = max(18, int(title_size * 0.56))
    sec_title_size = max(24, int(title_size * 0.84))
    body_size = int(typo.get("body_size", 16))
    title_weight = typo.get("title_weight", "900")
    body_weight = typo.get("body_weight", "500")
    title_italic = "italic" if typo.get("title_italic", False) else "normal"
    body_italic = "italic" if typo.get("body_italic", False) else "normal"
    title_color = typo.get("title_color") or "#0f172a"
    body_color = typo.get("body_color") or "#334155"
    page_bg = typo.get("page_bg") or theme.get("page_bg", "#ffffff")

    main_img = pdata.get("edited_img_b64") or pdata.get("orig_img_b64")
    if not main_img:
        dummy = Image.new("RGB", (800, 480), (30, 41, 59))
        main_img = pil_to_base64_url(dummy)

    kw_badges_html = "".join([
        f'<span contenteditable="true" style="display:inline-block; background:{theme["light_bg"]}; color:{theme["primary"]}; border:1px solid {theme["light_border"]}; padding:7px 15px; border-radius:999px; font-weight:700; font-size:{max(13, body_size-1)}px; margin:4px;">#{_clean_step_prefix(k)}</span>'
        for k in b.get("keywords", []) if k.strip()
    ])

    slot1_html = render_media_tag(pdata.get("slot1_media"), max_w=min(680, detail_w - 60))
    slot2_html = render_media_tag(pdata.get("slot2_media"), max_w=min(680, detail_w - 60))
    slot3_html = render_media_tag(pdata.get("slot3_media"), max_w=min(680, detail_w - 60))

    # 다각도 추가 사진 갤러리 (멀티 업로드 사진 및 사용자가 반영 체크한 사진들을 자연스럽게 디테일 컷으로 노출)
    multi_imgs = pdata.get("multi_images", [])
    multi_gallery_html = ""
    active_gallery_imgs = [m for m in multi_imgs if m.get("use_in_page", True)]
    if active_gallery_imgs:
        cards = []
        for idx_m, m_item in enumerate(active_gallery_imgs):
            mb64 = m_item.get("polished_b64") or m_item.get("b64") or ""
            mlabel = _clean_step_prefix(m_item.get("angle_label") or f"다각도 실물 디테일 컷 {idx_m+1}")
            is_cutout_card = m_item.get("is_cutout", False)
            img_bg_style = "background:transparent; filter:drop-shadow(0 4px 10px rgba(0,0,0,0.12));" if is_cutout_card else "background:#ffffff; border-radius:12px;"
            if mb64:
                cards.append(f"""
                <div style="flex:1; min-width:210px; max-width:320px; background:#ffffff; border:1px solid #cbd5e1; border-radius:16px; padding:12px; box-shadow:0 6px 16px rgba(15,23,42,0.06); margin-bottom:8px;">
                    <img src="{mb64}" style="width:100%; height:auto; display:block; {img_bg_style}" />
                    <div contenteditable="true" style="font-size:13px; font-weight:700; color:#334155; margin-top:10px; text-align:center;">{mlabel}</div>
                </div>
                """)
        if cards:
            cards_joined = "".join(cards)
            multi_gallery_html = f"""
            <div style="margin:24px auto 10px auto; max-width:96%;">
                <div contenteditable="true" style="font-size:15px; font-weight:800; color:{theme['primary']}; margin-bottom:12px; text-align:center;">📸 실물 디테일 & 다각도 컷 갤러리</div>
                <div style="display:flex; gap:14px; flex-wrap:wrap; justify-content:center;">
                    {cards_joined}
                </div>
            </div>
            """

    kw_str = (pdata.get("keyword") or pdata.get("title") or "제품").strip()
    msize_str = pdata.get("manual_size") or ""
    nine_steps = pdata.get("nine_steps")
    if not nine_steps or len(nine_steps) < 9:
        nine_steps = get_default_9steps(msize=msize_str, kw=kw_str)
    s1, s2, s3, s4, s5, s6, s7, s8, s9 = nine_steps[:9]

    specs = pdata.get("product_specs") or DEFAULT_PRODUCT_SPECS
    spec_rows_html = ""
    for sp in specs:
        k_sp = _clean_step_prefix(sp.get("항목") or sp.get("label") or "")
        v_sp = _clean_step_prefix(sp.get("내용") or sp.get("value") or "")
        if "실측" in k_sp and pdata.get("manual_size"):
            v_sp = pdata["manual_size"]
        elif ("품명" in k_sp or "모델" in k_sp) and (not v_sp or ("드라이버" in v_sp and "드라이버" not in kw_str)):
            v_sp = kw_str
        elif ("용도" in k_sp or "사용처" in k_sp) and ("나사" in v_sp and "나사" not in kw_str):
            v_sp = f"{kw_str} 표준 규격 호환 및 다목적 장착"
        elif ("재질" in k_sp or "사양" in k_sp) and ("비트" in v_sp or "회전캡" in v_sp or "합금강" in v_sp and "드라이버" not in kw_str):
            v_sp = "고강도 내구성 소재 + 정밀 마감"
        spec_rows_html += f"""
        <tr>
            <th contenteditable="true" style="width:28%; background:{theme['sec_bg']}; color:{theme['dark']}; padding:13px 16px; border:1px solid #cbd5e1; font-weight:800; text-align:left; font-size:{max(13, body_size-1)}px;">{k_sp}</th>
            <td contenteditable="true" style="width:72%; background:#ffffff; color:{body_color}; padding:13px 16px; border:1px solid #cbd5e1; font-weight:{body_weight}; font-size:{max(13, body_size-1)}px; line-height:1.5;">{v_sp}</td>
        </tr>
        """

    ship = pdata.get("shipping_info") or DEFAULT_SHIPPING_INFO
    ship_courier = ship.get("courier") or DEFAULT_SHIPPING_INFO["courier"]
    ship_cutoff = ship.get("cutoff") or ship.get("cutoff_time") or DEFAULT_SHIPPING_INFO["cutoff"]
    ship_eta = ship.get("eta") or ship.get("delivery_days") or DEFAULT_SHIPPING_INFO["eta"]
    ship_fee = ship.get("fee") or ship.get("shipping_fee") or DEFAULT_SHIPPING_INFO["fee"]
    ship_exchange = ship.get("exchange") or ship.get("exchange_info") or DEFAULT_SHIPPING_INFO["exchange"]
    ship_caution = ship.get("caution_note") or f"{kw_str} 결착 부위를 정확히 확인하시고, 무리한 힘을 가하지 마시고 안전 가이드에 따라 사용해 주세요."
    brand = (studio_cfg or {}).get("brand_preset") or {}
    if (brand.get("shipping_fee") or "").strip():
        ship_fee = brand["shipping_fee"].strip()
    if (brand.get("exchange_notice") or "").strip():
        notice = brand["exchange_notice"].strip()
        if "전자상거래" not in notice and "7일" not in notice:
            notice = "전자상거래 등에서의 소비자보호에 관한 법률에 따라 수령 후 7일 이내 교환·반품이 가능합니다. " + notice
        ship_exchange = notice
    image_defaults = (studio_cfg or {}).get("image_defaults") or {}
    shadow_px = int(image_defaults.get("shadow_strength") or 18)
    shadow_px = max(0, min(40, shadow_px))
    if shadow_px <= 0:
        shadow_css = "none"
    else:
        shadow_blur = max(8, int(shadow_px * 1.35))
        # 역제곱 법칙 2중 물리 그림자 (Contact AO + Penumbra 확산)
        shadow_css = f"drop-shadow(0px 2px 4px rgba(0, 0, 0, 0.36)) drop-shadow(0px {shadow_px}px {shadow_blur}px rgba(15, 23, 42, 0.20))"
    cutout_src = pdata.get("fg_cutout_b64") or (pdata.get("photo_ai_report") or {}).get("fg_cutout_b64") or ""
    if cutout_src:
        hero_img_html = (
            f'<div style="max-width:{min(720, detail_w - 50)}px; margin:18px auto 0 auto; background:transparent; border:none; overflow:visible;">'
            f'<img src="{cutout_src}" alt="제품 누끼" style="width:78%; max-width:560px; height:auto; display:block; margin:8px auto 20px auto; background:transparent; filter:{shadow_css};" />'
            f'</div>'
        )
    else:
        hero_img_html = (
            f'<div style="max-width:{min(720, detail_w - 50)}px; margin:14px auto 0 auto; border-radius:20px; overflow:hidden; box-shadow:0 12px 32px rgba(15,23,42,0.08); border:1px solid {theme["light_border"]}; background:#ffffff;">'
            f'<img src="{main_img}" style="width:100%; display:block;" />'
            f'</div>'
        )
    store_name = (brand.get("store_name") or "").strip()
    slogan = (brand.get("slogan") or "").strip()
    brand_footer_html = ""
    if store_name or slogan:
        brand_footer_html = (
            f'<div contenteditable="true" style="margin-top:16px; color:#cbd5e1; font-size:{max(13, body_size-1)}px; font-weight:700;">'
            f'{store_name}{(" · " + slogan) if slogan else ""}'
            f'</div>'
        )

    hook_badge_clean = _clean_step_prefix(b.get('hook_badge') or f'실속형 {kw_str}')

    html = f"""
    <style>
        {all_fonts_css}
        .sp-container {{
            font-family: {b_font['family']};
            font-size: {body_size}px;
            font-weight: {body_weight};
            font-style: {body_italic};
            box-sizing: border-box;
            letter-spacing: -0.3px;
            background-color: {page_bg};
            color: {body_color};
            position: relative;
        }}
        .sp-container * {{
            box-sizing: border-box;
        }}
        .sp-title {{
            font-family: {t_font['family']};
            font-weight: {title_weight};
            font-style: {title_italic};
            letter-spacing: -0.6px;
        }}
        .sp-main-heading {{
            color: {title_color};
            font-size: {title_size}px;
            line-height: 1.24;
        }}
        .sp-sec-heading {{
            color: {title_color};
            font-size: {sec_title_size}px;
            line-height: 1.28;
        }}
        .sp-sub-eyebrow {{
            color: {theme['primary']};
            font-size: {sub_size}px;
            font-weight: 800;
            letter-spacing: -0.4px;
            margin-bottom: 8px;
        }}
        .sp-section-pill {{
            display: inline-block;
            background: {theme['light_bg']};
            color: {theme['primary']};
            border: 1px solid {theme['light_border']};
            font-size: 12px;
            font-weight: 800;
            padding: 4px 14px;
            border-radius: 999px;
            margin-bottom: 10px;
            letter-spacing: -0.2px;
        }}
        .sp-desc-box {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 22px 24px;
            margin: 18px auto 0 auto;
            max-width: 92%;
            line-height: 1.65;
            color: {body_color};
            font-size: {body_size}px;
        }}
        [contenteditable="true"]:hover {{
            outline: 2px dashed {theme['primary']};
            background-color: rgba(37, 99, 235, 0.03);
            cursor: text;
        }}
        .sp-toolbar {{
            position: sticky;
            top: 0;
            z-index: 990;
            background: #0f172a;
            color: #f8fafc;
            padding: 10px 14px;
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            align-items: center;
            justify-content: space-between;
            border-bottom: 3px solid {theme['primary']};
            font-family: 'Pretendard', sans-serif;
            font-size: 12.5px;
        }}
        .sp-toolbar-btn {{
            background: #2563eb;
            color: #ffffff;
            border: 1px solid #60a5fa;
            border-radius: 8px;
            padding: 5px 12px;
            cursor: pointer;
            font-weight: 800;
            font-size: 12px;
        }}
        .sp-toolbar-btn:hover {{
            background: #1d4ed8;
        }}
        #word-context-menu {{
            position: fixed;
            display: none;
            z-index: 99999;
            width: 345px;
            background: #0f172a;
            color: #f8fafc;
            border: 2px solid #38bdf8;
            border-radius: 14px;
            padding: 12px 14px;
            box-shadow: 0 20px 45px rgba(0, 0, 0, 0.55);
            font-family: 'Pretendard', -apple-system, sans-serif;
            font-size: 12.5px;
            user-select: none;
        }}
        #word-context-menu.open {{
            display: block;
        }}
        .wcm-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #334155;
            padding-bottom: 7px;
            margin-bottom: 9px;
        }}
        .wcm-badge {{
            background: #1e293b;
            color: #38bdf8;
            border: 1px solid #0284c7;
            padding: 2px 8px;
            border-radius: 6px;
            font-weight: 800;
            font-size: 11.5px;
            max-width: 245px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
        .wcm-close {{
            background: transparent;
            color: #94a3b8;
            border: none;
            font-size: 16px;
            font-weight: 900;
            cursor: pointer;
            padding: 0 4px;
        }}
        .wcm-close:hover {{ color: #ffffff; }}
        .wcm-row {{
            display: flex;
            align-items: center;
            gap: 6px;
            margin-bottom: 8px;
            flex-wrap: wrap;
        }}
        .wcm-label {{
            font-size: 11.5px;
            font-weight: 800;
            color: #cbd5e1;
            min-width: 48px;
        }}
        .wcm-select, .wcm-num {{
            background: #1e293b;
            color: #ffffff;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 4px 7px;
            font-size: 12px;
            font-weight: 700;
            cursor: pointer;
        }}
        .wcm-btn {{
            background: #1e293b;
            color: #f8fafc;
            border: 1px solid #475569;
            border-radius: 6px;
            padding: 4px 8px;
            cursor: pointer;
            font-weight: 800;
            font-size: 12px;
            line-height: 1.2;
        }}
        .wcm-btn:hover {{
            background: #2563eb;
            border-color: #93c5fd;
        }}
        .wcm-chip {{
            width: 20px;
            height: 20px;
            border-radius: 5px;
            border: 1.5px solid rgba(255,255,255,0.45);
            cursor: pointer;
            padding: 0;
        }}
        .wcm-chip:hover {{
            transform: scale(1.18);
            border-color: #ffffff;
        }}
        @media (max-width: 768px) {{
            .sp-main-heading {{ font-size: {max(24, int(title_size*0.78))}px !important; }}
            .sp-sec-heading {{ font-size: {max(20, int(sec_title_size*0.80))}px !important; }}
            .sp-sub-eyebrow {{ font-size: {max(15, int(sub_size*0.85))}px !important; }}
            .sp-desc-box {{ padding: 16px 14px !important; max-width: 98% !important; }}
            #word-context-menu {{ width: 92vw !important; left: 4vw !important; }}
        }}
    </style>

    <!-- [MS 워드 방식 우클릭(ContextMenu) 한 글자씩 실시간 서식 팝업 메뉴] -->
    <div id="word-context-menu" onmousedown="event.stopPropagation()">
        <div class="wcm-header">
            <span class="wcm-badge" id="wcm-target-preview">🔤 선택 글자 서식 편집</span>
            <button type="button" class="wcm-close" onclick="closeWordMenu()" title="닫기">✕</button>
        </div>

        <div class="wcm-row">
            <span class="wcm-label">글꼴(10종)</span>
            <select id="wcm-font" class="wcm-select" style="flex:1;" onchange="applyCharStyle({{fontFamily: this.value}})">
                <option value="">-- 글꼴 변경 (한 글자 가능) --</option>
                {font_options_html}
            </select>
        </div>

        <div class="wcm-row">
            <span class="wcm-label">크기·두께</span>
            <input type="number" id="wcm-size" class="wcm-num" value="24" min="10" max="120" style="width:58px;" onchange="applyCharStyle({{fontSize: this.value + 'px'}})" />
            <span style="font-size:11px; color:#94a3b8;">px</span>
            <button type="button" class="wcm-btn" onclick="stepCharSize(-2)" title="2px 작게">A-</button>
            <button type="button" class="wcm-btn" onclick="stepCharSize(2)" title="2px 크게">A+</button>
            <select id="wcm-weight" class="wcm-select" onchange="applyCharStyle({{fontWeight: this.value}})">
                <option value="">두께</option>
                <option value="300">가는(300)</option>
                <option value="400">보통(400)</option>
                <option value="500">중간(500)</option>
                <option value="700">굵게(700)</option>
                <option value="900">초고굵기(900)</option>
            </select>
        </div>

        <div class="wcm-row">
            <span class="wcm-label">스타일</span>
            <button type="button" class="wcm-btn" onclick="toggleCharStyle('fontWeight', '900', '400')"><b>B 굵게</b></button>
            <button type="button" class="wcm-btn" onclick="toggleCharStyle('fontStyle', 'italic', 'normal')"><i>I 기울임</i></button>
            <button type="button" class="wcm-btn" onclick="toggleCharUnderline()"><u>U 밑줄</u></button>
            <button type="button" class="wcm-btn" onclick="toggleCharStrike()"><s>S 취소선</s></button>
            <button type="button" class="wcm-btn" onclick="clearCharStyle()" style="background:#334155;">초기화</button>
        </div>

        <div class="wcm-row">
            <span class="wcm-label">글자색</span>
            <button type="button" class="wcm-chip" style="background:#0f172a;" onclick="applyCharStyle({{color:'#0f172a'}})"></button>
            <button type="button" class="wcm-chip" style="background:#dc2626;" onclick="applyCharStyle({{color:'#dc2626'}})"></button>
            <button type="button" class="wcm-chip" style="background:#ea580c;" onclick="applyCharStyle({{color:'#ea580c'}})"></button>
            <button type="button" class="wcm-chip" style="background:#00704A;" onclick="applyCharStyle({{color:'#00704A'}})"></button>
            <button type="button" class="wcm-chip" style="background:#2563eb;" onclick="applyCharStyle({{color:'#2563eb'}})"></button>
            <button type="button" class="wcm-chip" style="background:#7c3aed;" onclick="applyCharStyle({{color:'#7c3aed'}})"></button>
            <button type="button" class="wcm-chip" style="background:#facc15;" onclick="applyCharStyle({{color:'#facc15'}})"></button>
            <button type="button" class="wcm-chip" style="background:#ffffff;" onclick="applyCharStyle({{color:'#ffffff'}})"></button>
            <input type="color" id="wcm-color-picker" value="#dc2626" onchange="applyCharStyle({{color:this.value}})" style="width:24px;height:22px;border:none;padding:0;background:transparent;cursor:pointer;" title="직접 색상 선택" />
        </div>

        <div class="wcm-row" style="margin-bottom:2px;">
            <span class="wcm-label">형광펜</span>
            <button type="button" class="wcm-chip" style="background:#fef08a;" onclick="applyCharStyle({{backgroundColor:'#fef08a'}})"></button>
            <button type="button" class="wcm-chip" style="background:#bbf7d0;" onclick="applyCharStyle({{backgroundColor:'#bbf7d0'}})"></button>
            <button type="button" class="wcm-chip" style="background:#bfdbfe;" onclick="applyCharStyle({{backgroundColor:'#bfdbfe'}})"></button>
            <button type="button" class="wcm-chip" style="background:#fecdd3;" onclick="applyCharStyle({{backgroundColor:'#fecdd3'}})"></button>
            <button type="button" class="wcm-chip" style="background:#fed7aa;" onclick="applyCharStyle({{backgroundColor:'#fed7aa'}})"></button>
            <input type="color" value="#fef08a" onchange="applyCharStyle({{backgroundColor:this.value}})" style="width:24px;height:22px;border:none;padding:0;background:transparent;cursor:pointer;" />
            <button type="button" class="wcm-btn" onclick="applyCharStyle({{backgroundColor:'transparent'}})" style="font-size:11px;">형광펜 지움</button>
        </div>
    </div>

    <!-- [상단 고정 안내바 & 사이즈 규격 배지 & 우클릭 편집본 즉시 저장 버튼] -->
    <div class="sp-toolbar" style="max-width:{detail_w}px; margin:0 auto;">
        <div>
            🖱️ <b>워드식 우클릭 편집:</b> 원하는 <b>한 글자(또는 단어)</b> 위에서 <b>마우스 우클릭</b>하면 그 글자만 글꼴·크기·두께·색상을 바꿀 수 있습니다!
            <span style="display:inline-block; background:#1e293b; color:#38bdf8; border:1px solid #38bdf8; border-radius:6px; padding:2px 8px; margin-left:6px; font-weight:800;">
                📐 가로 {detail_w}px / 썸네일 {thumb_w}×{thumb_h}px (적합: {rec_plats})
            </span>
        </div>
        <button type="button" class="sp-toolbar-btn" onclick="downloadEditedPageHtml()">💾 우클릭 수정본 HTML 즉시 저장</button>
    </div>

    <div id="sp-export-root" class="sp-container" style="max-width:{detail_w}px; margin:0 auto; background:{page_bg}; border:1px solid #cbd5e1;">

        <!-- ==================== 첫인상 · 메인 헤드카피 (Hero) ==================== -->
        <div style="padding:48px 30px 38px 30px; text-align:center; background:linear-gradient(180deg, {theme['light_bg']} 0%, {page_bg} 100%); border-bottom:1px solid #e2e8f0;">
            <div contenteditable="true" class="sp-title" style="display:inline-block; background:{theme['badge_bg']}; color:#ffffff; font-size:13.5px; padding:6px 18px; border-radius:99px; margin-bottom:14px;">
                {hook_badge_clean}
            </div>
            <div contenteditable="true" class="sp-sub-eyebrow">
                {_clean_step_prefix(s1.get('subtitle', ''))}
            </div>
            <h1 contenteditable="true" class="sp-title sp-main-heading" style="margin:0 0 14px 0;">
                {_clean_step_prefix(s1.get('main_title') or b.get('hook_title', ''))}
            </h1>
            <p contenteditable="true" style="font-size:{body_size+1}px; color:{body_color}; font-weight:700; margin:0 0 18px 0;">
                {_clean_step_prefix(b.get('hook_sub', ''))}
            </p>
            <div style="margin-bottom:22px;">
                {kw_badges_html}
            </div>

            {slot1_html}

            {hero_img_html}

            {multi_gallery_html}

            <div contenteditable="true" class="sp-desc-box" style="margin-top:24px; background:#ffffff; border-color:{theme['light_border']}; font-weight:600;">
                {_format_step_body(s1.get('body', ''))}
            </div>
        </div>

        <!-- ==================== 차별화 · 핵심 비교 포인트 ==================== -->
        <div style="padding:45px 30px; text-align:center; background:{page_bg}; border-bottom:1px solid #e2e8f0;">
            <span class="sp-section-pill" contenteditable="true">핵심 차별화 포인트</span>
            <div contenteditable="true" class="sp-sub-eyebrow">{_clean_step_prefix(s2.get('subtitle', ''))}</div>
            <h2 contenteditable="true" class="sp-title sp-sec-heading" style="margin:0 0 22px 0; color:{theme['primary']};">
                {_clean_step_prefix(s2.get('main_title', ''))}
            </h2>

            <!-- 일반 저가형 vs 우리 제품 한눈 비교표 -->
            <div style="display:flex; gap:16px; flex-wrap:wrap; text-align:left; margin-bottom:20px;">
                <div style="flex:1; min-width:250px; background:#fef2f2; border:2px solid #fecaca; border-radius:16px; padding:22px;">
                    <div class="sp-title" contenteditable="true" style="color:#991b1b; font-size:{body_size+3}px; margin-bottom:12px;">❌ 일반 시중 저가형 {kw_str}</div>
                    <div contenteditable="true" style="color:#7f1d1d; font-size:{body_size}px; font-weight:600; line-height:1.8;">
                        • 규격이 헐겁거나 유격이 심해 쉽게 흔들리고 이탈 위험<br>
                        • 부실한 마감과 내구성 취약 소재로 잦은 파손 및 교체 스트레스<br>
                        • 부정확한 호환 정보로 실사용 장착 실패 우려
                    </div>
                </div>
                <div style="flex:1; min-width:250px; background:{theme['light_bg']}; border:2px solid {theme['primary']}; border-radius:16px; padding:22px;">
                    <div class="sp-title" contenteditable="true" style="color:{theme['primary']}; font-size:{body_size+3}px; margin-bottom:12px;">⭕ 정밀 설계 {kw_str}</div>
                    <div contenteditable="true" style="color:#0f172a; font-size:{body_size}px; font-weight:700; line-height:1.8;">
                        • 미세 유격까지 빈틈없이 잡아주는 안정적인 밀착 고정 설계<br>
                        • 충격과 반복 사용에도 변형 없는 고내구성 복합 강화 소재<br>
                        • 실측 규격 검증 완료로 완벽 호환 및 직관적 간편 사용
                    </div>
                </div>
            </div>

            <div contenteditable="true" class="sp-desc-box">
                {_format_step_body(s2.get('body', ''))}
            </div>
        </div>

        <!-- ==================== 상품 특징 · 3대 핵심 기능 ==================== -->
        <div style="padding:45px 30px; text-align:center; background:{theme['sec_bg']}; border-bottom:1px solid #e2e8f0;">
            <span class="sp-section-pill" contenteditable="true">핵심 설계 디테일</span>
            <div contenteditable="true" class="sp-sub-eyebrow">{_clean_step_prefix(s3.get('subtitle', ''))}</div>
            <h2 contenteditable="true" class="sp-title sp-sec-heading" style="margin:0 0 24px 0;">
                {_clean_step_prefix(s3.get('main_title', ''))}
            </h2>

            <div style="display:flex; gap:14px; flex-wrap:wrap; justify-content:center; margin-bottom:18px;">
                <div style="flex:1; min-width:200px; background:#ffffff; border:2px solid {theme['light_border']}; border-radius:16px; padding:20px; text-align:center;">
                    <div style="font-size:38px; margin-bottom:8px;">🔒</div>
                    <div contenteditable="true" class="sp-title" style="font-size:{body_size+2}px; color:{theme['primary']}; margin-bottom:6px;">{_clean_step_prefix(b.get('point1_title') or '흔들림 없는 강력 고정')}</div>
                    <div contenteditable="true" style="font-size:{body_size-1}px; color:{body_color}; line-height:1.45;">{_clean_step_prefix(b.get('point1_desc') or '미세한 유격까지 잡아주어 주행 및 일상 사용 시 완벽 밀착')}</div>
                </div>
                <div style="flex:1; min-width:200px; background:#ffffff; border:2px solid {theme['light_border']}; border-radius:16px; padding:20px; text-align:center;">
                    <div style="font-size:38px; margin-bottom:8px;">⚙️</div>
                    <div contenteditable="true" class="sp-title" style="font-size:{body_size+2}px; color:{theme['primary']}; margin-bottom:6px;">{_clean_step_prefix(b.get('point2_title') or '자유로운 각도 세팅')}</div>
                    <div contenteditable="true" style="font-size:{body_size-1}px; color:{body_color}; line-height:1.45;">{_clean_step_prefix(b.get('point2_desc') or '사용자 시야와 장착 환경에 맞추어 유연하고 최적화된 조절 가능')}</div>
                </div>
                <div style="flex:1; min-width:200px; background:#ffffff; border:2px solid {theme['light_border']}; border-radius:16px; padding:20px; text-align:center;">
                    <div style="font-size:38px; margin-bottom:8px;">🛡️</div>
                    <div contenteditable="true" class="sp-title" style="font-size:{body_size+2}px; color:{theme['primary']}; margin-bottom:6px;">{_clean_step_prefix(b.get('point3_title') or '검증된 고강도 내구성')}</div>
                    <div contenteditable="true" style="font-size:{body_size-1}px; color:{body_color}; line-height:1.45;">{_clean_step_prefix(b.get('point3_desc') or '내마모성과 내충격성을 강화한 소재로 오랜 시간 안심 사용')}</div>
                </div>
            </div>

            {slot2_html}

            <div contenteditable="true" class="sp-desc-box" style="background:#ffffff;">
                {_format_step_body(s3.get('body', ''))}
            </div>
        </div>

        <!-- ==================== 제조 · 소재 · 내구성 검증 ==================== -->
        <div style="padding:45px 30px; text-align:center; background:{page_bg}; border-bottom:1px solid #e2e8f0;">
            <span class="sp-section-pill" contenteditable="true">소재 및 내구성 체크</span>
            <div contenteditable="true" class="sp-sub-eyebrow">{_clean_step_prefix(s4.get('subtitle', ''))}</div>
            <h2 contenteditable="true" class="sp-title sp-sec-heading" style="margin:0 0 16px 0;">
                {_clean_step_prefix(s4.get('main_title', ''))}
            </h2>
            <div contenteditable="true" class="sp-desc-box">
                {_format_step_body(s4.get('body', ''))}
            </div>
        </div>

        <!-- ==================== 실물 규격 · 100원 동전 비교 실측 & 상세 스펙표 ==================== -->
        <div style="padding:45px 30px; text-align:center; background:{theme['sec_bg']}; border-bottom:1px solid #e2e8f0;">
            <span class="sp-section-pill" contenteditable="true">실측 사이즈 & 상세 스펙</span>
            <div contenteditable="true" class="sp-sub-eyebrow">{_clean_step_prefix(s5.get('subtitle', ''))}</div>
            <h2 contenteditable="true" class="sp-title sp-sec-heading" style="margin:0 0 16px 0; color:{theme['primary']};">
                {_clean_step_prefix(s5.get('main_title', ''))}
            </h2>
            <div contenteditable="true" class="sp-desc-box" style="background:#ffffff; margin-bottom:24px;">
                {_format_step_body(s5.get('body', ''))}
            </div>

            <div style="text-align:left; background:#ffffff; border-radius:16px; padding:22px; border:1px solid #cbd5e1;">
                <h3 contenteditable="true" class="sp-title" style="font-size:{body_size+4}px; color:{theme['dark']}; margin:0 0 14px 0;">
                    📋 제품 상세 스펙 및 기본 정보 (전자상거래법 상품정보제공고시 준수)
                </h3>
                <table style="width:100%; border-collapse:collapse; border:1px solid #cbd5e1;">
                    {spec_rows_html}
                </table>
            </div>
        </div>

        <!-- ==================== 사용법 · 상황별 활용 가이드 ==================== -->
        <div style="padding:45px 30px; text-align:center; background:{page_bg}; border-bottom:1px solid #e2e8f0;">
            <span class="sp-section-pill" contenteditable="true">다용도 활용 가이드</span>
            <div contenteditable="true" class="sp-sub-eyebrow">{_clean_step_prefix(s6.get('subtitle', ''))}</div>
            <h2 contenteditable="true" class="sp-title sp-sec-heading" style="margin:0 0 18px 0;">
                {_clean_step_prefix(s6.get('main_title', ''))}
            </h2>

            <div style="display:grid; grid-template-columns:repeat(2, 1fr); gap:12px; text-align:left; max-width:92%; margin:0 auto 18px auto;">
                <div contenteditable="true" style="background:{theme['light_bg']}; border:1px solid {theme['light_border']}; border-radius:12px; padding:14px 16px; font-weight:700;">
                    🎯 <b>표준 규격 호환:</b> 범용 표준 설계로 폭넓은 사용 환경에 안정적인 결착
                </div>
                <div contenteditable="true" style="background:{theme['light_bg']}; border:1px solid {theme['light_border']}; border-radius:12px; padding:14px 16px; font-weight:700;">
                    ⚡ <b>간편한 탈부착:</b> 복잡한 도구 없이 직관적이고 손쉬운 장착 및 조절
                </div>
                <div contenteditable="true" style="background:{theme['light_bg']}; border:1px solid {theme['light_border']}; border-radius:12px; padding:14px 16px; font-weight:700;">
                    🛡️ <b>흔들림 없는 지지력:</b> 거친 진동과 일상 충격에도 견고한 안정성 유지
                </div>
                <div contenteditable="true" style="background:{theme['light_bg']}; border:1px solid {theme['light_border']}; border-radius:12px; padding:14px 16px; font-weight:700;">
                    ✨ <b>실측 최적화 피팅:</b> 불필요한 부피를 줄인 컴팩트한 완성도
                </div>
            </div>

            {slot3_html}

            <div contenteditable="true" class="sp-desc-box">
                {_format_step_body(s6.get('body', ''))}
            </div>
        </div>

        <!-- ==================== 배송 안내 ==================== -->
        <div style="padding:42px 30px; text-align:center; background:{theme['sec_bg']}; border-bottom:1px solid #e2e8f0;">
            <span class="sp-section-pill" contenteditable="true">출고 및 배송 안내</span>
            <div contenteditable="true" class="sp-sub-eyebrow">{_clean_step_prefix(s7.get('subtitle', ''))}</div>
            <h2 contenteditable="true" class="sp-title sp-sec-heading" style="margin:0 0 16px 0;">
                {_clean_step_prefix(s7.get('main_title', ''))}
            </h2>
            <div contenteditable="true" class="sp-desc-box" style="background:#ffffff; margin-bottom:18px;">
                {_format_step_body(s7.get('body', ''))}
            </div>
            <div style="text-align:left; max-width:92%; margin:0 auto; background:#ffffff; border:1px solid #cbd5e1; border-radius:14px; padding:18px 20px; line-height:1.85; font-size:{max(13, body_size-1)}px;">
                <div contenteditable="true">• <b>지정 택배사:</b> {ship_courier}</div>
                <div contenteditable="true">• <b>당일 출고 마감:</b> <span style="color:{theme['primary']}; font-weight:800;">{ship_cutoff}</span></div>
                <div contenteditable="true">• <b>평균 배송 기간:</b> {ship_eta}</div>
                <div contenteditable="true">• <b>배송비 안내:</b> {ship_fee}</div>
            </div>
        </div>

        <!-- ==================== 올바른 사용법 & 보관 팁 ==================== -->
        <div style="padding:42px 30px; text-align:center; background:{page_bg}; border-bottom:1px solid #e2e8f0;">
            <span class="sp-section-pill" contenteditable="true">사용 팁 & 주의사항</span>
            <div contenteditable="true" class="sp-sub-eyebrow">{_clean_step_prefix(s8.get('subtitle', ''))}</div>
            <h2 contenteditable="true" class="sp-title sp-sec-heading" style="margin:0 0 16px 0;">
                {_clean_step_prefix(s8.get('main_title', ''))}
            </h2>
            <div contenteditable="true" class="sp-desc-box">
                {_format_step_body(s8.get('body', ''))}
                <span style="display:block; height:10px;"></span>
                <b>⚠️ 사용 시 주의사항:</b> {ship_caution}
            </div>
        </div>

        <!-- ==================== 자주 묻는 질문(FAQ) & 안심 보장 & 특가 오퍼 ==================== -->
        <div style="padding:45px 30px 50px 30px; text-align:center; background:{theme['sec_bg']};">
            <span class="sp-section-pill" contenteditable="true">자주 묻는 질문 & 교환·환불 안내</span>
            <div contenteditable="true" class="sp-sub-eyebrow">{_clean_step_prefix(s9.get('subtitle', ''))}</div>
            <h2 contenteditable="true" class="sp-title sp-sec-heading" style="margin:0 0 18px 0;">
                {_clean_step_prefix(s9.get('main_title', ''))}
            </h2>

            <div style="text-align:left; max-width:92%; margin:0 auto 22px auto; background:#ffffff; border:1px solid #cbd5e1; border-radius:16px; padding:20px 22px; line-height:1.75;">
                <div contenteditable="true" style="margin-bottom:10px;">
                    <b>Q. {kw_str} 장착 및 호환 기종은 어떻게 확인하나요?</b><br>
                    👉 본 제품은 범용 표준 규격을 준수하여 제작되었으며, 상세페이지 내 실측 가이드를 확인하신 후 사용 환경의 결착 규격을 점검해 주시면 문제없이 장착 가능합니다.
                </div>
                <div contenteditable="true" style="margin-bottom:10px;">
                    <b>Q. 조립 또는 사용 시 별도의 특수 공구가 필요한가요?</b><br>
                    👉 아니요, 누구나 직관적으로 손쉽게 결착 및 조절할 수 있도록 설계되어 별도의 복잡한 도구 없이도 간편하게 세팅하실 수 있습니다.
                </div>
                <div contenteditable="true">
                    <b>Q. 교환·반품 및 초기 불량 보장은 어떻게 되나요?</b><br>
                    👉 {ship_exchange}<br>
                    👉 {_format_step_body(s9.get('body', ''))}
                </div>
            </div>

            <!-- 합리적 가격 책정 최종 배너 -->
            <div style="max-width:92%; margin:0 auto; padding:30px 24px; background:{theme['dark']}; color:#ffffff; border-radius:20px; text-align:center; box-shadow:0 14px 30px rgba(0,0,0,0.16);">
                <div contenteditable="true" style="color:#cbd5e1; font-size:{body_size-1}px; margin-bottom:6px;">{_clean_step_prefix(b.get('price_reason',''))}</div>
                <div style="font-size:{body_size+2}px; color:#94a3b8; text-decoration:line-through;" contenteditable="true">시중 동일 사양 비교가 {b.get('price_origin','6,900원')}</div>
                <div class="sp-title" style="font-size:{title_size}px; color:{theme['accent_text']}; margin-top:6px;" contenteditable="true">온라인 할인가 {b.get('price_sale','3,900원')}</div>
                {brand_footer_html}
            </div>
        </div>

    </div>

    <script>
    (function() {{
        let savedRange = null;
        const menu = document.getElementById('word-context-menu');
        const previewBadge = document.getElementById('wcm-target-preview');
        const sizeInput = document.getElementById('wcm-size');
        const rootContainer = document.getElementById('sp-export-root');

        function selectSingleCharAtPoint(x, y) {{
            let range = null;
            if (document.caretRangeFromPoint) {{
                range = document.caretRangeFromPoint(x, y);
            }} else if (document.caretPositionFromPoint) {{
                const pos = document.caretPositionFromPoint(x, y);
                if (pos) {{
                    range = document.createRange();
                    range.setStart(pos.offsetNode, pos.offset);
                    range.collapse(true);
                }}
            }}
            if (range && range.startContainer && range.startContainer.nodeType === 3) {{
                const textNode = range.startContainer;
                const len = (textNode.textContent || '').length;
                let offset = range.startOffset;
                if (offset >= len && len > 0) offset = len - 1;
                if (offset < len) {{
                    range.setStart(textNode, offset);
                    range.setEnd(textNode, offset + 1);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                    return range.cloneRange();
                }}
            }}
            return null;
        }}

        rootContainer.addEventListener('contextmenu', function(e) {{
            e.preventDefault();
            const sel = window.getSelection();
            if (sel && sel.rangeCount > 0 && !sel.isCollapsed) {{
                savedRange = sel.getRangeAt(0).cloneRange();
            }} else {{
                savedRange = selectSingleCharAtPoint(e.clientX, e.clientY);
            }}

            if (!savedRange || savedRange.collapsed) {{
                previewBadge.textContent = '🔤 글자를 드래그하거나 글자 위에서 우클릭하세요';
            }} else {{
                const txt = savedRange.toString().trim();
                previewBadge.textContent = '🔤 선택: "' + (txt.length > 10 ? txt.slice(0, 10) + '…' : txt) + '" (' + txt.length + '글자)';
                let node = savedRange.startContainer;
                if (node && node.nodeType === 3) node = node.parentElement;
                if (node) {{
                    const curPx = Math.round(parseFloat(window.getComputedStyle(node).fontSize) || 20);
                    sizeInput.value = curPx;
                }}
            }}

            menu.classList.add('open');
            const mw = 350, mh = 250;
            let left = e.clientX + 6;
            let top = e.clientY + 6;
            if (left + mw > window.innerWidth - 10) left = Math.max(10, window.innerWidth - mw - 12);
            if (top + mh > window.innerHeight - 10) top = Math.max(10, e.clientY - mh - 8);
            menu.style.left = left + 'px';
            menu.style.top = top + 'px';
        }});

        window.closeWordMenu = function() {{
            menu.classList.remove('open');
        }};

        document.addEventListener('mousedown', function(e) {{
            if (menu.classList.contains('open') && !menu.contains(e.target)) {{
                menu.classList.remove('open');
            }}
        }});

        function restoreSelection() {{
            if (!savedRange) return null;
            const sel = window.getSelection();
            sel.removeAllRanges();
            sel.addRange(savedRange);
            return savedRange;
        }}

        window.applyCharStyle = function(styleObj) {{
            const r = restoreSelection();
            if (!r || r.collapsed) return;

            let sc = r.startContainer;
            let ec = r.endContainer;
            if (sc === ec && sc.nodeType === 1 && sc.tagName === 'SPAN' && sc.getAttribute('data-char-span') === '1') {{
                Object.assign(sc.style, styleObj);
                return;
            }}
            if (sc === ec && sc.nodeType === 3 && sc.parentElement && sc.parentElement.tagName === 'SPAN'
                && sc.parentElement.getAttribute('data-char-span') === '1'
                && r.startOffset === 0 && r.endOffset === sc.textContent.length) {{
                Object.assign(sc.parentElement.style, styleObj);
                return;
            }}

            const span = document.createElement('span');
            span.setAttribute('data-char-span', '1');
            Object.assign(span.style, styleObj);
            try {{
                span.appendChild(r.extractContents());
                r.insertNode(span);
                const newR = document.createRange();
                newR.selectNodeContents(span);
                savedRange = newR.cloneRange();
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(newR);
            }} catch (err) {{
                console.warn('char style error:', err);
            }}
        }};

        window.stepCharSize = function(delta) {{
            const cur = parseInt(sizeInput.value || '24', 10);
            const next = Math.max(10, Math.min(120, cur + delta));
            sizeInput.value = next;
            window.applyCharStyle({{fontSize: next + 'px'}});
        }};

        window.toggleCharStyle = function(prop, valOn, valOff) {{
            if (!savedRange) return;
            let node = savedRange.startContainer;
            if (node && node.nodeType === 3) node = node.parentElement;
            const cur = node ? window.getComputedStyle(node)[prop] : '';
            const isOn = (prop === 'fontWeight')
                ? (parseInt(cur, 10) >= 700 || cur === 'bold')
                : (cur === valOn);
            const obj = {{}};
            obj[prop] = isOn ? valOff : valOn;
            window.applyCharStyle(obj);
        }};

        window.toggleCharUnderline = function() {{
            if (!savedRange) return;
            let node = savedRange.startContainer;
            if (node && node.nodeType === 3) node = node.parentElement;
            const cur = node ? (node.style.borderBottom || '') : '';
            if (cur && cur !== 'none') {{
                window.applyCharStyle({{borderBottom: 'none', paddingBottom: '0'}});
            }} else {{
                window.applyCharStyle({{borderBottom: '4px solid #f97316', paddingBottom: '2px', fontWeight: '800'}});
            }}
        }};

        window.toggleCharStrike = function() {{
            if (!savedRange) return;
            let node = savedRange.startContainer;
            if (node && node.nodeType === 3) node = node.parentElement;
            const cur = node ? (window.getComputedStyle(node).textDecorationLine || '') : '';
            if (cur.indexOf('line-through') !== -1) {{
                window.applyCharStyle({{textDecoration: 'none'}});
            }} else {{
                window.applyCharStyle({{textDecoration: 'line-through'}});
            }}
        }};

        window.clearCharStyle = function() {{
            if (!savedRange) return;
            let node = savedRange.startContainer;
            if (node && node.nodeType === 3) node = node.parentElement;
            if (node && node.tagName === 'SPAN' && node.getAttribute('data-char-span') === '1') {{
                node.removeAttribute('style');
            }}
        }};

        // --- 2. Advanced HTML5 Drag & Drop Reordering ---
        let draggedItem = null;

        document.addEventListener('dragstart', function(e) {{
            const target = e.target.closest('.sp-draggable');
            if (!target) return;

            const isHandle = e.target.classList.contains('sp-drag-handle');
            const activeEl = document.activeElement;
            if (activeEl && activeEl.isContentEditable && !isHandle) {{
                const sel = window.getSelection();
                if (sel && sel.toString().length > 0) return;
            }}

            draggedItem = target;
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', 'sp-draggable');
            setTimeout(() => {{
                if (draggedItem) draggedItem.classList.add('sp-dragging');
            }}, 0);
        }});

        document.addEventListener('dragover', function(e) {{
            if (!draggedItem) return;
            const target = e.target.closest('.sp-draggable');
            if (!target || target === draggedItem || target.contains(draggedItem) || draggedItem.contains(target)) return;

            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';

            const rect = target.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;
            if (e.clientY < midY) {{
                target.classList.add('sp-drag-over-top');
                target.classList.remove('sp-drag-over-bottom');
            }} else {{
                target.classList.add('sp-drag-over-bottom');
                target.classList.remove('sp-drag-over-top');
            }}
        }});

        document.addEventListener('dragleave', function(e) {{
            const target = e.target.closest('.sp-draggable');
            if (target) {{
                target.classList.remove('sp-drag-over-top', 'sp-drag-over-bottom');
            }}
        }});

        document.addEventListener('drop', function(e) {{
            if (!draggedItem) return;
            const target = e.target.closest('.sp-draggable');
            if (!target || target === draggedItem || target.contains(draggedItem) || draggedItem.contains(target)) return;

            e.preventDefault();
            e.stopPropagation();

            const rect = target.getBoundingClientRect();
            const midY = rect.top + rect.height / 2;

            if (e.clientY < midY) {{
                target.parentNode.insertBefore(draggedItem, target);
            }} else {{
                target.parentNode.insertBefore(draggedItem, target.nextSibling);
            }}

            target.classList.remove('sp-drag-over-top', 'sp-drag-over-bottom');
            showDragToast('✅ 위치가 이동되었습니다. (상단 저장 버튼으로 다운로드 확정)');
        }});

        document.addEventListener('dragend', function(e) {{
            if (draggedItem) {{
                draggedItem.classList.remove('sp-dragging');
                draggedItem = null;
            }}
            document.querySelectorAll('.sp-drag-over-top, .sp-drag-over-bottom').forEach(el => {{
                el.classList.remove('sp-drag-over-top', 'sp-drag-over-bottom');
            }});
        }});

        function showDragToast(msg) {{
            let toast = document.getElementById('sp-drag-toast');
            if (!toast) {{
                toast = document.createElement('div');
                toast.id = 'sp-drag-toast';
                toast.style.cssText = 'position:fixed; bottom:22px; right:22px; background:#0f172a; color:#38bdf8; border:1px solid #0284c7; padding:9px 18px; border-radius:10px; font-weight:800; font-size:12.5px; z-index:999999; box-shadow:0 10px 28px rgba(0,0,0,0.45); transition:opacity 0.25s; opacity:0;';
                document.body.appendChild(toast);
            }}
            toast.textContent = msg;
            toast.style.opacity = '1';
            setTimeout(() => {{ toast.style.opacity = '0'; }}, 2000);
        }}

        window.downloadEditedPageHtml = function() {{
            const clone = rootContainer.cloneNode(true);
            clone.querySelectorAll('[contenteditable]').forEach(el => el.removeAttribute('contenteditable'));
            clone.querySelectorAll('.sp-drag-handle').forEach(el => el.remove());
            clone.querySelectorAll('.sp-draggable').forEach(el => {{
                el.removeAttribute('draggable');
                el.classList.remove('sp-draggable', 'sp-dragging', 'sp-drag-over-top', 'sp-drag-over-bottom');
            }});
            const fullDoc = '<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8"><title>상세페이지</title><style>' +
                document.querySelector('style').innerHTML + '</style></head><body style="margin:0;padding:0;">' +
                clone.outerHTML + '</body></html>';
            const blob = new Blob([fullDoc], {{type: 'text/html;charset=utf-8'}});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = '완성_상세페이지.html';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(url), 3000);
        }};
    }})();
    </script>
    """
    return html


# =====================================================================
# [NEW: 포토샵(PSD) / 일러스트레이터(SVG) / 레이어 분리 패키지 ZIP 생성기]
# =====================================================================
def build_photoshop_psd_bytes(pil_img):
    """
    외부 C 라이브러리 없이 순수 파이썬으로 Adobe Photoshop 호환 RGB 8-bit 비압축 `.psd` 바이너리를 생성합니다.
    포토샵에서 즉시 열리며 고화질 캔버스 편집이 가능합니다.
    """
    if pil_img is None:
        pil_img = Image.new("RGB", (1000, 1000), (255, 255, 255))
    rgb = pil_img.convert("RGB")
    w, h = rgb.size
    import numpy as np
    arr = np.array(rgb, dtype=np.uint8)

    out = io.BytesIO()
    # 1. File Header (26 bytes): Signature '8BPS', Version 1, 6 reserved, 3 channels (RGB), height, width, depth 8, mode 3 (RGB)
    out.write(struct.pack(">4sH6sHIIHH", b"8BPS", 1, b"\x00" * 6, 3, h, w, 8, 3))
    # 2. Color Mode Data Section (4 bytes: length 0)
    out.write(struct.pack(">I", 0))
    # 3. Image Resources Section (4 bytes: length 0)
    out.write(struct.pack(">I", 0))
    # 4. Layer and Mask Information Section (4 bytes: length 0 -> merged canvas ready)
    out.write(struct.pack(">I", 0))
    # 5. Image Data Section: Compression 0 (Raw planar R, G, B)
    out.write(struct.pack(">H", 0))
    out.write(arr[:, :, 0].tobytes())
    out.write(arr[:, :, 1].tobytes())
    out.write(arr[:, :, 2].tobytes())
    return out.getvalue()


def build_illustrator_svg_layer_file(pdata):
    """
    Adobe Illustrator 및 피그마(Figma), 포토샵에서 레이어별로 분리해 글자와 이미지를 바로 수정할 수 있는
    멀티 레이어(`<g id="Layer_...">`) 벡터 `.svg` 파일을 생성합니다.
    """
    def_data = get_default_project_data()
    b = pdata.get("page_blocks", def_data["page_blocks"])
    plat_spec = get_platform_spec(pdata.get("target_platform"))
    detail_w = int(plat_spec.get("detail_width", 860))
    canvas_h = 2600

    theme_key = pdata.get("theme_color", "")
    theme = BRAND_THEMES.get(theme_key, list(BRAND_THEMES.values())[0])
    primary_c = theme["primary"]
    light_bg = theme["light_bg"]
    dark_c = theme["dark"]

    nine_steps = pdata.get("nine_steps") or get_default_9steps(pdata.get("manual_size", ""))
    s1, s2, s3, s4, s5, s6, s7, s8, s9 = nine_steps[:9]

    # 투명 누끼 또는 완성 이미지 데이터 URL
    cutout_b64 = pdata.get("fg_cutout_b64") or pdata.get("photo_ai_report", {}).get("fg_cutout_b64") or pdata.get("edited_img_b64") or pdata.get("orig_img_b64") or ""

    svg_lines = [
        f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{detail_w}" height="{canvas_h}" viewBox="0 0 {detail_w} {canvas_h}">',
        f'  <!-- Layer 1: 배경 레이어 (Illustrator/Photoshop에서 개별 선택 및 색상 변경 가능) -->',
        f'  <g id="Layer_1_Background" data-name="01_배경_레이어">',
        f'    <rect x="0" y="0" width="{detail_w}" height="{canvas_h}" fill="#FFFFFF" />',
        f'    <rect x="0" y="0" width="{detail_w}" height="820" fill="{light_bg}" />',
        f'    <rect x="40" y="860" width="{detail_w-80}" height="340" rx="20" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="2" />',
        f'    <rect x="40" y="1240" width="{detail_w-80}" height="360" rx="20" fill="{light_bg}" stroke="{primary_c}" stroke-width="2" />',
        f'    <rect x="40" y="2280" width="{detail_w-80}" height="240" rx="24" fill="{dark_c}" />',
        f'  </g>',
        f'  <!-- Layer 2: 제품 누끼 이미지 레이어 (단독 이동·크기 조절 가능) -->',
        f'  <g id="Layer_2_Product_Cutout_Image" data-name="02_제품_누끼_이미지_레이어">',
    ]
    if cutout_b64:
        img_w = min(560, detail_w - 120)
        img_x = (detail_w - img_w) // 2
        svg_lines.append(f'    <image x="{img_x}" y="230" width="{img_w}" height="{img_w}" xlink:href="{cutout_b64}" href="{cutout_b64}" />')
    svg_lines.extend([
        f'  </g>',
        f'  <!-- Layer 3: 편집 가능한 텍스트 레이어 (일러스트레이터 T 도구로 한 글자씩 직접 수정 가능) -->',
        f'  <g id="Layer_3_Editable_Text" data-name="03_편집가능_텍스트_레이어" font-family="Pretendard, Malgun Gothic, sans-serif">',
        f'    <text x="{detail_w//2}" y="75" font-size="16" font-weight="800" fill="{primary_c}" text-anchor="middle">{escape(_clean_step_prefix(b.get("hook_badge", "")))}</text>',
        f'    <text x="{detail_w//2}" y="115" font-size="22" font-weight="700" fill="{primary_c}" text-anchor="middle">{escape(_clean_step_prefix(s1.get("subtitle", "")))}</text>',
        f'    <text x="{detail_w//2}" y="165" font-size="38" font-weight="900" fill="#0F172A" text-anchor="middle">{escape(_clean_step_prefix(s1.get("main_title", "")))}</text>',
        f'    <text x="{detail_w//2}" y="205" font-size="18" font-weight="700" fill="#334155" text-anchor="middle">{escape(_clean_step_prefix(b.get("hook_sub", "")))}</text>',
        f'    <text x="{detail_w//2}" y="920" font-size="20" font-weight="800" fill="{primary_c}" text-anchor="middle">{escape(_clean_step_prefix(s2.get("subtitle", "")))}</text>',
        f'    <text x="{detail_w//2}" y="965" font-size="32" font-weight="900" fill="#0F172A" text-anchor="middle">{escape(_clean_step_prefix(s2.get("main_title", "")))}</text>',
        f'    <text x="{detail_w//2}" y="1030" font-size="18" font-weight="600" fill="#334155" text-anchor="middle">{escape(_clean_step_prefix(s2.get("body", "").replace("<>", " / ")))}</text>',
        f'    <text x="{detail_w//2}" y="1305" font-size="20" font-weight="800" fill="{primary_c}" text-anchor="middle">{escape(_clean_step_prefix(s3.get("subtitle", "")))}</text>',
        f'    <text x="{detail_w//2}" y="1350" font-size="30" font-weight="900" fill="#0F172A" text-anchor="middle">{escape(_clean_step_prefix(s3.get("main_title", "")))}</text>',
        f'    <text x="{detail_w//2}" y="1420" font-size="20" font-weight="800" fill="{primary_c}" text-anchor="middle">1) {escape(_clean_step_prefix(b.get("point1_title", "")))} — {escape(_clean_step_prefix(b.get("point1_desc", "")))}</text>',
        f'    <text x="{detail_w//2}" y="1465" font-size="20" font-weight="800" fill="{primary_c}" text-anchor="middle">2) {escape(_clean_step_prefix(b.get("point2_title", "")))} — {escape(_clean_step_prefix(b.get("point2_desc", "")))}</text>',
        f'    <text x="{detail_w//2}" y="1510" font-size="20" font-weight="800" fill="{primary_c}" text-anchor="middle">3) {escape(_clean_step_prefix(b.get("point3_title", "")))} — {escape(_clean_step_prefix(b.get("point3_desc", "")))}</text>',
        f'    <text x="{detail_w//2}" y="1680" font-size="28" font-weight="900" fill="#0F172A" text-anchor="middle">{escape(_clean_step_prefix(s4.get("main_title", "")))}</text>',
        f'    <text x="{detail_w//2}" y="1730" font-size="17" font-weight="600" fill="#334155" text-anchor="middle">{escape(_clean_step_prefix(s4.get("body", "").replace("<>", " / ")))}</text>',
        f'    <text x="{detail_w//2}" y="1840" font-size="28" font-weight="900" fill="{primary_c}" text-anchor="middle">{escape(_clean_step_prefix(s5.get("main_title", "")))}</text>',
        f'    <text x="{detail_w//2}" y="1890" font-size="17" font-weight="700" fill="#0F172A" text-anchor="middle">{escape(_clean_step_prefix(pdata.get("manual_size", "")))}</text>',
        f'    <text x="{detail_w//2}" y="2000" font-size="26" font-weight="900" fill="#0F172A" text-anchor="middle">{escape(_clean_step_prefix(s6.get("main_title", "")))}</text>',
        f'    <text x="{detail_w//2}" y="2120" font-size="24" font-weight="800" fill="#0F172A" text-anchor="middle">{escape(_clean_step_prefix(s7.get("main_title", "")))}</text>',
        f'    <text x="{detail_w//2}" y="2355" font-size="18" font-weight="600" fill="#CBD5E1" text-anchor="middle">{escape(_clean_step_prefix(b.get("price_reason", "")))}</text>',
        f'    <text x="{detail_w//2}" y="2395" font-size="20" font-weight="700" fill="#94A3B8" text-anchor="middle">비교 시중가 {escape(b.get("price_origin", "6,900원"))}</text>',
        f'    <text x="{detail_w//2}" y="2455" font-size="42" font-weight="900" fill="#FACC15" text-anchor="middle">온라인 할인가 {escape(b.get("price_sale", "3,900원"))}</text>',
        f'  </g>',
        f'</svg>'
    ])
    return "\n".join(svg_lines).encode("utf-8")


def create_design_tool_package_zip(pdata):
    """
    [포토샵(PSD) / 일러스트레이터(SVG) 호환 다중 저장소 패키지 ZIP]
    완성된 상세페이지를 포토샵이나 일러스트레이터에서 열어 이미지와 글자를 자유롭게 재편집할 수 있도록:
    1) `01_포토샵_전용_원본캔버스.psd` (Adobe Photoshop RGB 8-bit 호환 파일)
    2) `02_일러스트레이터_레이어분리_원본.svg` (배경 / 투명누끼 / 편집가능 텍스트 `<text>` 3단 레이어 분리)
    3) `03_개별_이미지_레이어_에셋/` (`01_투명배경_단독누끼.png`, `02_스튜디오_완성썸네일.png`, `03_원본사진.png`, `04_다각도_보정컷_...`)
    4) `04_분리된_텍스트_카피_원고.txt` & `05_구조화_데이터.json`
    5) `06_쇼핑몰_즉시업로드용_완성_상세페이지.html`
    을 하나의 ZIP 패키지로 묶어 반환합니다.
    """
    plat_spec = get_platform_spec(pdata.get("target_platform"))
    tw, th = plat_spec.get("thumb_size", (1000, 1000))
    detail_w = plat_spec.get("detail_width", 860)

    ed_pil = base64_url_to_pil(pdata.get("edited_img_b64")) or base64_url_to_pil(pdata.get("orig_img_b64"))
    if ed_pil is None:
        ed_pil = Image.new("RGB", (tw, th), (255, 255, 255))

    fg_b64 = pdata.get("fg_cutout_b64") or pdata.get("photo_ai_report", {}).get("fg_cutout_b64")
    fg_pil = base64_url_to_pil(fg_b64) if fg_b64 else ed_pil

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1) 포토샵(.psd) 파일
        psd_bytes = build_photoshop_psd_bytes(ed_pil.resize((tw, th), Image.Resampling.LANCZOS))
        zf.writestr(f"01_포토샵_편집용_원본캔버스_{tw}x{th}.psd", psd_bytes)

        # 2) 일러스트레이터(.svg) 레이어 분리 벡터 파일
        svg_bytes = build_illustrator_svg_layer_file(pdata)
        zf.writestr(f"02_일러스트레이터_레이어분리_편집본_{detail_w}px.svg", svg_bytes)

        # 3) 개별 고화질 PNG 레이어 에셋
        if fg_pil is not None:
            b_fg = io.BytesIO()
            fg_pil.save(b_fg, format="PNG")
            zf.writestr("03_개별_이미지_레이어_에셋/01_투명배경_제품단독_누끼레이어.png", b_fg.getvalue())

        b_ed = io.BytesIO()
        ed_pil.resize((tw, th), Image.Resampling.LANCZOS).save(b_ed, format="PNG")
        zf.writestr(f"03_개별_이미지_레이어_에셋/02_스튜디오_완성_대표썸네일_{tw}x{th}.png", b_ed.getvalue())

        bg_layer = Image.new("RGB", (tw, th), (255, 255, 255))
        b_bg = io.BytesIO()
        bg_layer.save(b_bg, format="PNG")
        zf.writestr(f"03_개별_이미지_레이어_에셋/03_순백색_배경레이어_{tw}x{th}.png", b_bg.getvalue())

        for idx_m, m_item in enumerate(pdata.get("multi_images", [])):
            mpil = base64_url_to_pil(m_item.get("polished_b64") or m_item.get("b64"))
            if mpil is not None:
                bm = io.BytesIO()
                mpil.save(bm, format="PNG")
                zf.writestr(f"03_개별_이미지_레이어_에셋/04_다각도_후가공컷_{idx_m+1}.png", bm.getvalue())

        # 4) 섹션별 분리된 텍스트 원고 (.txt) - 포토샵/일러스트 복사-붙여넣기 최적화
        b_blocks = pdata.get("page_blocks", {})
        nine_steps = pdata.get("nine_steps") or get_default_9steps(pdata.get("manual_size", ""))
        txt_lines = [
            "=====================================================================",
            f"[{pdata.get('title', '제품 상세페이지')}] 포토샵(PSD) · 일러스트레이터(SVG) 레이어 작업용 분리 원고",
            f"- 설정된 가로 사이즈 규격: 가로 {detail_w}px / 대표썸네일 {tw}x{th}px",
            f"- 적합 플랫폼: {plat_spec.get('recommended_platforms', '')}",
            "=====================================================================\n",
            f"[메인 상단 배지] {_clean_step_prefix(b_blocks.get('hook_badge', ''))}",
            f"[메인 헤드카피] {_clean_step_prefix(b_blocks.get('hook_title', ''))}",
            f"[해시태그 서브] {_clean_step_prefix(b_blocks.get('hook_sub', ''))}",
            f"[핵심 포인트 1] {_clean_step_prefix(b_blocks.get('point1_title', ''))} : {_clean_step_prefix(b_blocks.get('point1_desc', ''))}",
            f"[핵심 포인트 2] {_clean_step_prefix(b_blocks.get('point2_title', ''))} : {_clean_step_prefix(b_blocks.get('point2_desc', ''))}",
            f"[핵심 포인트 3] {_clean_step_prefix(b_blocks.get('point3_title', ''))} : {_clean_step_prefix(b_blocks.get('point3_desc', ''))}",
            f"[가격 배너] 시중 비교가 {b_blocks.get('price_origin', '')} -> 할인가 {b_blocks.get('price_sale', '')} ({b_blocks.get('price_reason', '')})\n",
            "---------------------------------------------------------------------",
            "[섹션별 상세 스토리 원고 (번호 표시 제거 완료)]",
            "---------------------------------------------------------------------"
        ]
        for idx_s, st_item in enumerate(nine_steps[:9], 1):
            txt_lines.append(f"\n[{idx_s}번째 섹션 - {st_item.get('role', '')}]")
            txt_lines.append(f"• 작은 부제목: {_clean_step_prefix(st_item.get('subtitle', ''))}")
            txt_lines.append(f"• 핵심 큰제목: {_clean_step_prefix(st_item.get('main_title', ''))}")
            txt_lines.append(f"• 본문 카피: {_clean_step_prefix(st_item.get('body', '')).replace('<>', ' ')}")

        txt_lines.append("\n---------------------------------------------------------------------")
        txt_lines.append("[상세 스펙 표 데이터]")
        for sp in pdata.get("product_specs", []):
            txt_lines.append(f"• {sp.get('항목') or sp.get('label')}: {sp.get('내용') or sp.get('value')}")

        zf.writestr("04_포토샵_일러스트_복붙용_분리_텍스트원고.txt", "\n".join(txt_lines).encode("utf-8"))

        # 5) 완성된 상세페이지 HTML
        final_html = pdata.get("draft_html") or render_structured_detail_html(pdata)
        zf.writestr(f"05_즉시업로드용_완성_상세페이지_{detail_w}px.html", final_html.encode("utf-8"))

    buf.seek(0)
    return buf.getvalue()
