# trendforge_app.py
# TrendForge AI — Content Pack Builder (Single + Bulk) with polished UI
# Drop-in: no external assets required. Replace `generate_pack()` with your real LLM call when ready.

import streamlit as st
import textwrap, io, zipfile
from datetime import datetime

# ---------- Page ----------
st.set_page_config(
    page_title="TrendForge AI — Content Pack Builder",
    page_icon="✨",
    layout="wide"
)

# ---------- Theme / CSS ----------
BRAND_PRIMARY = "#2563eb"   # blue
BRAND_ACCENT  = "#22c55e"   # green
CARD_BG       = "#0b1220"
CARD_LINE     = "#22314a"

st.markdown(f"""
<style>
/* page bg */
.stApp {{ background: linear-gradient(180deg,#0f172a 0%,#0b1220 50%,#0b0f14 100%); }}

/* center container */
.container {{ max-width: 1050px; margin: 0 auto; padding: 8px 16px 40px; }}

/* badge */
.tg-badge {{
  display:inline-flex; align-items:center; gap:10px;
  background:#0b1220; border:1px solid {CARD_LINE};
  color:#e6edf8; font-weight:800; padding:10px 14px; border-radius:14px;
  box-shadow:0 18px 50px rgba(0,0,0,.35);
}}
/* card */
.tg-card {{
  background:{CARD_BG}; border:1px solid {CARD_LINE}; border-radius:16px;
  padding:18px; box-shadow:0 28px 80px rgba(0,0,0,.35); color:#e6edf8;
}}
.tg-card h3 {{ margin:0 0 8px; }}
.tg-sub {{ color:#a6b0c3; margin:0 0 14px; }}

/* inputs */
.stTextInput input, .stTextArea textarea, .stSelectbox div[data-baseweb="select"] > div {{
  background:#0e1520 !important; color:#eaf1f7 !important;
  border:1px solid #2b3a4e !important; border-radius:12px !important;
}}
.stTextArea textarea {{ min-height: 140px !important; }}

/* download row */
.dl-row {{ display:flex; flex-wrap:wrap; gap:10px; }}

/* dividers */
hr.split {{ border:0; border-top:1px solid {CARD_LINE}; margin:26px 0; }}

/* pill */
.pill {{ display:inline-block; padding:6px 10px; border-radius:999px;
  font-size:12px; font-weight:700; background:#ecfeff; color:#155e75; border:1px solid #a5f3fc; }}
</style>
""", unsafe_allow_html=True)

# ---------- Fake generator (swap with your model) ----------
def generate_pack(topic: str, niche: str, audience: str, tone: str, platform: str) -> str:
    """
    Return a markdown content pack.
    ❗ Replace this with your real LLM call; keep the same return (markdown str).
    """
    hooks = "\n".join([f"{i+1}. A sharp, scroll-stopping hook tied to **{topic}**"
                       for i in range(10)])
    md = f"""
# Content Pack — {topic} ({platform.title()})
_Niche_: **{niche}**  
_Audience_: **{audience}**  
_Tone_: **{tone}**

---

## 10 Hook Ideas
{hooks}

## 5 Concepts to Film
- POV/tutorial about {topic} for {audience}
- Duet/react to a trending creator in {niche}
- Before/after sequence relevant to {topic}
- Myth vs Fact carousel
- Quick wins: 3-step mini-guide

## Captions (with CTAs)
- “Tried this? Comment **YES** or **NO** 👇”
- “Save this so you don’t forget 💾”
- “DM me ‘{topic.split()[0].lower()}’ for the template”

## Hashtags
#{platform} #{niche.replace(" ", "")} #contentpack #trendforge

---
Generated: {datetime.utcnow().isoformat()}Z
"""
    return textwrap.dedent(md)

def bytes_markdown(md_text: str) -> bytes:
    buf = io.BytesIO()
    buf.write(md_text.encode("utf-8"))
    return buf.getvalue()

# ---------- Header ----------
st.markdown('<div class="container">', unsafe_allow_html=True)
st.markdown(
    '''
    <div style="display:flex;align-items:center;justify-content:space-between;margin:16px 0 10px;">
      <div class="tg-badge">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="#2563eb" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path d="M12 2l2.39 4.84L20 8.27l-4 3.9.94 5.49L12 15.77 7.06 17.66 8 12.17 4 8.27l5.61-1.43L12 2z"/>
        </svg>
        TrendForge AI
      </div>
      <div><span class="pill">Beta</span></div>
    </div>
    ''',
    unsafe_allow_html=True
)

# ---------- SINGLE PACK ----------
st.markdown('<div class="tg-card">', unsafe_allow_html=True)
st.markdown("### TrendForge AI — Content Pack Builder")
st.markdown('<p class="tg-sub">Generate a polished content pack for TikTok, Instagram, or YouTube.</p>', unsafe_allow_html=True)

