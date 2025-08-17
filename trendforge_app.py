# trendforge_app.py  —  TrendForge AI (fixed)
# ---------------------------------------------------------
# - keeps your white spacer bars
# - fixes USER_ID
# - single + bulk progress bars
# - bulk ZIP download
# - hides duplicate Streamlit header bar
# ---------------------------------------------------------

import os, io, time, json, unicodedata, random, re, hashlib, uuid, datetime as dt
from pathlib import Path
from collections import defaultdict

import streamlit as st
import requests  # make sure 'requests' is in requirements.txt

# (Optional) .env support; ignore if not present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# =====================  Brand / Paths  =====================
ASSETS = Path("./assets"); ASSETS.mkdir(exist_ok=True)
OUT    = Path("./content_packs"); OUT.mkdir(exist_ok=True)

TF_BRAND_NAME    = "TrendForge AI"
TF_PRIMARY_HEX   = "#1E88E5"  # deep blue
TF_SECONDARY_HEX = "#FFB300"  # amber
TF_BG_HEX        = "#F5F7FA"
TF_WATERMARK_OFFLINE = "Generated in Offline Mode"

# simple logo generator if missing
from PIL import Image, ImageDraw, ImageFont
def make_trendforge_logo(path: Path):
    W, H = 360, 96
    img = Image.new("RGBA", (W, H), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0,0),(W,H)], fill=(30,136,229,255))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    text = "TrendForge AI"
    tw, th, *_ = draw.textbbox((0,0), text, font=font)
    draw.text(((W-tw)//2, (H-th)//2), text, font=font, fill=(255,255,255,255))
    img.save(path)

LOGO_PATH = ASSETS / "trendforge_logo.png"
if not LOGO_PATH.exists():
    make_trendforge_logo(LOGO_PATH)

# =====================  Fonts / PDF  =====================
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def _register_unicode_fonts() -> bool:
    try:
        pdfmetrics.registerFont(TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
        pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
        return True
    except Exception:
        return False
_HAS_UNI = _register_unicode_fonts()
FONT_BODY = "DejaVuSans" if _HAS_UNI else "Helvetica"
FONT_BOLD = "DejaVuSans-Bold" if _HAS_UNI else "Helvetica-Bold"
PAGE_W, PAGE_H = letter
MARGIN = 0.7 * inch
CONTENT_W = PAGE_W - 2*MARGIN

def _san(s):
    t = unicodedata.normalize("NFKC", str(s or ""))
    if not _HAS_UNI:
        t = t.replace("•","- ").replace("–","-").replace("—","-").replace("-","-")
    return t

# =====================  ENV / Secrets  =====================
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY", "")
LZS_API_KEY      = os.getenv("LZS_API_KEY", "")
LZS_PRODUCT_ID   = os.getenv("LZS_PRODUCT_ID", "")
LICENSE_REQUIRED = os.getenv("LICENSE_REQUIRED", "false").lower() == "true"
FREE_DAILY_LIMIT = int(os.getenv("FREE_DAILY_LIMIT", "3"))
PRO_DAILY_LIMIT  = int(os.getenv("PRO_DAILY_LIMIT", "50"))
CHECKOUT_URL     = os.getenv("CHECKOUT_URL", "https://example.com")

# --- session/user id (fixes USER_ID error) ---
def _session_id():
    sid = st.session_state.get("_sid")
    if not sid:
        sid = hashlib.sha1(uuid.uuid4().hex.encode()).hexdigest()[:12]
        st.session_state["_sid"] = sid
    return sid
USER_ID = os.getenv("USER_ID", _session_id())

# =====================  Licensing (optional)  =====================
def validate_license(license_key: str) -> bool:
    """Returns True if license is valid for your product, else False."""
    if not (license_key and LZS_API_KEY and LZS_PRODUCT_ID):
        return False
    try:
        url = "https://api.lemonsqueezy.com/v1/licenses/validate"
        headers = {"Authorization": f"Bearer {LZS_API_KEY}", "Accept": "application/json"}
        payload = {"license_key": license_key, "product_id": int(LZS_PRODUCT_ID)}
        r = requests.post(url, json=payload, headers=headers, timeout=12)
        data = r.json()
        return bool(data.get("meta", {}).get("valid", False))
    except Exception:
        return False

# =====================  Helpers  =====================
BLOCKED = {"hate", "violent harm", "self-harm"}
def is_allowed(text: str) -> bool:
    t = (text or "").lower()
    return not any(b in t for b in BLOCKED)

def with_retry(fn, tries: int = 3, delay: float = 0.6):
    for i in range(tries):
        try:
            return fn()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(delay * (2**i))

def normalize_pack(hooks, captions, hashtags, plan):
    hooks = (hooks or [])[:10]; hooks += [""]*(10-len(hooks))
    captions = (captions or [])[:10]; captions += [""]*(10-len(captions))
    hashtags = (hashtags or [])[:30]; hashtags += [""]*(30-len(hashtags))
    plan = (plan or [])[:7]
    if len(plan) < 7:
        plan += [{"day": len(plan)+i+1, "post":"", "note":""} for i in range(7-len(plan))]
    return hooks, captions, hashtags, plan

# quota (simple per-process)
USER_QUOTA = defaultdict(int)
DAILY_LIMIT_FALLBACK = int(os.getenv("DAILY_LIMIT", "10"))
def _quota_key(user_id):
    return f"{user_id}:{dt.date.today().isoformat()}"
def check_quota(user_id: str, count: int = 1):
    key = _quota_key(user_id)
    if USER_QUOTA[key] + count > st.session_state.get("DAILY_LIMIT", DAILY_LIMIT_FALLBACK):
        raise RuntimeError("Daily limit reached. Upgrade for more.")
    USER_QUOTA[key] += count

# =====================  Content Generation  =====================
PLATFORM_TIPS = {
    "tiktok": ["Hook in the first 1.5s", "Use text overlay with a bold promise", "Keep jump-cuts 1–2s", "Use trending audio under VO"],
    "instagram": ["Front-load keywords in first caption line", "Use 4:5 or square for reach", "Pin best comment for saves", "Carousels perform well for tutorials"],
    "youtube": ["Hook + payoff preview within 3s", "Add a pattern interrupt at 5–7s", "Pair Shorts with related long-form", "Strong end-card CTA"],
}

USE_AI = bool(OPENAI_API_KEY)

def offline_generate(topic, niche, audience, tone, platform):
    random.seed(topic + niche + (audience or "") + (tone or "") + platform)
    verbs  = ["Unlock","Try","Avoid","Master","Discover","Boost","Fix","Start","Stop","Learn"]
    angles = ["in 60 seconds","no one told you","beginners need","pros swear by","on a budget","without fancy gear"]
    hooks = [f"{random.choice(verbs)} {topic} {random.choice(angles)}" for _ in range(10)]
    captions = [f"{(tone or 'Helpful').title()} take: {topic} for {niche}. Save this! 🔖" for _ in range(10)]
    tags = [f"#{w.replace(' ','')}" for w in (niche.split() + topic.split()) if w][:10]
    extra = ["#fyp","#viral","#howto","#tutorial","#learnontiktok","#reels","#shorts","#contenttips","#creator","#trending"]
    hashtags = (tags + extra)[:30]
    plan = [{"day": i+1, "post": hooks[i], "note": "Use b-roll + captions; clear CTA."} for i in range(7)]
    return hooks, captions, hashtags, plan

def ai_generate(topic, niche, audience, tone, platform):
    if not USE_AI:
        return offline_generate(topic, niche, audience, tone, platform)
    try:
        import openai
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        prompt = f'''
Create a short-form content pack for "{topic}" in the "{niche}" niche for the "{platform}" platform.
Audience: {audience or "general creators"}. Tone: {tone or "friendly and direct"}.
Return JSON with keys: hooks (10), captions (10), hashtags (30), plan (7 items).
Each hook <= 12 words; captions 1–2 sentences; plan items have fields day, post, note.
'''
        resp = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role":"system","content":"You are a concise social media strategist. Avoid filler; be specific."},
                {"role":"user","content":prompt}
            ],
            temperature=0.7,
        )
        text = resp.choices[0].message.content or ""
        start, end = text.find("{"), text.rfind("}")
        if start!=-1 and end!=-1:
            data = json.loads(text[start:end+1])
            return (
                data.get("hooks", []),
                data.get("captions", []),
                data.get("hashtags", []),
                data.get("plan", []),
            )
        return offline_generate(topic, niche, audience, tone, platform)
    except Exception as e:
        st.warning(f"AI disabled this run → {e}")
        return offline_generate(topic, niche, audience, tone, platform)

def build_markdown(topic, niche, audience, tone, platform, hooks, captions, hashtags, plan):
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    md = [f"# Content Pack — {topic} ({platform.title()})",
          f"**Niche:** {niche}  ",
          f"**Audience:** {audience or 'General'}  ",
          f"**Tone:** {tone or 'Friendly'}  ",
          f"_Generated: {now}_",
          "\n---\n",
          "## 🔥 Hooks (10)\n"]
    for i, h in enumerate(hooks[:10], 1): md.append(f"{i}. {h}")
    md += ["\n## ✍️ Captions (10)\n"]
    for i, c in enumerate(captions[:10], 1): md.append(f"{i}. {c}")
    md += ["\n## #️⃣ Hashtags (30)\n", " ".join(hashtags[:30])]
    md += ["\n## 🗓️ 7-Day Posting Plan\n"]
    for item in plan[:7]:
        md.append(f"- **Day {item.get('day')}** — {item.get('post')}  \n  _Note:_ {item.get('note')}")
    tips = PLATFORM_TIPS.get(platform.lower(), [])
    if tips:
        md += ["\n## 🧠 Platform Tips\n"]
        for t in tips: md.append(f"- {t}")
    return "\n".join(md)

def build_trendforge_pdf(pdf_path: Path, *, topic, niche, audience, tone, platform,
                         hooks, captions, hashtags, plan, tips, ai_used: bool):
    styles = getSampleStyleSheet()
    H_TITLE = ParagraphStyle("H_TITLE", parent=styles["Title"], fontName=FONT_BOLD, fontSize=22,
                             textColor=colors.black, spaceAfter=12, leading=26)
    P_BODY  = ParagraphStyle("P_BODY",  parent=styles["BodyText"], fontName=FONT_BODY, fontSize=10, leading=14)
    P_SMALL = ParagraphStyle("P_SMALL", parent=styles["BodyText"], fontName=FONT_BODY, fontSize=8,  leading=11, textColor=colors.gray)

    def _on_page(c, doc):
        c.saveState()
        c.setFillColor(colors.HexColor(TF_PRIMARY_HEX))
        c.rect(0, PAGE_H - 0.9*inch, PAGE_W, 0.9*inch, fill=1, stroke=0)
        try:
            c.drawImage(str(LOGO_PATH), MARGIN, PAGE_H - 0.83*inch, width=1.8*inch, height=0.48*inch, mask='auto')
        except Exception:
            pass
        c.setFillColor(colors.white)
        c.setFont(FONT_BOLD, 13)
        c.drawString(MARGIN + 2.0*inch + 6, PAGE_H - 0.55*inch, _san(TF_BRAND_NAME))
        c.setFont(FONT_BODY, 9)
        c.drawRightString(PAGE_W - MARGIN, PAGE_H - 0.55*inch, dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
        c.restoreState()

        c.saveState()
        c.setFont(FONT_BODY, 8)
        c.setFillColor(colors.gray)
        c.drawRightString(PAGE_W - MARGIN, 0.5*inch, f"Page {doc.page}")
        c.restoreState()

        if not ai_used:
            c.saveState()
            c.setFillColorRGB(0.90, 0.90, 0.90)
            c.setFont("Helvetica", 42)
            c.translate(PAGE_W/2, PAGE_H/2)
            c.rotate(35)
            c.drawCentredString(0, 0, TF_WATERMARK_OFFLINE)
            c.restoreState()

    doc = SimpleDocTemplate(str(pdf_path), pagesize=letter,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    flow = []

    cover_tbl = Table(
        [[Paragraph(_san("Content Strategy Pack"), H_TITLE)],
         [Paragraph(_san(f"Topic: {topic}"), P_BODY)],
         [Paragraph(_san(f"Niche: {niche}  |  Audience: {audience or 'General'}  |  Tone: {tone or 'Friendly'}"), P_SMALL)],
         [Paragraph(_san(f"Platform: {platform.title()}  |  Mode: {'AI Enhanced' if ai_used else 'Offline'}"), P_SMALL)]],
        colWidths=[CONTENT_W]
    )
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor(TF_BG_HEX)),
        ("BOX",(0,0),(-1,-1),0.25,colors.HexColor(TF_PRIMARY_HEX)),
        ("INNERGRID",(0,0),(-1,-1),0.25,colors.HexColor("#E0E6EF")),
        ("LEFTPADDING",(0,0),(-1,-1),10), ("RIGHTPADDING",(0,0),(-1,-1),10),
        ("TOPPADDING",(0,0),(-1,-1),10),  ("BOTTOMPADDING",(0,0),(-1,-1),10),
    ]))
    flow += [cover_tbl, Spacer(1, 0.2*inch)]

    def divider(title: str):
        bar = Table([[Paragraph(_san(title), ParagraphStyle("BAR", fontName=FONT_BOLD, fontSize=12, textColor=colors.white))]],
                    colWidths=[CONTENT_W])
        bar.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,-1),colors.HexColor(TF_PRIMARY_HEX)),
            ("LEFTPADDING",(0,0),(-1,-1),10),
            ("TOPPADDING",(0,0),(-1,-1),6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6),
        ]))
        flow.extend([Spacer(1, 0.08*inch), bar, Spacer(1, 0.12*inch)])

    divider("Executive Summary")
    summary_text = f"This pack includes hooks, captions, hashtags, and a 7-day plan tailored for {platform.title()} creators in the {niche} niche."
    flow.append(Paragraph(_san(summary_text), P_BODY))

    divider("Hooks (10)")
    for i, h in enumerate(hooks[:10], 1):
        flow.append(Paragraph(_san(f"{i}. {h}"), P_BODY))

    divider("Captions (10)")
    for i, c in enumerate(captions[:10], 1):
        flow.append(Paragraph(_san(f"{i}. {c}"), P_BODY))

    divider("Hashtags (30)")
    tags = (hashtags or [])[:30]
    cols = 3
    rows = []
    padded = tags + [""] * ((cols - (len(tags) % cols)) % cols)
    for i in range(0, len(padded), cols):
        rows.append([Paragraph(_san(padded[i + j]), P_BODY) for j in range(cols)])
    tag_table = Table(rows, colWidths=[CONTENT_W/3]*3)
    tag_table.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#E0E6EF")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    flow.append(tag_table)

    divider("7-Day Posting Plan")
    head = ["Day","Post Idea","Notes"]
    rows = [[str(it.get("day")), _san(it.get("post","")), _san(it.get("note",""))] for it in (plan or [])[:7]]
    t = Table([head] + rows, colWidths=[0.6*inch, 3.9*inch, CONTENT_W - (0.6*inch + 3.9*inch)])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor(TF_SECONDARY_HEX)),
        ("TEXTCOLOR",(0,0),(-1,0),colors.black),
        ("FONT",(0,0),(-1,0),FONT_BOLD,10),
        ("FONT",(0,1),(-1,-1),FONT_BODY,10),
        ("GRID",(0,0),(-1,-1),0.25,colors.HexColor("#E0E6EF")),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    flow.append(t)

    divider(f"{platform.title()} Tips")
    for tip in (PLATFORM_TIPS.get(platform.lower(), []) or [])[:6]:
        flow.append(Paragraph(_san("• " + tip), P_BODY))

    divider("Appendix")
    flow.append(Paragraph(_san(f"Mode: {'AI Enhanced' if ai_used else 'Offline'}. Generated by {TF_BRAND_NAME}."), P_SMALL))

    doc.build(flow, onFirstPage=_on_page, onLaterPages=_on_page)

