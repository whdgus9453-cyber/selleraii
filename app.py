import copy
import io
import json
import socket
import base64
from datetime import datetime
from PIL import Image
import qrcode
import streamlit as st
from tunnel_manager import get_current_tunnel_url, start_tunnel_background

# =====================================================================
# [4대 코어 모듈 분리 임포트]
# =====================================================================
from core_storage import (
    init_storage,
    save_config,
    get_default_9steps,
    get_default_project_data,
    list_projects,
    save_project,
    duplicate_project,
    delete_project,
    create_hub_backup_zip,
    restore_hub_backup_zip,
)
from core_api import (
    check_single_key_live,
    saved_key_badge,
    detect_naver_key_mode,
    make_ncp_iam_signature_headers,
    fetch_shopping_reference,
    analyze_custom_url,
    generate_marketer_strategy_report,
    generate_category_spec_questions,
    run_director_chat_turn,
    generate_9step_and_6agent_plan,
)
from core_media import (
    ECOMMERCE_10_PLATFORMS,
    COMPETITOR_10_MOODS,
    get_platform_spec,
    render_platform_thumbnail_bytes,
    process_photo_with_full_report,
    pil_to_base64_url,
    base64_url_to_pil,
    file_to_media_data_url,
    render_free_cutout_shortcuts,
    is_already_cutout_png,
    quick_auto_cutout_pil,
    create_procedural_studio_background,
    apply_color_harmonization,
    composite_photocraft_layers,
    render_html5_eraser_canvas,
    _erase_edge_shadow_hsv,
    separate_physical_shadow_lab,
    defringe_and_color_decontamination,
)
import streamlit.components.v1 as components
from core_builder import (
    BRAND_THEMES,
    DEFAULT_SHIPPING_INFO,
    DEFAULT_PRODUCT_SPECS,
    render_structured_detail_html,
    create_design_tool_package_zip,
)
from ui_styles import MARKETER_FONTS, apply_ui_styles, render_live_badge

# =====================================================================
# [0. 페이지 설정 & 반응형 스타일]
# =====================================================================
st.set_page_config(
    page_title="SellerAI Studio",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)
apply_ui_styles()
config = init_storage()


def inject_photoshop_shortcuts():
    """포토샵/일러스트레이터 키보드 단축키를 Streamlit 창에 안전하게 바인딩하고 removeChild 에러를 방지합니다."""
    if st.session_state.get("__shortcuts_injected"):
        return
    st.session_state["__shortcuts_injected"] = True

    shortcut_js = """
    <script>
    (function() {
      // 1. Streamlit React의 removeChild 에러 팝업 원천 차단
      const suppressRemoveChild = function(e) {
        if (e && e.message && e.message.includes('removeChild')) {
          e.stopImmediatePropagation();
          e.preventDefault();
          return true;
        }
      };
      window.addEventListener('error', suppressRemoveChild, true);
      try {
        if (window.parent && window.parent !== window) {
          window.parent.addEventListener('error', suppressRemoveChild, true);
        }
      } catch(err) {}

      // 2. 단축키 바인딩
      let doc = null;
      try { doc = window.parent.document; } catch(e) { doc = document; }
      if (!doc || doc.__photocraft_shortcuts_bound) return;
      doc.__photocraft_shortcuts_bound = true;

      doc.addEventListener('keydown', function(e) {
        const activeEl = doc.activeElement;
        const isInput = activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA' || activeEl.isContentEditable);

        // Ctrl + S -> 저장
        if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
          e.preventDefault();
          const buttons = Array.from(doc.querySelectorAll('button'));
          const saveBtn = buttons.find(b => b.innerText && (b.innerText.includes('스튜디오 완성본 저장') || b.innerText.includes('프로젝트 저장') || b.innerText.includes('저장')));
          if (saveBtn) {
            saveBtn.click();
          }
          return;
        }

        if (isInput) return;

        // 1, 2, 3, 4 -> 단계 이동
        if (['1', '2', '3', '4'].includes(e.key)) {
          const stepIdx = e.key;
          const stepBtns = Array.from(doc.querySelectorAll('button')).filter(b => b.innerText && b.innerText.includes(stepIdx + '.'));
          if (stepBtns.length > 0) {
            e.preventDefault();
            stepBtns[0].click();
          }
        }
      });
    })();
    </script>
    """
    try:
        components.html(shortcut_js, height=0, width=0)
    except Exception:
        pass

inject_photoshop_shortcuts()


@st.cache_data(ttl=3600)
def _get_access_urls():
    lan_ip = "127.0.0.1"
    tailscale_ip = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.2)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("100."):
                tailscale_ip = ip
    except Exception:
        pass
    return lan_ip, tailscale_ip


def _make_qr_b64(url: str) -> str:
    if not url:
        return ""
    try:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=4,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode()}"
    except Exception:
        return ""


def _render_page(data):
    return render_structured_detail_html(data, studio_cfg=config)