left, right = st.columns([1.05, 0.95], gap="large")
with left:
    with st.form("single_form", clear_on_submit=False):
        topic    = st.text_input("Topic", placeholder="fall makeup trends 2025")
        niche    = st.text_input("Niche", placeholder="beauty creators")
        audience = st.text_input("Audience", placeholder="women 18–30")
        tone     = st.text_input("Tone", placeholder="energetic, helpful")
        platform = st.selectbox("Platform", ["tiktok", "instagram", "youtube"], index=0)
        run_single = st.form_submit_button("Generate Pack", use_container_width=True)

    if run_single:
        if not all([topic, niche, audience, tone]):
            st.warning("Please fill in all fields.")
        else:
            with st.spinner("Crafting your pack…"):
                md = generate_pack(topic, niche, audience, tone, platform)
            st.success("Your content pack is ready 🎉")
            st.markdown("#### Preview")
            st.code(md, language="markdown")
            fname = f"TF_{platform}_{topic.strip().replace(' ','_')}.md"
            st.markdown('<div class="dl-row">', unsafe_allow_html=True)
            st.download_button("⬇️ Download Markdown", data=bytes_markdown(md),
                               file_name=fname, mime="text/markdown")
            st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown(
        """
        <div style="background:#0e1520;border:1px dashed #334155;border-radius:14px;padding:14px;">
          <div style="font-weight:800;margin-bottom:6px;">Preview tips</div>
          <ul style="color:#a8b3c7;margin:0 0 0 18px;">
            <li>Try different tones: “educational”, “story-driven”, “humorous”.</li>
            <li>Switch platform to adjust hooks/hashtags.</li>
            <li>Use Bulk Packs below to generate dozens at once.</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("</div>", unsafe_allow_html=True)  # end single card
st.markdown('<hr class="split" />', unsafe_allow_html=True)

# ---------- BULK PACKS ----------
st.markdown('<div class="tg-card">', unsafe_allow_html=True)
st.markdown("### Bulk Packs")
st.markdown('<p class="tg-sub">Paste one topic per line. We’ll generate a pack for each and give you a ZIP.</p>', unsafe_allow_html=True)

b1, b2 = st.columns([1.05, 0.95], gap="large")
with b1:
    with st.form("bulk_form", clear_on_submit=False):
        topics_raw = st.text_area("Topics (one per line)",
                                  placeholder="fall makeup trends 2025\nbeginner skincare routine\nsmokey eye tutorial")
        niche_b     = st.text_input("Niche", placeholder="beauty creators", key="bn")
        audience_b  = st.text_input("Audience", placeholder="women 18–30", key="ba")
        tone_b      = st.text_input("Tone", placeholder="energetic, helpful", key="bt")
        platform_b  = st.selectbox("Platform", ["tiktok","instagram","youtube"], index=0, key="bp")
        run_bulk = st.form_submit_button("Generate Bulk ZIP", use_container_width=True)

    if run_bulk:
        topics = [t.strip() for t in topics_raw.splitlines() if t.strip()]
        if not topics:
            st.warning("Add at least one topic.")
        elif not (niche_b and audience_b and tone_b):
            st.warning("Please fill in niche, audience, and tone.")
        else:
            zip_buf = io.BytesIO()
            prog = st.progress(0, text=f"0/{len(topics)} packs")
            with zipfile.ZipFile(zip_buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
                for i, t in enumerate(topics, start=1):
                    with st.spinner(f"Generating: {t}"):
                        md = generate_pack(t, niche_b, audience_b, tone_b, platform_b)
                    zf.writestr(f"TF_{platform_b}_{t.replace(' ','_')}.md", md)
                    prog.progress(i/len(topics), text=f"{i}/{len(topics)} packs")
            st.success(f"Done! {len(topics)} packs generated.")
            st.download_button(
                "⬇️ Download ZIP",
                data=zip_buf.getvalue(),
                file_name=f"trendforge_bulk_{platform_b}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip"
            )

with b2:
    st.markdown(
        """
        <div style="background:#0e1520;border:1px dashed #334155;border-radius:14px;padding:14px;">
          <div style="font-weight:800;margin-bottom:6px;">Bulk tips</div>
          <ul style="color:#a8b3c7;margin:0 0 0 18px;">
            <li>Stick to one niche per bulk run for consistent tone.</li>
            <li>Use short, specific topics (5–8 words works best).</li>
            <li>ZIP includes a separate .md file for each topic.</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True
    )

st.markdown("</div>", unsafe_allow_html=True)  # end bulk card
st.markdown("</div>", unsafe_allow_html=True)  # end container