def generate_one(topic, niche, audience, tone, platform):
    """Returns (markdown_text, pdf_bytes, base_filename) for one pack."""
    use_ai = bool(OPENAI_API_KEY)
    if use_ai:
        hooks, captions, hashtags, plan = ai_generate(topic, niche, audience, tone, platform)
    else:
        hooks, captions, hashtags, plan = offline_generate(topic, niche, audience, tone, platform)

    hooks, captions, hashtags, plan = normalize_pack(hooks, captions, hashtags, plan)
    md = build_markdown(topic, niche, audience, tone, platform, hooks, captions, hashtags, plan)

    safe = re.sub(r"[^A-Za-z0-9_\-]+", "_", topic)[:40]
    base = f"TrendForge_{platform}_{safe}"

    pdf_path = OUT / f"{base}.pdf"
    build_trendforge_pdf(
        pdf_path=pdf_path,
        topic=topic, niche=niche, audience=audience, tone=tone, platform=platform,
        hooks=hooks, captions=captions, hashtags=hashtags, plan=plan,
        tips=PLATFORM_TIPS.get(platform.lower(), []),
        ai_used=use_ai
    )
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    return md, pdf_bytes, base

# =====================  UI  =====================
st.set_page_config(page_title="TrendForge AI — Content Pack Builder", page_icon="🎨", layout="wide")