def _record_key_status(key_type, code, msg):
    config.setdefault("key_status", {})[key_type] = {
        "code": code,
        "msg": msg,
        "checked_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def _platform_for_width(width):
    width = int(width or 860)
    for key, spec in ECOMMERCE_10_PLATFORMS.items():
        if int(spec.get("detail_width", 0)) == width:
            return key
    return list(ECOMMERCE_10_PLATFORMS.keys())[0]


def sync_dual_control(label, min_v, max_v, default_v, step=None, base_key="ctrl", help_text=None, fmt=None):
    """
    Renders a slider with a numeric input directly beneath it.
    Both are bi-directionally synchronized in st.session_state.
    Dragging the slider or typing directly in the numeric input updates instantly.
    """
    val_key = f"val_{base_key}"
    sl_key = f"sl_{base_key}"
    num_key = f"num_{base_key}"

    is_float = isinstance(min_v, float) or isinstance(max_v, float) or isinstance(default_v, float) or (step is not None and isinstance(step, float))
    target_type = float if is_float else int
    min_val = target_type(min_v)
    max_val = target_type(max_v)
    step_val = target_type(step) if step is not None else (0.05 if is_float else 1)

    if val_key not in st.session_state:
        st.session_state[val_key] = target_type(default_v)
        st.session_state[sl_key] = st.session_state[val_key]
        st.session_state[num_key] = st.session_state[val_key]

    def _on_slider_change():
        st.session_state[val_key] = st.session_state[sl_key]
        st.session_state[num_key] = st.session_state[sl_key]

    def _on_num_change():
        st.session_state[val_key] = st.session_state[num_key]
        st.session_state[sl_key] = st.session_state[num_key]

    st.slider(
        label,
        min_value=min_val,
        max_value=max_val,
        step=step_val,
        key=sl_key,
        help=help_text,
        on_change=_on_slider_change
    )

    st.number_input(
        f"↳ 직접 입력 ({label})",
        min_value=min_val,
        max_value=max_val,
        step=step_val,
        format=fmt if fmt else ("%.2f" if is_float else "%d"),
        key=num_key,
        on_change=_on_num_change,
        help=f"{label} 수치를 키보드로 직접 입력할 수 있습니다."
    )

    return st.session_state[val_key]


def set_dual_control_value(base_key, new_val):
    """Updates synced dual control state programmatically (e.g. from 1-click scene presets)."""
    val_key = f"val_{base_key}"
    sl_key = f"sl_{base_key}"
    num_key = f"num_{base_key}"
    st.session_state[val_key] = new_val
    st.session_state[sl_key] = new_val
    st.session_state[num_key] = new_val



# 세션 상태 초기화
if "active_page" not in st.session_state:
    st.session_state.active_page = "studio"
if "active_step" not in st.session_state:
    st.session_state.active_step = 1

# =====================================================================
# [1. 프로젝트 데이터 세션 동기화]
# =====================================================================
if "current_proj_id" not in st.session_state:
    existing = list_projects()
    if existing:
        st.session_state.current_proj_id = existing[0][0]
        st.session_state.proj_data = existing[0][1]
    else:
        new_id = f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.current_proj_id = new_id
        st.session_state.proj_data = get_default_project_data()
        save_project(new_id, st.session_state.proj_data)
else:
    for p_id, p_item in list_projects():
        if p_id == st.session_state.current_proj_id:
            if p_item.get("updated_at") != st.session_state.proj_data.get("updated_at"):
                st.session_state.proj_data = p_item
            break

pdata = st.session_state.proj_data
pid = st.session_state.current_proj_id
def_proj = get_default_project_data()
for k, v in def_proj.items():
    if k not in pdata:
        pdata[k] = copy.deepcopy(v)

# 자동 보정: 제품 키워드가 설정되어 있으나 예전 템플릿(나사/드라이버) 문구가 남아있는 경우 키워드에 맞게 자동 갱신
kw_chk = (pdata.get("keyword") or "").strip()
hook_chk = pdata.get("page_blocks", {}).get("hook_title", "")
step1_chk = (pdata.get("nine_steps") or [{}])[0].get("main_title", "")
if kw_chk and ("나사" in hook_chk or "드라이버" in hook_chk or "드라이버" in step1_chk) and ("드라이버" not in kw_chk and "나사" not in kw_chk):
    msize_chk = pdata.get("manual_size", "")
    pdata["nine_steps"] = get_default_9steps(msize=msize_chk, kw=kw_chk)
    rep_chk = generate_marketer_strategy_report([], [], pdata)
    pdata.setdefault("page_blocks", {}).update(rep_chk.get("recommended_blocks", {}))
    pdata["draft_html"] = _render_page(pdata)
    save_project(pid, pdata)

if pdata.get("orig_img_b64") and not pdata.get("multi_images"):
    pdata["multi_images"] = [{
        "name": "대표 제품 사진",
        "angle_label": "전면 디테일",
        "b64": pdata["orig_img_b64"],
        "polished_b64": pdata.get("edited_img_b64") or pdata["orig_img_b64"]
    }]

plat_list = list(ECOMMERCE_10_PLATFORMS.keys())

# =====================================================================
# [2. 사이드바: 메뉴 전환 & 프로젝트 관리]
# =====================================================================
with st.sidebar:
    st.markdown("### ⚡ SellerAI Studio")

    # 1) 최상단 메인 메뉴 전환 (스튜디오 vs API 환경설정)
    menu_choice = st.radio(
        "📌 메인 메뉴",
        ["⚡ 4단계 작업 스튜디오", "🔑 API 연동 및 환경설정"],
        index=0 if st.session_state.active_page == "studio" else 1,
        key="main_menu_choice"
    )
    st.session_state.active_page = "studio" if "작업 스튜디오" in menu_choice else "api_settings"

    st.markdown("---")
    _lan_ip, _ts_ip = _get_access_urls()
    _tunnel_url = get_current_tunnel_url()
    if not _tunnel_url:
        _tunnel_url = start_tunnel_background(8501)

    _target_mobile_url = _tunnel_url or f"http://{_lan_ip}:8501"
    _qr_img = _make_qr_b64(_target_mobile_url)

    st.markdown(f"""
    <div class="dark-safe-card" style="padding:12px; font-size:0.84em; margin-bottom:8px; border:1px solid #3b82f6; border-radius:10px; background:#0f172a;">
        <div style="font-weight:700; color:#38bdf8; margin-bottom:6px; display:flex; align-items:center; justify-content:space-between;">
            <span>📱 갤럭시 모바일 즉시 연결</span>
            <span style="font-size:0.75em; background:#1e293b; color:#10b981; padding:2px 6px; border-radius:4px; border:1px solid #10b981;">LTE/5G 지원</span>
        </div>
        <div style="text-align:center; padding:8px 0;">
            {"<img src='" + _qr_img + "' style='width:145px; height:145px; border-radius:8px; border:2px solid #ffffff; background:white; padding:4px;' alt='Mobile QR'>" if _qr_img else ""}
            <div style="font-size:0.76em; color:#94a3b8; margin-top:5px;">
                📸 갤럭시 기본 카메라로 스캔하세요!
            </div>
        </div>
        <div style="font-size:0.80em; color:#cbd5e1; border-top:1px solid #334155; padding-top:6px; margin-top:4px;">
            • <b>모바일 링크</b>: <a href="{_target_mobile_url}" target="_blank" style="color:#60a5fa; word-break:break-all;">{_target_mobile_url}</a><br>
            • <b>로컬 Wi-Fi</b>: <a href="http://{_lan_ip}:8501" target="_blank" style="color:#94a3b8;">http://{_lan_ip}:8501</a><br>
            • <b>PC 브라우저</b>: <a href="http://localhost:8501" target="_blank" style="color:#94a3b8;">http://localhost:8501</a>
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("⌨️ 포토샵·일러스트 단축키 가이드", expanded=False):
        st.markdown("""
        <div style="font-size:0.80em; line-height:1.6; color:#94a3b8;">
          • <b style="color:#38bdf8;">Ctrl + S</b> : 프로젝트 & 완성본 즉시 저장<br>
          • <b style="color:#38bdf8;">1 ~ 4</b> : 1단계 ~ 4단계 탭 전환<br>
          • <b style="color:#38bdf8;">E</b> : 인앱 지우개 모드<br>
          • <b style="color:#38bdf8;">B</b> : 원본 복구 브러시 모드<br>
          • <b style="color:#38bdf8;">[ / ]</b> : 브러시 크기 줄이기 / 키우기<br>
          • <b style="color:#38bdf8;">Ctrl + Z</b> : 실행 취소 (Undo)<br>
          • <b style="color:#38bdf8;">+ / -</b> : 캔버스 줌인 / 줌아웃<br>
          • <b style="color:#38bdf8;">0</b> : 100% 원본 배율 맞춤
        </div>
        """, unsafe_allow_html=True)

    if st.button("✨ + 새 제품 기획 시작", use_container_width=True, type="primary"):
        new_id = f"proj_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        st.session_state.current_proj_id = new_id
        st.session_state.proj_data = get_default_project_data()
        save_project(new_id, st.session_state.proj_data)
        st.session_state.active_step = 1
        st.session_state.active_page = "studio"
        st.rerun()

    projs = list_projects()
    st.caption(f"📂 내 프로젝트 목록 ({len(projs)}개)")
    for p_id, p_item in projs:
        is_cur = (p_id == st.session_state.current_proj_id)
        lbl = f"{'👉 ' if is_cur else ''}{p_item.get('title','새 제품')[:14]}"
        c_p, c_c, c_d = st.columns([6, 2, 2])
        if c_p.button(lbl, key=f"sel_{p_id}", use_container_width=True, type="primary" if is_cur else "secondary"):
            st.session_state.current_proj_id = p_id
            st.session_state.proj_data = p_item
            st.rerun()
        if c_c.button("📋", key=f"cp_{p_id}", help="복제"):
            new_pid, new_pdata = duplicate_project(p_id)
            if new_pid:
                st.session_state.current_proj_id = new_pid
                st.session_state.proj_data = new_pdata
                st.rerun()
        if c_d.button("🗑️", key=f"d_{p_id}", help="삭제"):
            delete_project(p_id)
            rem = list_projects()
            if rem:
                st.session_state.current_proj_id, st.session_state.proj_data = rem[0]
            st.rerun()

    st.markdown("---")
    if st.session_state.active_page == "studio":
        if st.button("⚙️ API 키 설정 페이지 열기", use_container_width=True):
            st.session_state.active_page = "api_settings"
            st.rerun()


# =====================================================================
# [3. 독립 전용 페이지: 🔑 API 연동 및 환경설정]
# =====================================================================
def render_settings_page():
    c_hdr1, c_hdr2 = st.columns([7, 3])
    with c_hdr1:
        st.markdown("## 🔑 API 연동 및 환경설정 관리 센터")
        st.caption("외부 AI(Gemini, 네이버 클라우드, Photoroom, Clipdrop 등) 키 등록과 연결 상태를 한눈에 관리합니다.")
    with c_hdr2:
        if st.button("⬅️ ⚡ 4단계 작업 스튜디오로 돌아가기", type="primary", use_container_width=True):
            st.session_state.active_page = "studio"
            st.rerun()

    tab_api, tab_brand, tab_image, tab_data = st.tabs([
        "🔑 10종 AI 멀티 API 연동",
        "🏢 스토어 & 브랜드 설정",
        "🖼️ 이미지 & 출력 규격",
        "💾 전체 백업 & 데이터 복원",
    ])

    with tab_api:
        st.markdown("##### 🤖 이커머스 전문 AI API 키 목록")
        st.caption("키를 입력한 후 [💾 모든 API 키 일괄 저장] 또는 [⚡ 개별 연결 테스트]를 눌러 상태를 검증하세요.")

        api_definitions = [
            ("gemini", "1. Google Gemini API (카피라이팅 & 마케팅 회의 필수)", "gemini_key", None, "https://aistudio.google.com/app/apikey"),
            ("naver", "2. 네이버 클라우드 플랫폼 (NCP IAM Access / Secret) & 오픈API", "naver_id", "naver_secret", "https://www.ncloud.com"),
            ("photoroom", "3. Photoroom API (상업용 상품 누끼 1순위)", "photoroom_key", None, "https://www.photoroom.com/api"),
            ("clipdrop", "4. Clipdrop API (배경 합성 AI)", "clipdrop_key", None, "https://clipdrop.co/apis"),
            ("fal", "5. Fal.ai API (스튜디오 조명 연출)", "fal_key", None, "https://fal.ai"),
            ("bria", "6. Bria.ai API (상업용 스튜디오 AI)", "bria_key", None, "https://bria.ai"),
            ("drap_art", "7. DrapArt (드랩아트 - 이커머스 패션/배경 AI)", "drap_art_key", None, "https://www.drapart.com"),
            ("flair_ai", "8. Flair.ai (플레어 - 상품 3D 연출 스튜디오)", "flair_ai_key", None, "https://flair.ai"),
            ("hookle", "9. Hookle (후커블 - SNS 마케팅 자동화)", "hookle_key", None, "https://hookle.net"),
            ("removebg", "10. Remove.bg API (배경 제거 2순위)", "removebg_key", None, "https://www.remove.bg/api"),
        ]

        for key_id, label, field, field2, link_url in api_definitions:
            with st.container():
                st.markdown(f"**{label}** &nbsp; <a href='{link_url}' target='_blank' style='font-size:0.82em; color:#38bdf8;'>[키 발급 사이트 이동 ↗]</a>", unsafe_allow_html=True)
                c_k1, c_k2, c_btn = st.columns([4.5, 4.5, 2.5] if field2 else [7, 0.1, 2.5])
                with c_k1:
                    config[field] = st.text_input(label, value=config.get(field, ""), type="password", key=f"cfg_{field}", label_visibility="collapsed", placeholder="API Key 입력")
                if field2:
                    with c_k2:
                        config[field2] = st.text_input("Secret", value=config.get(field2, ""), type="password", key=f"cfg_{field2}", label_visibility="collapsed", placeholder="Secret Key 입력")
                with c_btn:
                    if st.button("⚡ 연결 테스트", key=f"test_{key_id}", use_container_width=True):
                        code, msg = check_single_key_live(key_id, config.get(field, ""), config.get(field2, "") if field2 else "")
                        _record_key_status(key_id, code, msg)
                        save_config(config)
                        st.rerun()

                filled = bool((config.get(field) or "").strip()) and (not field2 or bool((config.get(field2) or "").strip()))
                code, msg = saved_key_badge(config, key_id, filled)
                render_live_badge(code, msg)

        st.markdown("---")
        c_save, c_all, c_back = st.columns([4, 4, 3])
        if c_save.button("💾 모든 API 키 일괄 저장", type="primary", use_container_width=True):
            save_config(config)
            st.success("✅ 모든 API 키 설정이 seller_hub_data/config.json 에 안전하게 저장되었습니다!")
        if c_all.button("🚀 전체 API 일괄 연결 테스트", use_container_width=True):
            with st.spinner("등록된 모든 API 키를 테스트 중입니다..."):
                for key_id, _label, field, field2, _ in api_definitions:
                    code, msg = check_single_key_live(key_id, config.get(field, ""), config.get(field2, "") if field2 else "")
                    _record_key_status(key_id, code, msg)
                save_config(config)
                st.success("✅ 전체 API 검증이 완료되었습니다!")
                st.rerun()
        if c_back.button("🔙 스튜디오로 돌아가기", use_container_width=True):
            st.session_state.active_page = "studio"
            st.rerun()

    with tab_brand:
        brand = config.setdefault("brand_preset", {})
        font_keys = list(MARKETER_FONTS.keys())
        brand["store_name"] = st.text_input("기본 스토어명", value=brand.get("store_name", ""))
        brand["slogan"] = st.text_input("브랜드 슬로건", value=brand.get("slogan", ""))
        brand["shipping_fee"] = st.text_area("기본 배송비 안내", value=brand.get("shipping_fee", ""), height=70)
        brand["exchange_notice"] = st.text_area(
            "교환·반품 안내 (전자상거래법 기준)",
            value=brand.get("exchange_notice", "전자상거래 등에서의 소비자보호에 관한 법률에 따라 수령 후 7일 이내 교환·반품이 가능합니다."),
            height=80,
        )
        brand["target_margin_pct"] = st.slider("기본 목표 마진율 (%)", 10, 80, int(brand.get("target_margin_pct") or 35))
        title_idx = font_keys.index(brand["title_font"]) if brand.get("title_font") in font_keys else 1
        body_idx = font_keys.index(brand["body_font"]) if brand.get("body_font") in font_keys else 0
        brand["title_font"] = st.selectbox("기본 제목 폰트", font_keys, index=title_idx)
        brand["body_font"] = st.selectbox("기본 본문 폰트", font_keys, index=body_idx)

        c_b1, c_b2 = st.columns(2)
        if c_b1.button("💾 브랜드 기본값 저장", type="primary", use_container_width=True):
            save_config(config)
            st.success("✅ 브랜드 기본값을 저장했습니다.")
        if c_b2.button("현재 작업 프로젝트에 기본값 적용", use_container_width=True):
            if brand.get("shipping_fee"):
                pdata["shipping_info"]["fee"] = brand["shipping_fee"]
                pdata["shipping_info"]["shipping_fee"] = brand["shipping_fee"]
            if brand.get("exchange_notice"):
                pdata["shipping_info"]["exchange"] = brand["exchange_notice"]
                pdata["shipping_info"]["exchange_info"] = brand["exchange_notice"]
            if brand.get("title_font"):
                pdata["title_font"] = brand["title_font"]
            if brand.get("body_font"):
                pdata["body_font"] = brand["body_font"]
            pdata["draft_html"] = _render_page(pdata)
            save_project(st.session_state.current_proj_id, pdata)
            st.success("✅ 현재 프로젝트에 브랜드 기본값을 즉시 반영했습니다.")

    with tab_image:
        image_cfg = config.setdefault("image_defaults", {})
        width_options = [860, 780, 1000]
        current_width = int(image_cfg.get("detail_width") or 860)
        if current_width not in width_options:
            width_options.append(current_width)
        image_cfg["detail_width"] = st.selectbox(
            "기본 상세페이지 가로 규격",
            width_options,
            index=width_options.index(current_width),
            format_func=lambda w: {860: "860px (네이버 스마트스토어/G마켓 표준)", 780: "780px (쿠팡 최적)", 1000: "1000px (와이드/와디즈)"}.get(w, f"{w}px"),
        )
        image_cfg["save_format"] = st.selectbox(
            "기본 저장 포맷",
            ["PNG", "JPEG"],
            index=0 if str(image_cfg.get("save_format", "PNG")).upper() != "JPEG" else 1,
        )
        image_cfg["jpeg_quality"] = st.slider("JPEG 압축 화질", 80, 100, int(image_cfg.get("jpeg_quality") or 92))
        image_cfg["keep_png_alpha"] = st.checkbox("PNG 투명 누끼 배경 유지", value=bool(image_cfg.get("keep_png_alpha", True)))
        image_cfg["shadow_strength"] = st.slider("상세페이지 기본 바닥 그림자 강도", 0, 40, int(image_cfg.get("shadow_strength") or 18))

        st.markdown("##### 🎨 PhotoCraft 인앱 스튜디오 기본값")
        bg_keys = ["clean_white", "dark_metallic", "warm_wood", "neon_tech"]
        cur_bg = image_cfg.get("default_studio_bg", "clean_white")
        bg_idx = bg_keys.index(cur_bg) if cur_bg in bg_keys else 0
        image_cfg["default_studio_bg"] = st.selectbox(
            "기본 절차적 스튜디오 배경 조명",
            bg_keys,
            index=bg_idx,
            format_func=lambda s: {
                "clean_white": "⚪ 클린 화이트 호리존 (순백색 ~ 소프트 그레이 미세 방사광)",
                "dark_metallic": "⚫ 다크 메탈릭 스튜디오 (슬레이트 블랙 + 상단 스포트라이트)",
                "warm_wood": "🪵 웜 우드 데스크 (따뜻한 오크 우드 + 앰비언트 라이트)",
                "neon_tech": "🔷 네온 테크 사이버 (딥 네이비 + 사이언/블루 글로우)"
            }.get(s, s)
        )
        c_ic1, c_ic2 = st.columns(2)
        image_cfg["default_contact_shadow"] = c_ic1.checkbox("바닥 접촉 그림자 기본 켜기", value=bool(image_cfg.get("default_contact_shadow", True)))
        image_cfg["default_floor_reflection"] = c_ic2.checkbox("바닥 유리 반사광 기본 켜기", value=bool(image_cfg.get("default_floor_reflection", False)))

        if st.button("💾 출력 규격 설정 저장", type="primary", use_container_width=True):
            save_config(config)
            st.success("✅ 출력 규격 및 PhotoCraft 기본값을 저장했습니다.")

    with tab_data:
        st.markdown("##### 📦 데이터 백업 및 복원")
        backup_zip = create_hub_backup_zip()
        st.download_button(
            "📥 전체 프로젝트 & 설정 ZIP 백업 다운로드",
            data=backup_zip,
            file_name=f"seller_hub_backup_{datetime.now().strftime('%Y%m%d')}.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary",
        )
        st.markdown("---")
        restore_file = st.file_uploader("백업 ZIP 파일 복원", type=["zip"], key="restore_zip")
        if restore_file and st.button("📤 선택한 ZIP 파일로 데이터 복원 실행", use_container_width=True):
            count = restore_hub_backup_zip(restore_file.getvalue())
            st.success(f"✅ {count}개 프로젝트 및 설정 파일을 성공적으로 복원했습니다!")
            st.rerun()
        if st.button("🧹 메모리 캐시 비우기 (메모리 최적화)", use_container_width=True):
            st.cache_data.clear()
            st.cache_resource.clear()
            st.success("✅ 캐시를 비웠습니다.")


# =====================================================================
# [4. 4단계 작업 스튜디오 화면]
# =====================================================================
if st.session_state.active_page == "api_settings":
    render_settings_page()
    st.stop()

# --- 스튜디오 메인 헤더 & API 페이지 링크 ---
c_title_left, c_title_right = st.columns([7.5, 2.5])
with c_title_left:
    st.markdown(f"### ⚡ [{pdata.get('title', '새 제품')}] 기획 & 상세페이지 스튜디오")
with c_title_right:
    if st.button("⚙️ API 연동 및 환경설정", use_container_width=True):
        st.session_state.active_page = "api_settings"
        st.rerun()

# --- 4단계 인터랙티브 스텝 진행 내비게이션 바 ---
step_cols = st.columns(4)
steps_meta = [
    (1, "📸 1. 기초자료 & 사진"),
    (2, "🛒 2. TOP 10 분석 & 전략"),
    (3, "🎨 3. AI 미디어 스튜디오"),
    (4, "🎬 4. 상세페이지 빌더"),
]
for col, (s_idx, s_title) in zip(step_cols, steps_meta):
    is_active = (st.session_state.active_step == s_idx)
    if col.button(s_title, key=f"nav_step_{s_idx}", type="primary" if is_active else "secondary", use_container_width=True):
        st.session_state.active_step = s_idx
        st.rerun()

st.markdown("<hr style='margin:10px 0 14px 0; border-color:#334155;'>", unsafe_allow_html=True)


# ---------------------------------------------------------------------
# [1단계: 📸 기초자료 & 다각도 사진 멀티 업로드]
# ---------------------------------------------------------------------
if st.session_state.active_step == 1:
    st.markdown("#### 📸 1단계: 제품 기초자료 입력 & 다각도 사진 등록")
    render_free_cutout_shortcuts("⚡ [초정밀 무료 누끼 AI 바로가기 바] 외부에서 딴 투명 PNG 업로드 시 100% 무손실 직통 통과")
    c_l1, c_r1 = st.columns([5, 5], gap="large")

    with c_l1:
        st.markdown("##### 📝 제품 핵심 기본정보")
        kw = st.text_input("제품명 / 키워드", value=pdata.get("keyword") or pdata.get("title", ""), key=f"kw_{pid}", placeholder="예: 초정밀 자석 시계 드라이버")
        cost = st.text_input("매입 원가 / 희망 판매가", value=pdata.get("cost_price", ""), key=f"cost_{pid}", placeholder="예: 원가 200원 / 희망가 3,900원")
        m_size = st.text_input("실측 규격 (직접 입력 또는 100원 동전 실측)", value=pdata.get("manual_size", ""), key=f"size_{pid}", placeholder="예: 총 길이 105mm (100원 동전 실측)")

        # 키워드/제품명 변경 시 전략 분석 & 9단계 기획 & 상세페이지 즉각 실시간 동기화
        cur_kw = (pdata.get("keyword") or "").strip()
        new_kw = kw.strip()
        kw_updated = False
        if new_kw and new_kw != cur_kw:
            pdata["keyword"] = new_kw
            pdata["title"] = new_kw
            pdata["nine_steps"] = get_default_9steps(msize=m_size.strip(), kw=new_kw)
            rep_chk = generate_marketer_strategy_report([], [], pdata)
            pdata.setdefault("page_blocks", {}).update(rep_chk.get("recommended_blocks", {}))
            kw_updated = True

        if cost.strip() != (pdata.get("cost_price") or "").strip():
            pdata["cost_price"] = cost.strip()
            kw_updated = True

        if m_size.strip() != (pdata.get("manual_size") or "").strip():
            pdata["manual_size"] = m_size.strip()
            kw_updated = True

        if kw_updated:
            pdata["draft_html"] = _render_page(pdata)
            save_project(pid, pdata)

        sel_plat = st.selectbox(
            "타겟 플랫폼 규격",
            plat_list,
            index=plat_list.index(pdata.get("target_platform", plat_list[0])) if pdata.get("target_platform") in plat_list else 0,
            key=f"plat_{pid}"
        )
        pdata["target_platform"] = sel_plat
        cur_spec = get_platform_spec(sel_plat)
        st.caption(f"📐 상세 가로 `{cur_spec['detail_width']}px` / 썸네일 `{cur_spec['thumb_size'][0]}×{cur_spec['thumb_size'][1]}px` ({cur_spec.get('recommended_platforms', '')})")

        # 스펙 5문 5답 인터뷰 (부분 렌더링)
        @st.fragment
        def render_spec_interview_fragment():
            st.markdown("---")
            with st.expander("📋 AI 필수 스펙 5문 5답 열기", expanded=False):
                spec_qs = generate_category_spec_questions(pdata, gemini_key=config.get("gemini_key", ""))
                saved_qa = pdata.get("spec_qa", {})
                new_qa = {}
                new_spec_rows = []
                for sq in spec_qs:
                    qk = sq.get("id")
                    cur_ans = saved_qa.get(qk, sq.get("default", ""))
                    ans_v = st.text_input(sq.get("label"), value=cur_ans, key=f"qa_{pid}_{qk}")
                    new_qa[qk] = ans_v
                    if ans_v.strip():
                        new_spec_rows.append({"항목": sq.get("label"), "내용": ans_v.strip(), "label": sq.get("label"), "value": ans_v.strip()})
                if st.button("✨ 스펙 표에 즉시 반영", type="primary", use_container_width=True):
                    pdata["spec_qa"] = new_qa
                    if new_spec_rows:
                        pdata["product_specs"] = new_spec_rows
                    pdata["draft_html"] = _render_page(pdata)
                    save_project(pid, pdata)
                    st.success("✅ 스펙 반영 완료!")
        render_spec_interview_fragment()

    with c_r1:
        st.markdown("##### 📸 제품 실물 사진 등록 (멀티 업로드)")
        st.caption("제품의 다양한 실물 사진(전면, 측면, 장착 디테일 컷 등)을 한 번에 올려주세요.")
        multi_up = st.file_uploader(
            "사진 파일 멀티 선택 (JPG, PNG, WebP)",
            accept_multiple_files=True,
            type=["jpg", "jpeg", "png", "webp"],
            key=f"multi_{pid}",
        )
        if multi_up:
            default_caps = ["전면 디테일", "측면 마감", "장착부 클로즈업", "실물 텍스처", "컴팩트 사이즈", "디테일 뷰"]
            has_new_upload = False
            cur_imgs = pdata.setdefault("multi_images", [])

            for uf in multi_up:
                raw_b = uf.getvalue()
                if not raw_b:
                    continue
                # 이미 정상 누끼까지 추출 완료된 파일인지 확인
                existing_match = next((m for m in cur_imgs if m.get("name") == uf.name), None)
                if existing_match and existing_match.get("is_cutout") and existing_match.get("cutout_b64"):
                    continue

                has_new_upload = True
                _, durl = file_to_media_data_url(uf, auto_polish=True)
                if not durl:
                    continue

                up_pil = base64_url_to_pil(durl)
                c_idx = len(cur_imgs) % len(default_caps)

                # 초고속 AI 정밀 누끼 추출 (u2netp)
                with st.spinner(f"⚡ '{uf.name}' 사진 AI 누끼 추출 중..."):
                    cut_pil = quick_auto_cutout_pil(up_pil)

                cutout_durl = pil_to_base64_url(cut_pil, fmt="PNG") if cut_pil else durl

                # 첫 번째 이미지이거나 대표 이미지가 없을 때, 또는 대표 이미지 누끼가 없을 때 대표로 즉시 설정
                if not pdata.get("fg_cutout_b64") or len(cur_imgs) == 0:
                    pdata["fg_cutout_b64"] = cutout_durl
                    pdata["orig_img_b64"] = durl

                    th_spec = get_platform_spec(pdata.get("target_platform"))
                    th_w, th_h = th_spec["thumb_size"]
                    canvas = Image.new("RGB", (th_w, th_h), (255, 255, 255))
                    fg_rgba = cut_pil.convert("RGBA") if cut_pil else up_pil.convert("RGBA")
                    scale = min(int(th_w * 0.78) / max(1, fg_rgba.width), int(th_h * 0.78) / max(1, fg_rgba.height))
                    nw, nh = max(1, int(fg_rgba.width * scale)), max(1, int(fg_rgba.height * scale))
                    resized_fg = fg_rgba.resize((nw, nh), Image.Resampling.LANCZOS)
                    canvas.paste(resized_fg, ((th_w - nw) // 2, (th_h - nh) // 2), resized_fg)
                    pdata["edited_img_b64"] = pil_to_base64_url(canvas, max_w=th_w, fmt="JPEG")
                    pdata.setdefault("photo_ai_report", {})["engine_used"] = "⚡ AI 초고속 누끼 (자동 추출 완료)"

                img_entry = {
                    "name": uf.name,
                    "angle_label": default_caps[c_idx],
                    "b64": durl,
                    "polished_b64": cutout_durl,
                    "cutout_b64": cutout_durl,
                    "is_cutout": True,
                    "use_in_page": True
                }

                if existing_match:
                    existing_match.update(img_entry)
                else:
                    cur_imgs.append(img_entry)

            if has_new_upload:
                if not pdata.get("orig_img_b64") and cur_imgs:
                    pdata["orig_img_b64"] = cur_imgs[0]["b64"]
                pdata["draft_html"] = _render_page(pdata)
                save_project(pid, pdata)
                st.session_state.proj_data = pdata
                st.success("🎉 사진 등록 및 AI 정밀 누끼 추출이 완료되어 AI스튜디오 및 상세페이지에 즉시 적용되었습니다!")
                st.rerun()

        # 투명 PNG 감지 배지 실시간 노출
        has_cutout_now = (
            any(m.get("is_cutout") for m in pdata.get("multi_images", []))
            or is_already_cutout_png(base64_url_to_pil(pdata.get("orig_img_b64")))
            or is_already_cutout_png(base64_url_to_pil(pdata.get("fg_cutout_b64")))
        )
        if has_cutout_now:
            st.success("✅ 이미 누끼가 완료된 고화질 투명 PNG입니다! (AI 재가공 없이 원본 100% 유지)")

        cur_multi = pdata.get("multi_images", [])
        if cur_multi:
            # 삭제 확인 모달 다이얼로그
            @st.dialog("⚠️ 사진 삭제 확인")
            def confirm_delete_dialog(delete_mode="all", target_indices=None):
                if delete_mode == "all":
                    st.warning("⚠️ **정말로 등록된 모든 사진을 삭제하시겠습니까?**")
                    st.markdown("<p style='font-size:0.9em; color:#cbd5e1;'>등록된 모든 사진이 완전히 삭제되며, 대표 누끼컷 및 썸네일도 초기화됩니다. 이 작업은 되돌릴 수 없습니다.</p>", unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ **선택하신 {len(target_indices)}장의 사진을 삭제하시겠습니까?**")
                    st.markdown("<p style='font-size:0.9em; color:#cbd5e1;'>선택된 사진들이 프로젝트에서 삭제됩니다.</p>", unsafe_allow_html=True)

                c_d1, c_d2 = st.columns(2)
                with c_d1:
                    if st.button("💥 네, 삭제합니다", type="primary", use_container_width=True, key=f"btn_modal_confirm_{pid}"):
                        if delete_mode == "all":
                            pdata["multi_images"] = []
                            pdata["orig_img_b64"] = ""
                            pdata["fg_cutout_b64"] = ""
                            pdata["edited_img_b64"] = ""
                        else:
                            pdata["multi_images"] = [m for idx, m in enumerate(pdata.get("multi_images", [])) if idx not in target_indices]
                            if pdata.get("multi_images"):
                                pdata["orig_img_b64"] = pdata["multi_images"][0].get("b64", "")
                                pdata["fg_cutout_b64"] = pdata["multi_images"][0].get("cutout_b64", "")
                                pdata["edited_img_b64"] = pdata["multi_images"][0].get("polished_b64", "")
                            else:
                                pdata["orig_img_b64"] = ""
                                pdata["fg_cutout_b64"] = ""
                                pdata["edited_img_b64"] = ""
                        pdata["draft_html"] = _render_page(pdata)
                        save_project(pid, pdata)
                        st.session_state.proj_data = pdata
                        st.success("삭제가 완료되었습니다.")
                        st.rerun()
                with c_d2:
                    if st.button("취소", use_container_width=True, key=f"btn_modal_cancel_{pid}"):
                        st.rerun()

            st.caption(f"등록된 사진: 총 {len(cur_multi)}장")

            # 1. 일괄 관리 툴바 (전체선택, 선택삭제, 전체삭제)
            sel_all_key = f"sel_all_{pid}"
            if sel_all_key not in st.session_state:
                st.session_state[sel_all_key] = False

            def _on_sel_all_change():
                target_state = st.session_state[sel_all_key]
                for idx_k in range(len(cur_multi)):
                    st.session_state[f"chk_sel_{pid}_{idx_k}"] = target_state

            c_tb1, c_tb2, c_tb3 = st.columns([3.5, 3.5, 3])
            with c_tb1:
                st.checkbox("☑️ 전체 선택", key=sel_all_key, on_change=_on_sel_all_change)
            with c_tb2:
                btn_del_sel = st.button("🗑️ 선택 삭제", use_container_width=True, key=f"btn_del_sel_{pid}", help="선택한 사진들을 삭제합니다.")
            with c_tb3:
                btn_del_all = st.button("💥 사진 전체 삭제", type="secondary", use_container_width=True, key=f"btn_del_all_{pid}", help="등록된 모든 사진을 초기화합니다.")

            if btn_del_all:
                confirm_delete_dialog("all")

            if st.button("✨ 등록된 대표 사진으로 AI 정밀 누끼 따기 (바닥 그림자 칼제거 & 본체 보호)", type="primary", use_container_width=True, key=f"btn_quick_cutout_all_{pid}"):
                with st.spinner("⚡ AI 정밀 누끼 추출 및 바닥 그림자 완벽 제거 중..."):
                    # 대표 사진 기준으로 누끼 추출
                    main_m = cur_multi[0]
                    orig_durl = pdata.get("orig_img_b64") or main_m.get("b64")
                    up_pil = base64_url_to_pil(orig_durl)
                    cut_pil = quick_auto_cutout_pil(up_pil, clean_shadow=True)
                    cutout_durl = pil_to_base64_url(cut_pil, fmt="PNG") if cut_pil else orig_durl

                    pdata["fg_cutout_b64"] = cutout_durl
                    pdata["orig_img_b64"] = orig_durl

                    th_spec = get_platform_spec(pdata.get("target_platform"))
                    th_w, th_h = th_spec["thumb_size"]
                    canvas = Image.new("RGB", (th_w, th_h), (255, 255, 255))
                    fg_rgba = cut_pil.convert("RGBA") if cut_pil else up_pil.convert("RGBA")
                    scale = min(int(th_w * 0.78) / max(1, fg_rgba.width), int(th_h * 0.78) / max(1, fg_rgba.height))
                    nw, nh = max(1, int(fg_rgba.width * scale)), max(1, int(fg_rgba.height * scale))
                    resized_fg = fg_rgba.resize((nw, nh), Image.Resampling.LANCZOS)
                    canvas.paste(resized_fg, ((th_w - nw) // 2, (th_h - nh) // 2), resized_fg)
                    pdata["edited_img_b64"] = pil_to_base64_url(canvas, max_w=th_w, fmt="JPEG")

                    main_m["polished_b64"] = cutout_durl
                    main_m["cutout_b64"] = cutout_durl
                    main_m["is_cutout"] = True

                    pdata["draft_html"] = _render_page(pdata)
                    save_project(pid, pdata)
                    st.session_state.proj_data = pdata
                    st.success("✅ AI 정밀 누끼 추출 및 상세페이지 반영이 완료되었습니다!")
                    st.rerun()

            selected_indices = []
            cols_g = st.columns(min(3, len(cur_multi)))
            for idx_m, m_item in enumerate(cur_multi):
                chk_key_m = f"chk_sel_{pid}_{idx_m}"
                if chk_key_m not in st.session_state:
                    st.session_state[chk_key_m] = st.session_state[sel_all_key]

                with cols_g[idx_m % len(cols_g)]:
                    chk_this = st.checkbox(f"선택 #{idx_m+1}", key=chk_key_m)
                    if chk_this:
                        selected_indices.append(idx_m)
                    mpil = base64_url_to_pil(m_item.get("polished_b64") or m_item.get("b64"))
                    if mpil is not None:
                        st.image(mpil, use_container_width=True)
                    m_lbl = st.text_input("사진 캡션", value=m_item.get("angle_label", ""), key=f"lbl_m_{pid}_{idx_m}", placeholder="예: 전면 디테일 (공백 시 숨김)")
                    if m_lbl != m_item.get("angle_label"):
                        m_item["angle_label"] = m_lbl
                        pdata["draft_html"] = _render_page(pdata)
                        save_project(pid, pdata)
                    
                    c_chk_use = st.checkbox("📋 상세페이지 반영", value=m_item.get("use_in_page", True), key=f"chk_use_p_{pid}_{idx_m}", help="체크 시 상세페이지 본문에 바로 반영됩니다.")
                    if c_chk_use != m_item.get("use_in_page", True):
                        m_item["use_in_page"] = c_chk_use
                        pdata["draft_html"] = _render_page(pdata)
                        save_project(pid, pdata)
                        st.rerun()

                    b1, b2, b3 = st.columns([1, 1, 1])
                    if b1.button("⭐ 대표", key=f"set_main_{idx_m}", use_container_width=True, help="이 사진을 대표 컷으로 설정"):
                        pdata["orig_img_b64"] = m_item["b64"]
                        if m_item.get("cutout_b64"):
                            pdata["fg_cutout_b64"] = m_item["cutout_b64"]
                        pdata["draft_html"] = _render_page(pdata)
                        save_project(pid, pdata)
                        st.session_state.proj_data = pdata
                        st.rerun()

                    if b2.button("✂️ 누끼", key=f"recut_single_{idx_m}", use_container_width=True, help="이 사진의 AI 누끼를 즉시 추출"):
                        with st.spinner("AI 누끼 추출 중..."):
                            up_p = base64_url_to_pil(m_item.get("b64"))
                            cp = quick_auto_cutout_pil(up_p)
                            cdurl = pil_to_base64_url(cp, fmt="PNG") if cp else m_item.get("b64")
                            m_item["cutout_b64"] = cdurl
                            m_item["polished_b64"] = cdurl
                            m_item["is_cutout"] = True
                            pdata["fg_cutout_b64"] = cdurl
                            pdata["draft_html"] = _render_page(pdata)
                            save_project(pid, pdata)
                            st.session_state.proj_data = pdata
                            st.success("✅ 누끼 추출 완료!")
                            st.rerun()

                    if b3.button("🗑️", key=f"del_m_{idx_m}", use_container_width=True, help="이 사진 삭제"):
                        confirm_delete_dialog("selected", [idx_m])

            if btn_del_sel:
                if selected_indices:
                    confirm_delete_dialog("selected", selected_indices)
                else:
                    st.warning("⚠️ 삭제할 사진을 먼저 체크해 주세요.")

        if pdata.get("fg_cutout_b64") or pdata.get("edited_img_b64"):
            st.markdown("##### ✨ 완성된 대표 누끼 컷 (투명 직통 & 썸네일)")
            cutout_img = base64_url_to_pil(pdata.get("fg_cutout_b64") or pdata.get("edited_img_b64"))
            if cutout_img is not None:
                st.image(cutout_img, use_container_width=True)
                st.caption("💎 투명 배경이 100% 무손실 보존되어 상세페이지 배경과 완벽히 융합됩니다.")

    # 1단계 하단 다음 단계 이동 버튼 (핵심!)
    st.markdown("---")
    c_btn_l, c_btn_r = st.columns([4, 6])
    with c_btn_l:
        if st.button("💾 기초자료 저장만 하기", use_container_width=True):
            pdata["keyword"] = kw.strip()
            pdata["cost_price"] = cost.strip()
            pdata["manual_size"] = m_size.strip()
            pdata["target_platform"] = sel_plat
            if kw.strip():
                pdata["title"] = kw.strip()
            pdata["draft_html"] = _render_page(pdata)
            save_project(pid, pdata)
            st.success("✅ 저장 완료!")
    with c_btn_r:
        if st.button("💾 기초정보 & 사진 저장 후 [2단계 TOP 10 분석]으로 이동 ➡️", type="primary", use_container_width=True):
            pdata["keyword"] = kw.strip()
            pdata["cost_price"] = cost.strip()
            pdata["manual_size"] = m_size.strip()
            pdata["target_platform"] = sel_plat
            if kw.strip():
                pdata["title"] = kw.strip()
                _ag, _st9 = generate_9step_and_6agent_plan(pdata, gemini_key=config.get("gemini_key", ""))
                pdata["six_agents_research"] = _ag
                pdata["nine_steps"] = _st9
                # 2단계에 필요한 스마트스토어 TOP 10 데이터 자동 사전 수집
                if not pdata.get("ref_items"):
                    items_i, prices_i, _ = fetch_shopping_reference(kw.strip())
                    if items_i:
                        pdata["ref_items"] = items_i
                _rep = generate_marketer_strategy_report(pdata.get("ref_items", []), [], pdata)
                cur_hook = pdata.get("page_blocks", {}).get("hook_title", "")
                if not cur_hook or ("나사" in cur_hook or "드라이버" in cur_hook) and ("드라이버" not in kw.strip()):
                    pdata.setdefault("page_blocks", {}).update(_rep.get("recommended_blocks", {}))
            pdata["draft_html"] = _render_page(pdata)
            save_project(pid, pdata)
            st.session_state.active_step = 2
            st.rerun()

    # 1단계 실시간 상세페이지 미리보기 (필요 시 펼치기 - 성능 최적화)
    st.markdown("---")
    with st.expander("👁️ 사진 & 제품명이 반영된 상세페이지 미리보기 (클릭하여 확인)", expanded=False):
        st.caption("💡 제품명을 입력하거나 사진을 업로드하면 아래 상세페이지에 실시간으로 즉시 반영됩니다.")
        detail_html = pdata.get("draft_html") or _render_page(pdata)
        components.html(detail_html, height=750, scrolling=True)


# ---------------------------------------------------------------------
# [2단계: 🛒 TOP 10 분석 & 1:1 디렉터 전략 회의실]
# ---------------------------------------------------------------------
elif st.session_state.active_step == 2:
    st.markdown("#### 🛒 2단계: 스마트스토어 TOP 10 심층 분석 & 1:1 디렉터 전략 회의실")
    kw_ref = (pdata.get("keyword") or pdata.get("title") or "").strip()

    c_t2_l, c_t2_r = st.columns([6.2, 3.8], gap="large")
    with c_t2_l:
        st.markdown(f"##### 🛒 [{kw_ref or '제품'}] 스마트스토어 상위 10개 실거래 상품 표 (링크 클릭 시 새 탭 열림)")
        if not pdata.get("ref_items") and kw_ref:
            items_i, prices_i, _ = fetch_shopping_reference(kw_ref)
            if items_i:
                pdata["ref_items"] = items_i
                save_project(pid, pdata)

        if pdata.get("ref_items"):
            rows_html = "".join([
                f'<tr>'
                f'<td style="font-weight:900; color:#facc15 !important; white-space:nowrap; text-align:center;">{it.get("순위", "")}</td>'
                f'<td style="font-weight:800; color:#e2e8f0 !important; white-space:nowrap;">{it.get("스토어명", "")}</td>'
                f'<td><a href="{it.get("상품링크", "#")}" target="_blank" rel="noopener noreferrer" style="color:#38bdf8 !important; font-weight:800; text-decoration:underline;">{it.get("참고한 실제 상품명", "")}</a></td>'
                f'<td style="font-weight:900; color:#4ade80 !important; white-space:nowrap; text-align:right;">{it.get("판매가", "")}</td>'
                f'<td style="white-space:nowrap; text-align:center;"><a href="{it.get("상품링크", "#")}" target="_blank" rel="noopener noreferrer" class="top10-link-btn">🔗 열기 ↗</a></td>'
                f'</tr>'
                for it in pdata["ref_items"]
            ])
            table_html = (
                '<div style="max-height:360px; overflow-y:auto; border-radius:12px; border:1px solid #334155; margin-bottom:12px;">'
                '<table class="top10-table" style="width:100%; border-collapse:collapse;">'
                '<thead><tr>'
                '<th>순위</th><th>스토어명</th><th>실제 상품명 (클릭 시 이동)</th><th>판매가</th><th>바로가기</th>'
                '</tr></thead>'
                f'<tbody>{rows_html}</tbody>'
                '</table>'
                '</div>'
            )
            st.html(table_html)
        else:
            st.info("1단계에서 제품명을 입력하고 저장하면 상위 10개 실거래 상품이 자동으로 수집됩니다.")

        c_u1, c_u2 = st.columns([7, 3])
        new_url = c_u1.text_input("벤치마킹 참고 URL 직접 추가", placeholder="https://smartstore.naver.com/...", label_visibility="collapsed", key=f"url_{pid}")
        if c_u2.button("🔍 URL 분석 추가", use_container_width=True):
            if new_url.strip():
                u_info = analyze_custom_url(new_url.strip(), fallback_keyword=kw_ref or "제품")
                pdata.setdefault("ref_urls", []).append(u_info)
                save_project(pid, pdata)
                st.success("✅ 분석 완료!")
                st.rerun()

        if pdata.get("ref_urls"):
            for idx, u in enumerate(pdata["ref_urls"]):
                ma = u.get("marketing_analysis", {})
                st.markdown(f"""
                <div class="dark-safe-card" style="padding:10px 14px; font-size:0.88em;">
                    <b>📌 참고 URL {idx+1}:</b> <a href="{u['url']}" target="_blank" style="color:#38bdf8 !important;">{u['title']}</a> ({u['price']})<br>
                    • <b>소구점:</b> {ma.get('emphasized_points', '')} | <b>리뷰 칭찬:</b> {ma.get('review_praise_points', '')}
                </div>
                """, unsafe_allow_html=True)

    with c_t2_r:
        m_rep = generate_marketer_strategy_report(pdata.get("ref_items", []), pdata.get("ref_urls", []), pdata)
        ps = m_rep["price_stats"]
        if ps.get("avg"):
            st.markdown(f"""
            <div class="dark-safe-card" style="padding:12px 14px; font-size:0.9em; margin-bottom:10px;">
                <b>💰 수학적 3단 가격 전략</b><br>
                • <b>1안 진입가:</b> <span class="price-highlight-green">{ps['entry']:,}원</span> (최저가 방어)<br>
                • <b>2안 주력가:</b> <span class="price-highlight-blue">{ps['main']:,}원</span> (마진 확보)<br>
                • <b>3안 세트가:</b> <span class="price-highlight-red">{ps['bundle']:,}원</span> (1+1 묶음)<br>
                <span style="font-size:0.84em; color:#94a3b8;">* 상위 10개 평균가({ps['avg']:,}원) 기반 산출</span>
            </div>
            """, unsafe_allow_html=True)

        # 1:1 디렉터 채팅
        @st.fragment
        def render_director_chat_fragment():
            st.markdown("##### 💬 AI 디렉터 1:1 전략 회의실")
            chat_container = st.container(height=320, border=True)
            with chat_container:
                if not pdata.get("chat_history"):
                    st.markdown("""
                    <div class="dark-safe-card" style="font-size:0.86em; padding:10px;">
                        👨‍💼 <b>AI 디렉터:</b> 대표님! 상위 10개 분석 결과를 바탕으로 주력 카피와 가격을 잡았습니다. 추가로 반영하고 싶은 전략이나 촬영 컷에 대해 편하게 말씀해 주세요!
                    </div>
                    """, unsafe_allow_html=True)
                for msg_item in pdata.get("chat_history", []):
                    role = msg_item.get("role", "user")
                    with st.chat_message("user" if role == "user" else "assistant"):
                        st.markdown(msg_item.get("content", ""))

            chat_in = st.chat_input("의견 입력 (예: 주력가는 3,900원으로 가고 자석 기능 더 강조해줘)")
            if chat_in:
                pdata.setdefault("chat_history", []).append({"role": "user", "content": chat_in})
                reply = run_director_chat_turn(chat_in, pdata, gemini_key=config.get("gemini_key", ""))
                pdata["chat_history"].append({"role": "assistant", "content": reply})
                pdata["draft_html"] = _render_page(pdata)
                save_project(pid, pdata)
                st.rerun()

            if st.button("✨ 위 전략 & 카피를 상세페이지에 즉시 적용", type="primary", use_container_width=True):
                if m_rep.get("recommended_blocks"):
                    pdata["page_blocks"].update(m_rep["recommended_blocks"])
                ag_out, st9_out = generate_9step_and_6agent_plan(pdata, gemini_key=config.get("gemini_key", ""))
                pdata["six_agents_research"] = ag_out
                pdata["nine_steps"] = st9_out
                pdata["draft_html"] = _render_page(pdata)
                save_project(pid, pdata)
                st.success("✅ 전략 및 카피 일괄 적용 완료!")
                st.rerun()
        render_director_chat_fragment()

    # 2단계 하단 내비게이션
    st.markdown("---")
    c_nav_prev2, c_nav_next2 = st.columns(2)
    with c_nav_prev2:
        if st.button("⬅️ 1단계(기초자료 & 사진)로 돌아가기", use_container_width=True):
            st.session_state.active_step = 1
            st.rerun()
    with c_nav_next2:
        if st.button("💾 3단계 [AI 미디어 스튜디오]로 이동 ➡️", type="primary", use_container_width=True):
            st.session_state.active_step = 3
            st.rerun()


# ---------------------------------------------------------------------
# [3단계: 🎨 AI 미디어 스튜디오]
# ---------------------------------------------------------------------
elif st.session_state.active_step == 3:
    st.markdown("#### 🎨 3단계: 다각도 교차 분석 AI 사진/영상 편집 스튜디오")

    if not pdata.get("orig_img_b64"):
        st.warning("먼저 1단계에서 제품 사진을 올려주세요.")
        if st.button("⬅️ 1단계로 사진 올리러 가기", type="primary"):
            st.session_state.active_step = 1
            st.rerun()
    else:
        orig_pil = base64_url_to_pil(pdata["orig_img_b64"])
        if is_already_cutout_png(orig_pil) or is_already_cutout_png(base64_url_to_pil(pdata.get("fg_cutout_b64"))):
            st.success("✅ 이미 누끼가 완료된 고화질 투명 PNG입니다! (AI 재가공 없이 원본 100% 유지)")
            st.info("💡 **[원본 무손실 직통 패스 가동 중]** 배경이 투명한 고화질 PNG 파일입니다. 불필요하게 AI가 누끼를 다시 따서 외곽선을 망가뜨리지 않고, 100% 무손실 원본 그대로 상세페이지와 스튜디오 썸네일에 직통 반영됩니다.")
        @st.fragment
        def render_photocraft_studio_fragment():
            col_s1, col_s2 = st.columns([5, 5], gap="large")

            # 전경 누끼 대상 PIL 준비
            target_cutout_b64 = pdata.get("fg_cutout_b64") or pdata.get("orig_img_b64")
            fg_pil = base64_url_to_pil(target_cutout_b64)
            if fg_pil is None:
                fg_pil = orig_pil

            with col_s1:
                st.markdown("##### 🎛️ 아트크래프트(PhotoCraft) 4단계 비파괴 스튜디오")

                # 규격 및 기본 프리셋
                c_p1, c_p2 = st.columns([6, 4])
                sel_plat_t3 = c_p1.selectbox(
                    "플랫폼 사이즈 규격",
                    plat_list,
                    index=plat_list.index(pdata.get("target_platform", plat_list[0])) if pdata.get("target_platform") in plat_list else 0,
                    key=f"pc_plat_{pid}"
                )
                pdata["target_platform"] = sel_plat_t3
                spec_t3 = get_platform_spec(sel_plat_t3)
                tw, th = spec_t3["thumb_size"]

                sel_mood_idx = c_p2.selectbox(
                    "TOP 10 명암 프리셋",
                    range(len(COMPETITOR_10_MOODS)),
                    format_func=lambda i: COMPETITOR_10_MOODS[i]["name"].split(":")[1] if ":" in COMPETITOR_10_MOODS[i]["name"] else COMPETITOR_10_MOODS[i]["name"],
                    key=f"pc_mood_{pid}"
                )
                mood_preset = COMPETITOR_10_MOODS[sel_mood_idx]

                # ⚡ 포토룸(PhotoRoom) 1-클릭 장면 프리셋 바
                st.markdown("###### ⚡ 포토룸(PhotoRoom) 1-클릭 커머스 프리셋")
                c_pr1, c_pr2, c_pr3, c_pr4 = st.columns(4)
                c_pr5, c_pr6, c_pr7, c_pr8 = st.columns(4)

                if c_pr1.button("⚪ 스탠다드", use_container_width=True, help="순백색 호리존 스튜디오 + 자연스러운 2중 접촉 그림자"):
                    st.session_state[f"l2_bgmode_{pid}"] = "🌅 스튜디오 조명 & 단상(Podium) 생성"
                    st.session_state[f"l2_proc_{pid}"] = "clean_white"
                    st.session_state[f"l2_pod_on_{pid}"] = False
                    st.session_state[f"l3_con_on_{pid}"] = True
                    set_dual_control_value(f"l3_con_op_{pid}", 0.75)
                    set_dual_control_value(f"l3_con_sp_{pid}", 0.85)
                    st.session_state[f"l3_amb_on_{pid}"] = True
                    set_dual_control_value(f"l3_amb_op_{pid}", 0.35)
                    set_dual_control_value(f"l3_amb_bl_{pid}", 16)
                    set_dual_control_value(f"l3_amb_x_{pid}", 0)
                    set_dual_control_value(f"l3_amb_y_{pid}", 16)
                    st.session_state[f"l3_sc_on_{pid}"] = False
                    st.session_state[f"l3_refl_on_{pid}"] = False
                    st.session_state[f"l3_rim_on_{pid}"] = False
                    set_dual_control_value(f"l4_wc_{pid}", 0)
                    set_dual_control_value(f"l4_cl_{pid}", 1.25)
                    set_dual_control_value(f"l4_ct_{pid}", 1.10)
                    set_dual_control_value(f"l4_vg_{pid}", 0)
                    st.session_state[f"l5_badge_on_{pid}"] = False
                    st.rerun()

                if c_pr2.button("🏛️ 대리석단상", use_container_width=True, help="럭셔리 마블 대리석 + 3D 원형 단상 받침대 + 은은한 반사광"):
                    st.session_state[f"l2_bgmode_{pid}"] = "🌅 스튜디오 조명 & 단상(Podium) 생성"
                    st.session_state[f"l2_proc_{pid}"] = "luxury_marble"
                    st.session_state[f"l2_pod_on_{pid}"] = True
                    set_dual_control_value(f"l2_pod_h_{pid}", 55)
                    set_dual_control_value(f"l2_pod_r_{pid}", 220)
                    st.session_state[f"l2_pod_st_{pid}"] = "clean_white"
                    st.session_state[f"l3_con_on_{pid}"] = True
                    set_dual_control_value(f"l3_con_op_{pid}", 0.80)
                    set_dual_control_value(f"l3_con_sp_{pid}", 0.85)
                    st.session_state[f"l3_amb_on_{pid}"] = True
                    set_dual_control_value(f"l3_amb_op_{pid}", 0.40)
                    set_dual_control_value(f"l3_amb_bl_{pid}", 18)
                    set_dual_control_value(f"l3_amb_x_{pid}", 0)
                    set_dual_control_value(f"l3_amb_y_{pid}", 18)
                    st.session_state[f"l3_sc_on_{pid}"] = False
                    st.session_state[f"l3_refl_on_{pid}"] = True
                    set_dual_control_value(f"l3_refl_op_{pid}", 0.20)
                    st.session_state[f"l3_rim_on_{pid}"] = False
                    set_dual_control_value(f"l4_wc_{pid}", 0)
                    set_dual_control_value(f"l4_cl_{pid}", 1.30)
                    set_dual_control_value(f"l4_ct_{pid}", 1.15)
                    set_dual_control_value(f"l4_vg_{pid}", 10)
                    st.rerun()

                if c_pr3.button("🪵 웜우드", use_container_width=True, help="따뜻한 원목 데스크 + 웜 골드 앰비언트 라이트"):
                    st.session_state[f"l2_bgmode_{pid}"] = "🌅 스튜디오 조명 & 단상(Podium) 생성"
                    st.session_state[f"l2_proc_{pid}"] = "warm_wood"
                    st.session_state[f"l2_pod_on_{pid}"] = False
                    st.session_state[f"l3_con_on_{pid}"] = True
                    set_dual_control_value(f"l3_con_op_{pid}", 0.75)
                    set_dual_control_value(f"l3_con_sp_{pid}", 0.90)
                    st.session_state[f"l3_amb_on_{pid}"] = True
                    set_dual_control_value(f"l3_amb_op_{pid}", 0.45)
                    set_dual_control_value(f"l3_amb_bl_{pid}", 20)
                    set_dual_control_value(f"l3_amb_x_{pid}", 5)
                    set_dual_control_value(f"l3_amb_y_{pid}", 18)
                    st.session_state[f"l3_sc_on_{pid}"] = False
                    st.session_state[f"l3_refl_on_{pid}"] = False
                    st.session_state[f"l3_rim_on_{pid}"] = True
                    st.session_state[f"l3_rim_col_{pid}"] = "gold"
                    set_dual_control_value(f"l3_rim_int_{pid}", 40)
                    set_dual_control_value(f"l3_rim_spr_{pid}", 7)
                    set_dual_control_value(f"l4_wc_{pid}", 15)
                    set_dual_control_value(f"l4_cl_{pid}", 1.20)
                    set_dual_control_value(f"l4_ct_{pid}", 1.12)
                    set_dual_control_value(f"l4_vg_{pid}", 15)
                    st.rerun()

                if c_pr4.button("⚫ 다크네온", use_container_width=True, help="다크 메탈릭 + 사이언 역광 림라이트 + 고대비 전자기기 화보"):
                    st.session_state[f"l2_bgmode_{pid}"] = "🌅 스튜디오 조명 & 단상(Podium) 생성"
                    st.session_state[f"l2_proc_{pid}"] = "dark_metallic"
                    st.session_state[f"l2_pod_on_{pid}"] = False
                    st.session_state[f"l3_con_on_{pid}"] = True
                    set_dual_control_value(f"l3_con_op_{pid}", 0.85)
                    set_dual_control_value(f"l3_con_sp_{pid}", 0.80)
                    st.session_state[f"l3_amb_on_{pid}"] = True
                    set_dual_control_value(f"l3_amb_op_{pid}", 0.50)
                    set_dual_control_value(f"l3_amb_bl_{pid}", 14)
                    set_dual_control_value(f"l3_amb_x_{pid}", 0)
                    set_dual_control_value(f"l3_amb_y_{pid}", 15)
                    st.session_state[f"l3_sc_on_{pid}"] = False
                    st.session_state[f"l3_refl_on_{pid}"] = True
                    set_dual_control_value(f"l3_refl_op_{pid}", 0.35)
                    st.session_state[f"l3_rim_on_{pid}"] = True
                    st.session_state[f"l3_rim_col_{pid}"] = "cyan"
                    set_dual_control_value(f"l3_rim_int_{pid}", 75)
                    set_dual_control_value(f"l3_rim_spr_{pid}", 7)
                    set_dual_control_value(f"l4_wc_{pid}", -15)
                    set_dual_control_value(f"l4_cl_{pid}", 1.45)
                    set_dual_control_value(f"l4_ct_{pid}", 1.30)
                    set_dual_control_value(f"l4_vg_{pid}", 25)
                    st.rerun()

                if c_pr5.button("🌸 파스텔뷰티", use_container_width=True, help="소프트 파스텔 배경 + 부드러운 화이트 단상 + 은은한 조명"):
                    st.session_state[f"l2_bgmode_{pid}"] = "🌅 스튜디오 조명 & 단상(Podium) 생성"
                    st.session_state[f"l2_proc_{pid}"] = "soft_pastel"
                    st.session_state[f"l2_pod_on_{pid}"] = True
                    set_dual_control_value(f"l2_pod_h_{pid}", 40)
                    set_dual_control_value(f"l2_pod_r_{pid}", 200)
                    st.session_state[f"l2_pod_st_{pid}"] = "clean_white"
                    st.session_state[f"l3_con_on_{pid}"] = True
                    set_dual_control_value(f"l3_con_op_{pid}", 0.55)
                    set_dual_control_value(f"l3_con_sp_{pid}", 0.85)
                    st.session_state[f"l3_amb_on_{pid}"] = True
                    set_dual_control_value(f"l3_amb_op_{pid}", 0.25)
                    set_dual_control_value(f"l3_amb_bl_{pid}", 22)
                    set_dual_control_value(f"l3_amb_x_{pid}", 0)
                    set_dual_control_value(f"l3_amb_y_{pid}", 12)
                    st.session_state[f"l3_sc_on_{pid}"] = False
                    st.session_state[f"l3_refl_on_{pid}"] = False
                    st.session_state[f"l3_rim_on_{pid}"] = True
                    st.session_state[f"l3_rim_col_{pid}"] = "white"
                    set_dual_control_value(f"l3_rim_int_{pid}", 45)
                    set_dual_control_value(f"l3_rim_spr_{pid}", 5)
                    set_dual_control_value(f"l4_wc_{pid}", 10)
                    set_dual_control_value(f"l4_cl_{pid}", 1.15)
                    set_dual_control_value(f"l4_ct_{pid}", 1.05)
                    set_dual_control_value(f"l4_vg_{pid}", 0)
                    st.rerun()

                if c_pr6.button("🧱 인더스트리얼", use_container_width=True, help="콘크리트 배경 + 3D 측면 투영 그림자 + 공구/하드웨어 전문 룩"):
                    st.session_state[f"l2_bgmode_{pid}"] = "🌅 스튜디오 조명 & 단상(Podium) 생성"
                    st.session_state[f"l2_proc_{pid}"] = "industrial_concrete"
                    st.session_state[f"l2_pod_on_{pid}"] = False
                    st.session_state[f"l3_con_on_{pid}"] = True
                    set_dual_control_value(f"l3_con_op_{pid}", 0.80)
                    set_dual_control_value(f"l3_con_sp_{pid}", 0.85)
                    st.session_state[f"l3_amb_on_{pid}"] = True
                    set_dual_control_value(f"l3_amb_op_{pid}", 0.30)
                    set_dual_control_value(f"l3_amb_bl_{pid}", 16)
                    set_dual_control_value(f"l3_amb_x_{pid}", 0)
                    set_dual_control_value(f"l3_amb_y_{pid}", 16)
                    st.session_state[f"l3_sc_on_{pid}"] = True
                    set_dual_control_value(f"l3_sc_ang_{pid}", 35)
                    set_dual_control_value(f"l3_sc_len_{pid}", 0.45)
                    set_dual_control_value(f"l3_sc_op_{pid}", 0.40)
                    st.session_state[f"l3_refl_on_{pid}"] = False
                    st.session_state[f"l3_rim_on_{pid}"] = False
                    set_dual_control_value(f"l4_wc_{pid}", -5)
                    set_dual_control_value(f"l4_cl_{pid}", 1.45)
                    set_dual_control_value(f"l4_ct_{pid}", 1.20)
                    set_dual_control_value(f"l4_vg_{pid}", 20)
                    st.rerun()

                if c_pr7.button("✨ 상세 투명PNG", use_container_width=True, help="배경 투명 무손실 직통 패스 (상세페이지 배경과 100% 자연 융합)"):
                    st.session_state[f"l2_bgmode_{pid}"] = "✨ 투명 배경 유지 (상세페이지 직통 융합 - 기본)"
                    st.session_state[f"l2_pod_on_{pid}"] = False
                    st.session_state[f"l3_con_on_{pid}"] = True
                    set_dual_control_value(f"l3_con_op_{pid}", 0.70)
                    set_dual_control_value(f"l3_con_sp_{pid}", 0.85)
                    st.session_state[f"l3_amb_on_{pid}"] = True
                    set_dual_control_value(f"l3_amb_op_{pid}", 0.30)
                    set_dual_control_value(f"l3_amb_bl_{pid}", 15)
                    set_dual_control_value(f"l3_amb_x_{pid}", 0)
                    set_dual_control_value(f"l3_amb_y_{pid}", 15)
                    st.session_state[f"l3_sc_on_{pid}"] = False
                    st.session_state[f"l3_refl_on_{pid}"] = False
                    st.session_state[f"l3_rim_on_{pid}"] = False
                    set_dual_control_value(f"l4_wc_{pid}", 0)
                    set_dual_control_value(f"l4_cl_{pid}", 1.20)
                    set_dual_control_value(f"l4_ct_{pid}", 1.10)
                    set_dual_control_value(f"l4_vg_{pid}", 0)
                    st.session_state[f"l5_badge_on_{pid}"] = False
                    st.rerun()

                if c_pr8.button("🔄 기본 초기화", use_container_width=True, help="모든 수치를 초기 기본값으로 리셋"):
                    set_dual_control_value(f"l1_posx_{pid}", 0)
                    set_dual_control_value(f"l1_posy_{pid}", 0)
                    set_dual_control_value(f"l1_scale_{pid}", 100)
                    set_dual_control_value(f"l1_rot_{pid}", 0)
                    set_dual_control_value(f"l1_feath_{pid}", 0.0)
                    st.session_state[f"l2_bgmode_{pid}"] = "✨ 투명 배경 유지 (상세페이지 직통 융합 - 기본)"
                    st.session_state[f"l2_pod_on_{pid}"] = False
                    st.session_state[f"l3_con_on_{pid}"] = True
                    set_dual_control_value(f"l3_con_op_{pid}", 0.75)
                    set_dual_control_value(f"l3_con_sp_{pid}", 0.85)
                    st.session_state[f"l3_amb_on_{pid}"] = True
                    set_dual_control_value(f"l3_amb_op_{pid}", 0.35)
                    set_dual_control_value(f"l3_amb_bl_{pid}", 16)
                    set_dual_control_value(f"l3_amb_x_{pid}", 0)
                    set_dual_control_value(f"l3_amb_y_{pid}", 16)
                    st.session_state[f"l3_sc_on_{pid}"] = False
                    st.session_state[f"l3_refl_on_{pid}"] = False
                    st.session_state[f"l3_rim_on_{pid}"] = False
                    set_dual_control_value(f"l4_wc_{pid}", 0)
                    set_dual_control_value(f"l4_cl_{pid}", 1.0)
                    set_dual_control_value(f"l4_ct_{pid}", 1.0)
                    set_dual_control_value(f"l4_vg_{pid}", 0)
                    st.session_state[f"l5_badge_on_{pid}"] = False
                    st.rerun()

                # AI 정밀 누끼 & 크롭 / 동전 실측 실행기
                with st.expander("📐 1단계: AI 정밀 누끼 추출 & 동전 실측 실행", expanded=not bool(pdata.get("fg_cutout_b64"))):
                    engine_mode = st.selectbox("누끼 엔진 모드", [
                        "🎯 다각도 교차분석 스마트 정밀 누끼 (추천)",
                        "🔄 자동 AI 폭포수 모드",
                        "🛡️ 무손실 원본 보존 프레임",
                        "☁️ 외부 클라우드 AI (Clipdrop / Photoroom)"
                    ], key=f"pc_eng_{pid}")
                    c_cr1, c_cr2, c_cr3, c_cr4 = st.columns(4)
                    cr_t = c_cr1.slider("위(%)", 0, 40, 18, key=f"pc_crt_{pid}")
                    cr_b = c_cr2.slider("아래(%)", 0, 40, 20, key=f"pc_crb_{pid}")
                    cr_l = c_cr3.slider("왼쪽(%)", 0, 40, 8, key=f"pc_crl_{pid}")
                    cr_r = c_cr4.slider("오른쪽(%)", 0, 40, 12, key=f"pc_crr_{pid}")

                    c_chk1, c_chk2 = st.columns(2)
                    opt_coin = c_chk1.checkbox("🪙 100원 동전 실측 후 자동 제거", value=True, key=f"pc_coin_{pid}")
                    opt_shadow = c_chk2.checkbox("🌑 바닥 그림자 자동 1차 감쇄", value=True, key=f"pc_sh_{pid}")

                    if st.button("✨ AI 정밀 누끼 & 실측 실행", type="primary", use_container_width=True, key=f"btn_run_cutout_{pid}"):
                        with st.spinner("다각도 사진 교차 분석 및 정밀 누끼 처리 중..."):
                            p_ctx = {"keyword": pdata.get("keyword", ""), "manual_size": pdata.get("manual_size", "")}
                            multi_pils = [base64_url_to_pil(m.get("b64")) for m in pdata.get("multi_images", []) if m.get("b64")]
                            res_pil, rep = process_photo_with_full_report(
                                orig_pil, engine_mode, mood_preset["name"],
                                crop_top=cr_t, crop_bottom=cr_b, crop_left=cr_l, crop_right=cr_r,
                                sharpness_val=float(mood_preset.get("sharpness", 1.35)),
                                brightness_val=float(mood_preset.get("brightness", 1.03)),
                                contrast_val=float(mood_preset.get("contrast", 1.14)),
                                color_val=1.05,
                                custom_bg_rgb=mood_preset.get("bg"),
                                cfg=config,
                                product_context=p_ctx,
                                remove_coin=opt_coin,
                                remove_shadow=opt_shadow,
                                platform_key=sel_plat_t3,
                                multi_pil_list=multi_pils,
                            )
                            if rep.get("measured_size"):
                                pdata["manual_size"] = rep["measured_size"]
                                pdata["page_blocks"]["point3_desc"] = rep["measured_size"]
                            if rep.get("fg_cutout_b64"):
                                pdata["fg_cutout_b64"] = rep["fg_cutout_b64"]
                            pdata["edited_img_b64"] = pil_to_base64_url(res_pil, max_w=1000)
                            pdata["photo_ai_report"] = rep
                            pdata["draft_html"] = _render_page(pdata)
                            save_project(pid, pdata)
                            st.success("✅ AI 정밀 누끼 완료!")
                            st.rerun()

                # 5대 레이어 탭
                tab_l1, tab_l2, tab_l3, tab_l4, tab_l5 = st.tabs([
                    "📐 L1. 피사체 변형·지우개",
                    "🌅 L2. 다중 배경·3D 단상",
                    "🌑 L3. 포토룸 3종 그림자·림라이트",
                    "🎨 L4. 색감·조명 톤",
                    "🏷️ L5. 판매 배지·스티커"
                ])

                # [레이어 1: 피사체 변형 & 인앱 마우스 지우개]
                with tab_l1:
                    st.caption("💡 모든 수치는 슬라이더를 마우스로 끌거나, 바로 아래 입력창에 숫자를 직접 입력하여 변경할 수 있습니다.")
                    
                    with st.expander("📐 피사체 위치 / 배율 / 회전 미세 변형 (Transform)", expanded=True):
                        c_tr1, c_tr2 = st.columns(2)
                        pos_x = sync_dual_control("가로 위치 (X)", -250, 250, 0, 1, base_key=f"l1_posx_{pid}")
                        pos_y = sync_dual_control("세로 위치 (Y)", -250, 250, 0, 1, base_key=f"l1_posy_{pid}")

                        c_tr3, c_tr4 = st.columns(2)
                        scale_pct = sync_dual_control("크기 배율 (%)", 30, 200, 100, 1, base_key=f"l1_scale_{pid}")
                        rotation_deg = sync_dual_control("회전 각도 (°)", -180, 180, 0, 1, base_key=f"l1_rot_{pid}")

                        c_fl1, c_fl2 = st.columns(2)
                        flip_h = c_fl1.checkbox("↔️ 좌우 반전 (Flip H)", value=False, key=f"l1_fliph_{pid}")
                        flip_v = c_fl2.checkbox("↕️ 상하 반전 (Flip V)", value=False, key=f"l1_flipv_{pid}")
                        feather_val = sync_dual_control("외곽선 페더 (Soft Edge)", 0.0, 5.0, 0.0, 0.1, base_key=f"l1_feath_{pid}", help_text="누끼 경계선을 부드럽게 감싸 배경과 자연스럽게 블렌딩합니다.")

                    with st.expander("🖌️ 마우스 직접 지우개 / 복구 브러시 캔버스 열기 (단축키: E, B, [ , ] )", expanded=False):
                        components.html(render_html5_eraser_canvas(target_cutout_b64, height=530), height=530)

                    up_erased = st.file_uploader(
                        "📥 지우개/외부 편집 완료된 이미지 올리기 (PNG, JPG, WebP)",
                        type=["png", "jpg", "jpeg", "webp"],
                        key=f"up_erased_{pid}",
                        help="포토샵, 포토룸, Bria 등 외부에서 직접 편집/리터칭한 이미지나 지우개로 수정한 사진을 올리면 상세페이지와 스튜디오에 즉시 반영됩니다."
                    )
                    if up_erased is not None:
                        _, up_durl = file_to_media_data_url(up_erased, auto_polish=False)
                        up_pil_check = base64_url_to_pil(up_durl)
                        is_up_cutout = is_already_cutout_png(up_pil_check)
                        if is_up_cutout:
                            pdata["fg_cutout_b64"] = up_durl
                        pdata["edited_img_b64"] = up_durl
                        pdata["cutout_v"] = "v7.0_custom_edited"
                        pdata["draft_html"] = _render_page(pdata)
                        # 멀티 갤러리에도 자동 동기화 추가
                        if not any(m.get("name") == up_erased.name for m in pdata.get("multi_images", [])):
                            pdata.setdefault("multi_images", []).append({
                                "name": up_erased.name,
                                "angle_label": "편집 완료 컷",
                                "b64": up_durl,
                                "polished_b64": up_durl,
                                "is_cutout": is_up_cutout,
                                "use_in_page": True
                            })
                        save_project(pid, pdata)
                        st.success("✅ 편집 이미지가 스튜디오 및 상세페이지에 즉시 반영되었습니다!")
                        st.rerun()

                    c_er1, c_er2 = st.columns(2)
                    erosion_px = sync_dual_control("테두리 조이기 (Erosion)", 0, 5, 1, 1, base_key=f"l1_ero_{pid}", help_text="외곽선을 1~5px 깎아 잔여 배경 테두리를 정리합니다.")
                    shadow_cut = sync_dual_control("그림자 강제 깎기 (HSV Cut)", 0, 100, 42, 1, base_key=f"l1_scut_{pid}", help_text="바닥 쪽 어둡고 채도 낮은 픽셀을 추가로 투명화합니다.")

                    if st.button("⚡ 외곽선/그림자 깎기 필터 즉시 적용", key=f"btn_hsv_cut_{pid}", use_container_width=True):
                        try:
                            polished_cutout = _erase_edge_shadow_hsv(fg_pil, shadow_threshold=int(shadow_cut), erosion_px=int(erosion_px))
                            pdata["fg_cutout_b64"] = pil_to_base64_url(polished_cutout, max_w=tw, fmt="PNG")
                            save_project(pid, pdata)
                            st.success("✅ 테두리 조이기 및 그림자 깎기가 적용되었습니다!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"처리 오류: {e}")

                    with st.expander("🔬 빛의 물리학 1·2: LAB 그림자 분리 & 화이트 헤일로 디프린지", expanded=True):
                        st.caption("AI 누끼 후 제품 바닥에 남은 진한 그림자를 물리학적으로 분리하고, 경계선 흰색 번짐을 100% 제거합니다.")
                        lab_shadow = sync_dual_control(
                            "바닥 그림자 물리 분리 강도 (LAB/색도)",
                            0, 100, 35, 1,
                            base_key=f"l1_labsh_{pid}",
                            help_text="원본 네 모서리 배경의 CIE LAB 값 및 정규화 색도(Chromaticity)를 기준으로 광도 불변 바닥 그림자를 부드럽게 감산합니다."
                        )

                        c_df1, c_df2 = st.columns(2)
                        defringe_on = c_df1.checkbox("🧼 테두리 디프린지 (Defringe)", value=True, key=f"l1_defr_on_{pid}", help="외곽선 반투명 픽셀에 순수 제품 내부 색상을 모폴로지 팽창 대체하여 흰색 테두리 번짐을 박멸합니다.")
                        choke_val = c_df2.slider("인워드 초크 수축 (px)", 0.0, 3.0, 0.8, 0.1, key=f"l1_choke_{pid}", help="알파 마스크를 0.5~2.5px 미세 수축시켜 외곽선 잔여 배경을 깎아냅니다.")
                        decontam_val = sync_dual_control("내부 색상 덮어씌움 강도", 0.0, 1.0, 1.0, 0.05, base_key=f"l1_decont_{pid}")

                        if st.button("⚡ LAB 그림자 분리 & 디프린지 영구 안착", key=f"btn_apply_lab_defr_{pid}", use_container_width=True):
                            try:
                                polished = separate_physical_shadow_lab(orig_pil, fg_pil, shadow_strength=int(lab_shadow))
                                polished = defringe_and_color_decontamination(polished, choke_px=float(choke_val), decontam_strength=float(decontam_val))
                                pdata["fg_cutout_b64"] = pil_to_base64_url(polished, max_w=tw, fmt="PNG")
                                save_project(pid, pdata)
                                st.success("✅ 물리 기반 그림자 분리 및 디프린지가 누끼 원본에 영구 반영되었습니다!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"오류 발생: {e}")

                # [레이어 2: 다중 배경 생성 & 3D 원형 단상]
                with tab_l2:
                    bg_mode_label = st.radio(
                        "배경 모드 선택",
                        [
                            "✨ 투명 배경 유지 (상세페이지 직통 융합 - 기본)",
                            "🌅 스튜디오 조명 & 단상(Podium) 생성",
                            "🖼️ 내 배경 이미지 직접 업로드 합성",
                            "🤖 AI 배경 생성 프롬프트"
                        ],
                        key=f"l2_bgmode_{pid}"
                    )

                    proc_style = "clean_white"
                    custom_bg_pil = None
                    dof_blur_px = 0
                    podium_enabled = False
                    podium_h = 55
                    podium_r = 220
                    podium_style = "clean_white"

                    if "스튜디오" in bg_mode_label:
                        proc_style = st.selectbox(
                            "스튜디오 조명 스타일 (7종 프리셋)",
                            [
                                "clean_white",
                                "dark_metallic",
                                "warm_wood",
                                "neon_tech",
                                "luxury_marble",
                                "soft_pastel",
                                "industrial_concrete",
                            ],
                            format_func=lambda s: {
                                "clean_white": "⚪ 클린 화이트 호리존 (순백색 ~ 소프트 그레이 미세 방사광)",
                                "dark_metallic": "⚫ 다크 메탈릭 스튜디오 (슬레이트 블랙 + 상단 스포트라이트)",
                                "warm_wood": "🪵 웜 우드 데스크 (따뜻한 오크 우드 + 앰비언트 라이트)",
                                "neon_tech": "🔷 네온 테크 사이버 (딥 네이비 + 사이언/블루 글로우)",
                                "luxury_marble": "🏛️ 럭셔리 마블 대리석 (화이트 대리석 은은한 마블 텍스처)",
                                "soft_pastel": "🌸 소프트 파스텔 스튜디오 (피치/로즈 ~ 스카이블루 감성)",
                                "industrial_concrete": "🧱 인더스트리얼 콘크리트 (쿨그레이 무광 인더스트리얼)",
                            }.get(s, s),
                            key=f"l2_proc_{pid}"
                        )

                        # 3D 원형 단상
                        podium_enabled = st.checkbox("🏛️ 3D 원형 단상(Podium) 받침대 생성", value=st.session_state.get(f"l2_pod_on_{pid}", False), key=f"l2_pod_on_{pid}")
                        if podium_enabled:
                            c_pd1, c_pd2 = st.columns(2)
                            podium_h = sync_dual_control("단상 높이(px)", 20, 120, 55, 1, base_key=f"l2_pod_h_{pid}")
                            podium_r = sync_dual_control("단상 너비(px)", 80, 350, 220, 5, base_key=f"l2_pod_r_{pid}")
                            podium_style = st.selectbox("단상 재질", ["clean_white", "dark_slate", "warm_gold"], format_func=lambda s: {"clean_white": "⚪ 화이트 스톤", "dark_slate": "⚫ 다크 슬레이트", "warm_gold": "👑 웜 골드"}.get(s, s), key=f"l2_pod_st_{pid}")

                    elif "업로드" in bg_mode_label:
                        c_bg_file = st.file_uploader("커스텀 배경 사진 업로드", type=["jpg", "png", "jpeg"], key=f"l2_bgfile_{pid}")
                        if c_bg_file:
                            custom_bg_pil = Image.open(c_bg_file)
                        dof_blur_px = sync_dual_control("배경 심도 아웃포커싱 (Gaussian Blur)", 0, 20, 4, 1, base_key=f"l2_blur_{pid}", help_text="배경을 흐리게 하여 피사체를 돋보이게 합니다.")
                    elif "AI 배경" in bg_mode_label:
                        st.text_input("AI 배경 프롬프트", value="clean minimalist commercial studio product table, cinematic lighting", key=f"l2_prompt_{pid}")
                        st.caption("💡 Fal.ai 또는 Clipdrop API 키가 등록되어 있으면 프롬프트에 맞춰 AI 배경을 생성합니다.")

                # [레이어 3: 포토룸 3종 그림자, 반사광 & 림라이트]
                with tab_l3:
                    light_dir = st.selectbox(
                        "☀️ 물리 광원 조명 방향 (역제곱 법칙)",
                        ["top", "top_left", "top_right"],
                        format_func=lambda s: {
                            "top": "☀️ 상단 수직 광원 (수직 접촉 밀착 + 중앙 Penumbra 확산)",
                            "top_left": "↖️ 좌상단 광원 (우하단 2중 확산 그림자)",
                            "top_right": "↗️ 우상단 광원 (좌하단 2중 확산 그림자)"
                        }.get(s, s),
                        key=f"l3_light_dir_{pid}"
                    )
                    c_sh1, c_sh2 = st.columns(2)
                    with c_sh1:
                        st.markdown("**① 바닥 접촉 그림자 (Contact AO)**")
                        contact_on = st.checkbox("접촉 그림자 사용 (공중부양 방지)", value=st.session_state.get(f"l3_con_on_{pid}", True), key=f"l3_con_on_{pid}")
                        contact_op = sync_dual_control("접촉 그림자 농도", 0.0, 1.0, 0.75, 0.05, base_key=f"l3_con_op_{pid}")
                        contact_sp = sync_dual_control("접촉 그림자 너비", 0.4, 1.2, 0.85, 0.05, base_key=f"l3_con_sp_{pid}")

                    with c_sh2:
                        st.markdown("**② 소프트 확산 섀도우 (Penumbra Cast)**")
                        amb_on = st.checkbox("확산 섀도우 사용", value=st.session_state.get(f"l3_amb_on_{pid}", True), key=f"l3_amb_on_{pid}")
                        amb_op = sync_dual_control("섀도우 농도", 0.0, 1.0, 0.35, 0.05, base_key=f"l3_amb_op_{pid}")
                        amb_blur = sync_dual_control("섀도우 번짐 (Blur)", 2, 60, 35, 1, base_key=f"l3_amb_bl_{pid}")
                        amb_x = sync_dual_control("광원 오프셋 (X)", -30, 30, 0, 1, base_key=f"l3_amb_x_{pid}")
                        amb_y = sync_dual_control("광원 높이 (Y)", 0, 40, 16, 1, base_key=f"l3_amb_y_{pid}")

                    st.markdown("---")
                    c_sc1, c_sc2 = st.columns(2)
                    with c_sc1:
                        st.markdown("**③ 3D 측면 투영 그림자 (3D Side Cast Shadow)**")
                        st.caption("포토룸 시그니처: 측면 광원에 의해 바닥으로 비스듬히 길게 드리워지는 고급 입체 그림자")
                        side_cast_on = st.checkbox("3D 측면 투영 그림자 켜기", value=st.session_state.get(f"l3_sc_on_{pid}", False), key=f"l3_sc_on_{pid}")
                        side_cast_ang = sync_dual_control("투영 각도 (°)", -80, 80, 30, 1, base_key=f"l3_sc_ang_{pid}")
                        side_cast_len = sync_dual_control("투영 길이 배율", 0.1, 1.0, 0.40, 0.05, base_key=f"l3_sc_len_{pid}")
                        side_cast_op = sync_dual_control("투영 투명도", 0.0, 1.0, 0.35, 0.05, base_key=f"l3_sc_op_{pid}")

                    with c_sc2:
                        st.markdown("**④ 바닥 반사광 & ⑤ 역광 림라이트**")
                        refl_on = st.checkbox("바닥 반사광 켜기 (전자기기/공구 고급 거울 반사)", value=st.session_state.get(f"l3_refl_on_{pid}", False), key=f"l3_refl_on_{pid}")
                        refl_op = sync_dual_control("반사광 투명도", 0.05, 0.80, 0.25, 0.05, base_key=f"l3_refl_op_{pid}") if refl_on else 0.0

                        st.markdown("#####")
                        rim_on = st.checkbox("역광 림라이트 켜기 (피사체 외곽 분리 발광)", value=st.session_state.get(f"l3_rim_on_{pid}", False), key=f"l3_rim_on_{pid}")
                        rim_col = "white"
                        rim_intens = 60
                        rim_spr = 7
                        if rim_on:
                            rim_col = st.selectbox("조명 색상", ["white", "gold", "cyan", "purple"], format_func=lambda s: {"white": "⚪ 순백색", "gold": "👑 웜 골드", "cyan": "🔷 네온 사이언", "purple": "🔮 네온 퍼플"}.get(s, s), key=f"l3_rim_col_{pid}")
                            rim_intens = sync_dual_control("조명 강도", 5, 100, 60, 5, base_key=f"l3_rim_int_{pid}")
                            rim_spr = sync_dual_control("번짐(px)", 3, 21, 7, 2, base_key=f"l3_rim_spr_{pid}")

                # [레이어 4: 스튜디오 색감 및 톤 매칭]
                with tab_l4:
                    c_lh1, c_lh2 = st.columns(2)
                    warm_cool = sync_dual_control("색온도 (쿨톤 ❄️ ↔ 🔥 웜톤)", -50, 50, 0, 1, base_key=f"l4_wc_{pid}")
                    clarity = sync_dual_control("선명도 / 클라리티", 0.80, 2.00, float(mood_preset.get("sharpness", 1.30)), 0.05, base_key=f"l4_cl_{pid}")

                    c_lh3, c_lh4 = st.columns(2)
                    contrast_val = sync_dual_control("명암비 (S-커브)", 0.70, 1.50, float(mood_preset.get("contrast", 1.12)), 0.02, base_key=f"l4_ct_{pid}")
                    vignette_val = sync_dual_control("주변부 비네팅 음영", 0, 80, 0, 1, base_key=f"l4_vg_{pid}")

                    st.markdown("---")
                    st.markdown("**✨ 빛의 물리학 4: 배경 환경광 역반사 & 색온도 동조화**")
                    c_lw1, c_lw2 = st.columns(2)
                    light_wrap_on = c_lw1.checkbox("배경 빛 역반사 (Light Wrap)", value=True, key=f"l4_lwrap_on_{pid}", help="배경 환경광을 제품 외곽선 안쪽 1~3px 영역에 Screen 방식으로 스며들게 합성합니다.")
                    temp_match_on = c_lw2.checkbox("배경 색온도 자동 동조화", value=True, key=f"l4_tmatch_on_{pid}", help="배경의 평균 색온도(Warm/Cool)를 측정하여 제품 하이라이트에 5~8% 미세 동조화합니다.")
                    wrap_strength = sync_dual_control("빛 역반사 투명도 (Light Wrap)", 0.0, 0.60, 0.25, 0.05, base_key=f"l4_lw_str_{pid}")

                # [레이어 5: 판매 촉진 배지 & 스티커]
                with tab_l5:
                    st.caption("🏷️ 포토룸 스타일 커머스 판매 촉진 배지 및 스티커를 제품 썸네일에 즉시 합성합니다.")
                    badge_on = st.checkbox("🏷️ 판매 촉진 배지/스티커 켜기", value=st.session_state.get(f"l5_badge_on_{pid}", False), key=f"l5_badge_on_{pid}")
                    badge_text = "🔥 BEST 1위"
                    badge_color = "red"
                    badge_pos = "top_left"
                    badge_scale = 1.0

                    if badge_on:
                        c_bd1, c_bd2 = st.columns([6, 4])
                        badge_preset_opt = c_bd1.selectbox(
                            "배지 문구 프리셋",
                            [
                                "🔥 BEST 1위",
                                "⚡ 1+1 기획 특가",
                                "🚚 무료 배송",
                                "KC 인증 완료",
                                "1년 무상 A/S",
                                "👑 프리미엄 품질",
                                "🎁 사은품 증정",
                                "50% OFF",
                                "✏️ 직접 텍스트 입력"
                            ],
                            key=f"l5_bd_sel_{pid}"
                        )
                        if "직접" in badge_preset_opt:
                            badge_text = c_bd1.text_input("직접 입력 문구", value="🔥 한정 수량", key=f"l5_bd_custom_{pid}")
                        else:
                            badge_text = badge_preset_opt

                        badge_color = c_bd2.selectbox(
                            "배지 색상 테마",
                            ["red", "gold", "blue", "dark", "green"],
                            format_func=lambda s: {
                                "red": "🔴 레드 (강렬한 할인/1위)",
                                "gold": "🟡 골드 (프리미엄/인증)",
                                "blue": "🔵 블루 (신뢰/배송/A/S)",
                                "dark": "⚫ 다크 (모던/블랙)",
                                "green": "🟢 그린 (친환경/안심)"
                            }.get(s, s),
                            key=f"l5_bd_col_{pid}"
                        )

                        c_bp1, c_bp2 = st.columns(2)
                        badge_pos = c_bp1.selectbox(
                            "배치 위치",
                            ["top_left", "top_right", "bottom_left", "bottom_right"],
                            format_func=lambda s: {
                                "top_left": "↖️ 좌측 상단",
                                "top_right": "↗️ 우측 상단",
                                "bottom_left": "↙️ 좌측 하단",
                                "bottom_right": "↘️ 우측 하단"
                            }.get(s, s),
                            key=f"l5_bd_pos_{pid}"
                        )
                        badge_scale = sync_dual_control("배지 크기 배율", 0.5, 2.0, 1.0, 0.05, base_key=f"l5_badge_sc_{pid}")

            # -----------------------------------------------------------
            # [우측: 실시간 비파괴 5-레이어 인메모리 합성 & 즉시 프리뷰]
            # -----------------------------------------------------------
            with col_s2:
                st.markdown(f"##### ✨ 포토룸급 5-레이어 스튜디오 완성본 ({tw}×{th}px)")

                # 인메모리 초고속 합성 실행 (<30ms)
                composite_result = composite_photocraft_layers(
                    fg_pil,
                    target_w=tw,
                    target_h=th,
                    bg_mode="transparent" if "투명" in bg_mode_label else ("procedural" if "스튜디오" in bg_mode_label else ("custom" if "업로드" in bg_mode_label else "clean_white")),
                    custom_bg_pil=custom_bg_pil,
                    bg_blur_px=int(dof_blur_px),
                    proc_style=proc_style,
                    fill_ratio=float(spec_t3.get("fill_ratio", 0.76)),
                    # 빛의 물리학 1 & 2: LAB 그림자 분리 & 디프린지
                    orig_pil=orig_pil,
                    lab_shadow_strength=int(lab_shadow),
                    defringe_enabled=bool(defringe_on),
                    choke_px=float(choke_val),
                    decontam_strength=float(decontam_val),
                    # Transform
                    pos_x=int(pos_x),
                    pos_y=int(pos_y),
                    scale_pct=float(scale_pct),
                    rotation=float(rotation_deg),
                    flip_h=bool(flip_h),
                    flip_v=bool(flip_v),
                    feather_px=float(feather_val),
                    # Podium
                    podium_enabled=bool(podium_enabled),
                    podium_height=int(podium_h),
                    podium_radius=int(podium_r),
                    podium_style=podium_style,
                    # 빛의 물리학 3: 역제곱 법칙 2중 물리 그림자 & 광원
                    light_direction=light_dir,
                    contact_enabled=bool(contact_on),
                    contact_opacity=float(contact_op),
                    contact_spread=float(contact_sp),
                    ambient_enabled=bool(amb_on),
                    ambient_x=int(amb_x),
                    ambient_y=int(amb_y),
                    ambient_blur=int(amb_blur),
                    ambient_opacity=float(amb_op),
                    reflection_enabled=bool(refl_on),
                    reflection_opacity=float(refl_op),
                    # 3D Side Cast Shadow (Photoroom)
                    side_cast_enabled=bool(side_cast_on),
                    side_cast_angle=float(side_cast_ang),
                    side_cast_length=float(side_cast_len),
                    side_cast_opacity=float(side_cast_op),
                    # Rim Light & 빛의 물리학 4: 라이트 랩 / 색온도 동조화
                    rim_light_enabled=bool(rim_on),
                    rim_color=rim_col,
                    rim_intensity=int(rim_intens),
                    rim_spread=int(rim_spr),
                    light_wrap_enabled=bool(light_wrap_on),
                    light_wrap_strength=float(wrap_strength),
                    temp_match_enabled=bool(temp_match_on),
                    # Sales Badges & Stickers (Photoroom)
                    badge_enabled=bool(badge_on),
                    badge_text=badge_text,
                    badge_color=badge_color,
                    badge_position=badge_pos,
                    badge_scale=float(badge_scale),
                    # Color & Tone
                    warm_cool=int(warm_cool),
                    clarity=float(clarity),
                    contrast=float(contrast_val),
                    vignette=int(vignette_val),
                )

                # 프리뷰 표시
                st.image(composite_result, use_container_width=True)

                # 즉시 저장 버튼 (원클릭)
                if st.button("💾 스튜디오 완성본 저장 & 상세페이지 직통 반영 (Ctrl+S)", type="primary", use_container_width=True, key=f"btn_save_studio_{pid}"):
                    is_trans = "투명" in bg_mode_label
                    pdata["edited_img_b64"] = pil_to_base64_url(composite_result, max_w=tw, fmt="PNG" if is_trans else "JPEG")
                    if is_trans:
                        pdata["fg_cutout_b64"] = pdata["edited_img_b64"]
                    pdata["cutout_v"] = "v7.0_photocraft_layered"
                    pdata["draft_html"] = _render_page(pdata)
                    save_project(pid, pdata)
                    st.success("✅ 스튜디오 편집본이 상세페이지와 프로젝트에 즉시 저장되었습니다! (단축키 Ctrl+S 지원)")
                    st.rerun()

                # 다운로드 버튼
                c_dl1, c_dl2 = st.columns(2)
                jpg_b = render_platform_thumbnail_bytes(composite_result, sel_plat_t3, "JPEG")
                png_b = render_platform_thumbnail_bytes(composite_result, sel_plat_t3, "PNG")
                c_dl1.download_button(f"📥 썸네일 JPG ({tw}×{th})", data=jpg_b, file_name=f"thumb_{tw}x{th}.jpg", mime="image/jpeg", use_container_width=True)
                c_dl2.download_button(f"📥 썸네일 PNG ({tw}×{th})", data=png_b, file_name=f"thumb_{tw}x{th}.png", mime="image/png", use_container_width=True)

                with st.popover("🤖 AI 엔진 & 작업 공정 리포트 보기"):
                    rep = pdata.get("photo_ai_report", {})
                    st.markdown(f"• **사용 엔진:** {rep.get('engine_used', 'PhotoCraft 5-Layer In-App Studio')}")
                    st.markdown(f"• **진단:** {rep.get('api_diagnosis', '정상 작동')}")
                    if rep.get("measured_size"):
                        st.markdown(f"• **실측:** {rep['measured_size']}")
                    st.markdown("**🛠️ 활성 레이어 & 빛의 물리학 파이프라인:**")
                    st.markdown(f"- **물리학 1 (그림자 분리):** CIE LAB & 색도 광도불변 감산 (강도 {lab_shadow})")
                    st.markdown(f"- **물리학 2 (디프린지):** Inward Choke ({choke_val}px) + 순수 내부색 팽창 ({'ON' if defringe_on else 'OFF'})")
                    st.markdown(f"- **물리학 3 (2중 그림자):** 조명 방향({light_dir}) · 접촉AO({contact_op:.2f}) · Penumbra({amb_op:.2f}, {amb_blur}px)")
                    st.markdown(f"- **물리학 4 (빛 역반사):** Fresnel Light Wrap ({wrap_strength:.2f}) · 색온도 동조화({'ON' if temp_match_on else 'OFF'})")
                    st.markdown(f"- **L2 (배경/단상):** {bg_mode_label} ({'3D 단상 ON' if podium_enabled else '단상 OFF'})")
                    st.markdown(f"- **L4 (톤/조명):** 색온도({warm_cool}) · 선명도({clarity:.2f}) · 대비({contrast_val:.2f}) · 비네팅({vignette_val})")
                    st.markdown(f"- **L5 (커머스 배지):** {'ON (' + badge_text + ')' if badge_on else 'OFF'}")
                    for stp in rep.get("process_steps", []):
                        st.markdown(f"- {stp}")

                with st.expander("📷 1단계 업로드 원본 사진 확인"):
                    st.image(orig_pil, use_container_width=True)

        render_photocraft_studio_fragment()

    # 3단계 하단 내비게이션
    st.markdown("---")
    c_nav_prev3, c_nav_next3 = st.columns(2)
    with c_nav_prev3:
        if st.button("⬅️ 2단계(TOP 10 분석 & 회의)로 돌아가기", use_container_width=True):
            st.session_state.active_step = 2
            st.rerun()
    with c_nav_next3:
        if st.button("💾 4단계 [상세페이지 빌더]로 이동 ➡️", type="primary", use_container_width=True):
            st.session_state.active_step = 4
            st.rerun()


# ---------------------------------------------------------------------
# [4단계: 🎬 상세페이지 빌더 & 다중 저장]
# ---------------------------------------------------------------------
elif st.session_state.active_step == 4:
    st.markdown("#### 🎬 4단계: 실시간 상세페이지 빌더 & 포토샵/일러스트 다중 저장소")
    col_b_ctl, col_b_vw = st.columns([4, 6], gap="large")

    with col_b_ctl:
        st.markdown("##### 🎨 디자인 테마 & 폰트 설정")
        th_keys = list(BRAND_THEMES.keys())
        cur_th = pdata.get("theme_color")
        cur_idx = th_keys.index(cur_th) if cur_th in th_keys else 0
        sel_th = st.selectbox("브랜드 테마 컬러", th_keys, index=cur_idx, key=f"theme_{pid}")
        pdata["theme_color"] = sel_th

        font_keys = list(MARKETER_FONTS.keys())
        c_f1, c_f2 = st.columns(2)
        t_font = c_f1.selectbox("제목 폰트", font_keys, index=font_keys.index(pdata.get("title_font")) if pdata.get("title_font") in font_keys else 1, key=f"tfont_{pid}")
        b_font = c_f2.selectbox("본문 폰트", font_keys, index=font_keys.index(pdata.get("body_font")) if pdata.get("body_font") in font_keys else 0, key=f"bfont_{pid}")
        pdata["title_font"] = t_font
        pdata["body_font"] = b_font

        with st.expander("🖼️ 편집 사진 즉시 상세페이지 반영 및 갤러리 관리", expanded=True):
            st.caption("외부 프로그램(포토샵, 캔바 등)에서 편집한 사진을 올리면 상세페이지 본문 갤러리에 즉시 반영됩니다.")
            up_direct_edit = st.file_uploader(
                "➕ 편집한 사진 파일 추가 (상세페이지 직통 반영)",
                type=["jpg", "jpeg", "png", "webp"],
                key=f"up_direct_edit_{pid}",
                help="업로드 즉시 상세페이지 본문의 실물 디테일 갤러리에 추가됩니다."
            )
            if up_direct_edit:
                _, durl_direct = file_to_media_data_url(up_direct_edit, auto_polish=False)
                if durl_direct and not any(m.get("name") == up_direct_edit.name for m in pdata.get("multi_images", [])):
                    up_p_check = base64_url_to_pil(durl_direct)
                    is_cut_d = is_already_cutout_png(up_p_check)
                    pdata.setdefault("multi_images", []).append({
                        "name": up_direct_edit.name,
                        "angle_label": "편집 디테일 컷",
                        "b64": durl_direct,
                        "polished_b64": durl_direct,
                        "is_cutout": is_cut_d,
                        "use_in_page": True
                    })
                    pdata["draft_html"] = _render_page(pdata)
                    save_project(pid, pdata)
                    st.success("✅ 편집 사진이 상세페이지 본문에 즉시 반영되었습니다!")
                    st.rerun()

            m_list_s4 = pdata.get("multi_images", [])
            if m_list_s4:
                st.caption(f"등록된 갤러리 사진 목록 ({len(m_list_s4)}장) - 체크 시 상세페이지 노출")
                for s4_idx, s4_item in enumerate(m_list_s4):
                    c_col1, c_col2, c_col3 = st.columns([2, 5, 3])
                    s4_pil = base64_url_to_pil(s4_item.get("polished_b64") or s4_item.get("b64"))
                    if s4_pil:
                        c_col1.image(s4_pil, width=60)
                    s4_lbl = c_col2.text_input(f"설명 #{s4_idx+1}", value=s4_item.get("angle_label", ""), key=f"s4_lbl_{pid}_{s4_idx}")
                    if s4_lbl != s4_item.get("angle_label"):
                        s4_item["angle_label"] = s4_lbl
                        pdata["draft_html"] = _render_page(pdata)
                        save_project(pid, pdata)
                    s4_chk = c_col3.checkbox("노출", value=s4_item.get("use_in_page", True), key=f"s4_chk_{pid}_{s4_idx}")
                    if s4_chk != s4_item.get("use_in_page", True):
                        s4_item["use_in_page"] = s4_chk
                        pdata["draft_html"] = _render_page(pdata)
                        save_project(pid, pdata)
                        st.rerun()

        with st.expander("🎬 본문 중간 미디어 삽입 (슬롯 1~3)", expanded=False):
            for s_num in [1, 2, 3]:
                st.caption(f"**슬롯 {s_num} (영상/GIF/사진)**")
                u_f = st.file_uploader(f"슬롯 {s_num} 파일 업로드", type=["jpg", "png", "gif", "mp4", "webm"], key=f"slot_{pid}_{s_num}_up")
                if u_f:
                    mtype, mdurl = file_to_media_data_url(u_f, auto_polish=True)
                    pdata[f"slot{s_num}_media"]["type"] = mtype
                    pdata[f"slot{s_num}_media"]["data"] = mdurl
                    pdata["draft_html"] = _render_page(pdata)
                    save_project(pid, pdata)
                cap_v = st.text_input(f"슬롯 {s_num} 캡션", value=pdata[f"slot{s_num}_media"].get("caption", ""), key=f"slot_{pid}_{s_num}_cap")
                if cap_v != pdata[f"slot{s_num}_media"].get("caption", ""):
                    pdata[f"slot{s_num}_media"]["caption"] = cap_v
                    pdata["draft_html"] = _render_page(pdata)
                    save_project(pid, pdata)

        with st.expander("🔀 9단계 섹션 순서 빠른 이동", expanded=False):
            st.caption("▲ / ▼ 버튼으로 전체 섹션 순서를 위아래로 재배치할 수 있습니다. (우측 미리보기 화면에서 마우스로 직접 잡고 드래그 이동도 가능합니다)")
            steps_list = pdata.get("nine_steps", [])
            for s_i, stp_obj in enumerate(steps_list):
                c_st_title, c_st_u, c_st_d = st.columns([7, 1.5, 1.5])
                c_st_title.write(f"**{s_i+1}.** {stp_obj.get('role', f'STEP {s_i+1}')}")
                if c_st_u.button("▲", key=f"stp_up_{pid}_{s_i}", disabled=(s_i == 0)):
                    steps_list[s_i - 1], steps_list[s_i] = steps_list[s_i], steps_list[s_i - 1]
                    pdata["nine_steps"] = steps_list
                    pdata["draft_html"] = _render_page(pdata)
                    save_project(pid, pdata)
                    st.rerun()
                if c_st_d.button("▼", key=f"stp_dn_{pid}_{s_i}", disabled=(s_i == len(steps_list) - 1)):
                    steps_list[s_i + 1], steps_list[s_i] = steps_list[s_i], steps_list[s_i + 1]
                    pdata["nine_steps"] = steps_list
                    pdata["draft_html"] = _render_page(pdata)
                    save_project(pid, pdata)
                    st.rerun()

        if st.button("✍️ 감각적인 전문 브랜드 카피로 1초 재작성", use_container_width=True):
            pdata["nine_steps"] = get_default_9steps(msize=pdata.get("manual_size", ""), kw=pdata.get("keyword", ""))
            pdata["draft_html"] = _render_page(pdata)
            save_project(pid, pdata)
            st.success("✅ 상위 1% 전문 브랜드 쇼핑몰 스타일로 카피가 자연스럽게 재작성되었습니다!")
            st.rerun()

        if st.button("🔄 상세페이지 새로고침 반영", type="primary", use_container_width=True):
            pdata["draft_html"] = _render_page(pdata)
            save_project(pid, pdata)
            st.rerun()

        st.markdown("##### 💾 다중 저장 및 내보내기")
        cur_html = pdata.get("draft_html") or _render_page(pdata)
        st.download_button(
            "📥 완성 HTML 다운로드",
            data=cur_html.encode("utf-8"),
            file_name=f"{pdata.get('title','product')}_detail.html",
            mime="text/html",
            use_container_width=True,
            type="primary"
        )

        psd_zip = create_design_tool_package_zip(pdata)
        st.download_button(
            "📦 포토샵(PSD)·일러스트(SVG) 레이어 에셋 ZIP 다운로드",
            data=psd_zip,
            file_name=f"{pdata.get('title','product')}_design_package.zip",
            mime="application/zip",
            use_container_width=True
        )

    with col_b_vw:
        st.markdown("##### 👁️ 실시간 인터랙티브 상세페이지 (마우스 클릭 직접 수정 가능)")
        cur_html = pdata.get("draft_html") or _render_page(pdata)
        st.components.v1.html(cur_html, height=850, scrolling=True)

    # 4단계 하단 내비게이션
    st.markdown("---")
    if st.button("⬅️ 3단계(AI 미디어 스튜디오)로 돌아가기", use_container_width=True):
        st.session_state.active_step = 3
        st.rerun()