st.markdown("""
<style>
.white-bar{
  height:18px;
  background:#ffffff;
  border-radius:10px;
  margin:10px 0;
  opacity:.9;
}
</style>
""", unsafe_allow_html=True)

# Hide Streamlit’s default top header (prevents duplicate bar)
st.markdown("""
<style>
header { visibility: hidden; height: 0; }
</style>
""", unsafe_allow_html=True)

col_logo, col_title = st.columns([1,3])
with col_logo:
    st.image(str(LOGO_PATH), width=200)
with col_title:
    st.title("TrendForge AI — Content Pack Builder")
    st.caption("Generate PDF + Markdown packs for TikTok, Instagram, and YouTube.")

# Simple per-session counter
if "USED_TODAY" not in st.session_state:
    st.session_state["USED_TODAY"] = 0

# Styles
st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1100px;}
.tg-card {border:1px solid #E6EAF2;border-radius:16px;padding:18px;background:#ffffff;
          box-shadow:0 4px 14px rgba(16,24,40,0.06);margin-bottom:16px;}
.tg-badge {display:inline-block;padding:4px 10px;border-radius:999px;background:#E6F0FF;color:#1E88E5;
           font-weight:600;font-size:.82rem;margin-left:8px;}
section[data-testid="stSidebar"] {width: 340px !important; border-right: 1px solid #EEF1F6;}
.stButton>button {border-radius:12px;padding:.6rem 1rem;font-weight:700}
</style>
""", unsafe_allow_html=True)

# Title row badge (shows PRO when valid key was entered)
title_col1, title_col2 = st.columns([3,1])
with title_col1:
    st.title("TrendForge AI — Content Pack Builder")
    st.caption("Generate PDF + Markdown packs for TikTok, Instagram, and YouTube.")
with title_col2:
    if st.session_state.get("IS_PRO"):
        st.markdown('<div class="tg-badge">PRO</div>', unsafe_allow_html=True)

# Sidebar (license + limits)
with st.sidebar:
    st.markdown("### Pro Access")
    license_key = st.text_input("Pro License (paste key)", type="password", placeholder="XXXX-XXXX-XXXX-XXXX")
    is_pro = validate_license(license_key) if license_key else False
    daily_limit = PRO_DAILY_LIMIT if (is_pro or not LICENSE_REQUIRED) else FREE_DAILY_LIMIT
    st.write("Daily limit:", daily_limit, "per day")
    st.markdown(f"**Want more?** [Upgrade to Pro]({CHECKOUT_URL})")

    st.markdown("---")
    st.markdown("### Free vs Pro")
    st.markdown(
        """
| Feature | Free | Pro |
|---|---|---|
| Packs per day | **3** | **50** |
| Bulk topics | ❌ | ✅ |
| Save brand style | ❌ | ✅ |
| Platforms | TikTok, Instagram | TikTok, Instagram, YouTube, LinkedIn |
| PDF & Markdown | ✅ | ✅ |
| Priority speed | ❌ | ✅ |
| Commercial use | ❌ | ✅ |
        """
    )
    st.session_state["IS_PRO"] = is_pro
    st.session_state["DAILY_LIMIT"] = daily_limit

# ======= Form (keep white bar spacers) =======
left, right = st.columns([1,1])

with left:
    st.markdown('<div class="tg-cards">', unsafe_allow_html=True)

    # --- white spacer bars (HTML, not widgets → no duplicate IDs) ---
    st.markdown("<div style='height:36px;background:#ffffff; border-radius:10px; margin-bottom:10px;'></div>", unsafe_allow_html=True)
   
    # --- real inputs (each with a unique key) ---
    topic    = st.text_input("Topic",    "fall makeup trends 2025", key="topic")
    niche    = st.text_input("Niche",    "beauty creators",         key="niche")
    audience = st.text_input("Audience", "women 18–30",             key="audience")
    tone     = st.text_input("Tone",     "energetic, helpful",      key="tone")

    platform = st.selectbox("Platform", ["tiktok","instagram","youtube"], index=0, key="platform")
    gen_btn  = st.button("Generate Pack", type="primary", use_container_width=True, key="generate_btn")

    st.markdown('</div>', unsafe_allow_html=True)

# ======= Single generate with progress =======
if gen_btn:
    limit = st.session_state.get("DAILY_LIMIT", FREE_DAILY_LIMIT)
    if st.session_state["USED_TODAY"] >= limit:
        st.error("Daily limit reached. Upgrade to Pro for more.")
        st.stop()

    prog = st.progress(0, text="Starting…")
    try:
        prog.progress(20, text="Thinking up hooks & captions…")
        md, pdf_bytes, base = generate_one(topic, niche, audience, tone, platform)

        with right:
            prog.progress(70, text="Formatting & building PDF…")
            st.markdown('<div class="tg-card">', unsafe_allow_html=True)
            st.subheader("Preview")
            st.markdown(md)
            c1, c2 = st.columns(2)
            c1.download_button("Download Markdown", data=md.encode("utf-8"),
                               file_name=f"{base}.md", mime="text/markdown", use_container_width=True)
            c2.download_button("Download PDF", data=pdf_bytes,
                               file_name=f"{base}.pdf", mime="application/pdf", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        st.session_state["USED_TODAY"] += 1
        prog.progress(100, text="Done ✅")
        time.sleep(0.3)
        prog.empty()
    except Exception as e:
        prog.empty()
        st.error(f"Failed to generate: {e}")

# Always show preview header spot on right
with right:
    st.subheader("Preview")

# =====================  Bulk Mode  =====================
st.markdown("---")
st.subheader("Bulk Mode")
bm_col1, bm_col2 = st.columns([2,1])
with bm_col1:
    bulk_topics = st.text_area("Topics (one per line)", "morning gym routines\nhealthy smoothie ideas\nstudy hacks for finals", height=120)
with bm_col2:
    bulk_platform = st.selectbox("Platform (bulk)", options=["tiktok","instagram","youtube"], index=0)
bulk_btn = st.button("Build All (Bulk)")

import zipfile
from io import BytesIO

if bulk_btn:
    try:
        topics = [t.strip() for t in bulk_topics.splitlines() if t.strip()]
        if not topics:
            st.warning("No topics provided."); st.stop()

        prog = st.progress(0, text="Preparing…")
        out_rows = []
        zip_buf = BytesIO()

        with zipfile.ZipFile(zip_buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            N = len(topics)
            for i, t in enumerate(topics, start=1):
                prog.progress(int((i-1)/N*100), text=f"[{i}/{N}] {t}")
                check_quota(USER_ID, count=1)
                if not is_allowed(t):
                    out_rows.append((t, "blocked", "", "")); continue

                hooks, captions, hashtags, plan = with_retry(
                    lambda: (ai_generate if USE_AI else offline_generate)(
                        t, niche, audience, tone, bulk_platform
                    )
                )
                hooks, captions, hashtags, plan = normalize_pack(hooks, captions, hashtags, plan)

                md = build_markdown(t, niche, audience, tone, bulk_platform, hooks, captions, hashtags, plan)
                safe = "".join([c if c.isalnum() or c in ("-","_") else "_" for c in t])[:40]
                base = f"TrendForge_{bulk_platform}_{safe}"

                pdf_path = OUT / f"{base}.pdf"
                build_trendforge_pdf(
                    pdf_path=pdf_path, topic=t, niche=niche, audience=audience, tone=tone, platform=bulk_platform,
                    hooks=hooks, captions=captions, hashtags=hashtags, plan=plan,
                    tips=PLATFORM_TIPS.get(bulk_platform.lower(), []), ai_used=bool(USE_AI)
                )
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()

                # write both into ZIP
                zf.writestr(f"{base}.pdf", pdf_bytes)
                zf.writestr(f"{base}.md", md.encode("utf-8"))

                out_rows.append((t, "ok", f"{base}.pdf", f"{base}.md"))

            prog.progress(100, text="Packaging ZIP…")
        zip_buf.seek(0)

        st.success(f"Built {len([r for r in out_rows if r[1]=='ok'])} packs.")
        for t, status, pdfp, mdp in out_rows:
            st.write(f"- **{t}** — {status} — {pdfp}")

        st.download_button(
            "⬇️ Download all as ZIP",
            data=zip_buf,
            file_name="trendforge_bulk_packs.zip",
            mime="application/zip"
        )
        prog.empty()

    except Exception as e:
        st.error(f"Bulk build failed: {e}")
