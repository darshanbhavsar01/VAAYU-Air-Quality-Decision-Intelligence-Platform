"""Generate the VAAYU hackathon pitch deck (.pptx)."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---- palette ----
NAVY   = RGBColor(0x0E, 0x24, 0x40)   # deep background
NAVY2  = RGBColor(0x13, 0x30, 0x55)
BLUE   = RGBColor(0x1F, 0x6F, 0xEB)   # accent
CYAN   = RGBColor(0x2A, 0xB8, 0xC6)   # secondary accent
GREEN  = RGBColor(0x2E, 0xB8, 0x72)
AMBER  = RGBColor(0xF2, 0x9C, 0x33)
INK    = RGBColor(0x1A, 0x22, 0x2B)
MUTED  = RGBColor(0x5C, 0x6B, 0x7A)
LIGHT  = RGBColor(0xF4, 0xF7, 0xFB)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
CARD   = RGBColor(0xFF, 0xFF, 0xFF)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
SW, SH = 13.333, 7.5
BLANK = prs.slide_layouts[6]


def slide():
    return prs.slides.add_slide(BLANK)


def rect(s, l, t, w, h, color, line=None, shape=MSO_SHAPE.RECTANGLE):
    sp = s.shapes.add_shape(shape, Inches(l), Inches(t), Inches(w), Inches(h))
    sp.fill.solid(); sp.fill.fore_color.rgb = color
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line; sp.line.width = Pt(1)
    sp.shadow.inherit = False
    return sp


def txt(s, l, t, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, space=6):
    """runs: list of paragraphs; each paragraph is list of (text,size,color,bold,italic)."""
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(h))
    tf = tb.text_frame; tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align; p.space_after = Pt(space); p.space_before = Pt(0)
        for (text, size, color, bold, *rest) in para:
            r = p.add_run(); r.text = text
            r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold
            r.font.name = "Calibri"
            if rest and rest[0]:
                r.font.italic = True
    return tb


def header(s, kicker, title, num):
    rect(s, 0, 0, SW, 1.35, NAVY)
    rect(s, 0, 1.35, SW, 0.06, BLUE)
    txt(s, 0.6, 0.28, 11, 0.35, [[(kicker.upper(), 12, CYAN, True)]])
    txt(s, 0.6, 0.6, 12, 0.7, [[(title, 30, WHITE, True)]])
    # footer
    txt(s, 0.6, SH - 0.45, 6, 0.3, [[("VAAYU · Air-Quality Decision Intelligence", 9, MUTED, False)]])
    txt(s, SW - 1.2, SH - 0.45, 0.7, 0.3, [[(str(num), 10, MUTED, True)]], align=PP_ALIGN.RIGHT)


def bullets(s, l, t, w, items, size=15, gap=10, marker="▸", mcolor=BLUE):
    tb = s.shapes.add_textbox(Inches(l), Inches(t), Inches(w), Inches(5))
    tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(gap); p.space_before = Pt(0)
        if isinstance(it, tuple):
            head, sub = it
        else:
            head, sub = it, None
        rm = p.add_run(); rm.text = marker + "  "
        rm.font.size = Pt(size); rm.font.color.rgb = mcolor; rm.font.bold = True; rm.font.name = "Calibri"
        rh = p.add_run(); rh.text = head
        rh.font.size = Pt(size); rh.font.color.rgb = INK; rh.font.bold = True; rh.font.name = "Calibri"
        if sub:
            rs = p.add_run(); rs.text = "  —  " + sub
            rs.font.size = Pt(size - 1); rs.font.color.rgb = MUTED; rs.font.bold = False; rs.font.name = "Calibri"
    return tb


def card(s, l, t, w, h, title, body, accent=BLUE, tcolor=INK):
    rect(s, l, t, w, h, CARD, line=RGBColor(0xE1, 0xE7, 0xEF))
    rect(s, l, t, 0.09, h, accent)
    txt(s, l + 0.25, t + 0.18, w - 0.4, 0.5, [[(title, 15, accent, True)]])
    txt(s, l + 0.25, t + 0.62, w - 0.4, h - 0.7, [[(body, 12.5, tcolor, False)]])


# ============================ SLIDE 1 — TITLE ============================
s = slide()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, 0, SW, SH, NAVY)
# accent band
rect(s, 0, 4.95, SW, 0.05, BLUE)
txt(s, 0.9, 1.55, 11, 1.2, [[("🌫️  VAAYU", 60, WHITE, True)]])
txt(s, 0.95, 2.95, 11.5, 0.6, [[("Nationwide Air-Quality Decision Intelligence", 24, CYAN, True)]])
txt(s, 0.95, 3.75, 11.6, 1.1,
    [[("Which neighbourhood will breach safe air limits ", 18, WHITE, False),
      ("tomorrow", 18, AMBER, True),
      (" — why, and what to do about it.", 18, WHITE, False)]])
txt(s, 0.95, 5.25, 11.6, 0.5,
    [[("Track 2 · Pollution Hotspot Detection", 14, WHITE, True),
      ("   |   Build with AI: Code for Communities (Hack2skill × GDG)", 14, MUTED, False)]])
txt(s, 0.95, 5.95, 11.6, 0.9,
    [[("🔗  Live: ", 13, CYAN, True), ("vaayu-api-k2ueldoewq-el.a.run.app", 13, WHITE, False)],
     [("💻  Code: ", 13, CYAN, True), ("github.com/darshanbhavsar01/VAAYU-Air-Quality-Decision-Intelligence-Platform", 12, WHITE, False)],
     [("💰  Built for ", 13, CYAN, True), ("₹0", 13, GREEN, True), (" — entirely on GCP free tier", 13, WHITE, False)]])

# ============================ SLIDE 2 — PROBLEM ============================
s = slide(); header(s, "The Problem", "An MP can't act on what they can't see", 2)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
txt(s, 0.6, 1.75, 12, 0.9,
    [[("A sitting Member of Parliament gets constant complaints about air quality — ", 17, INK, False),
      ("but no ward-level, forward-looking evidence to act on.", 17, BLUE, True)]])
card(s, 0.6, 2.9, 3.9, 3.3, "📉  What exists today",
     "City-average AQI dashboards showing YESTERDAY's numbers. Useful for headlines, useless for targeted action.", accent=MUTED)
card(s, 4.7, 2.9, 3.9, 3.3, "❓  What's missing",
     "WHICH neighbourhood will be unhealthy tomorrow?  WHY?  WHAT specific intervention helps?  None of it is answered.", accent=AMBER)
card(s, 8.8, 2.9, 3.9, 3.3, "⚠️  The consequence",
     "Complaints pile up. Interventions are city-wide, slow, and unaccountable. No evidence base for a constituency office.", accent=RGBColor(0xE9,0x3F,0x33))

# ============================ SLIDE 3 — WHY HARD ============================
s = slide(); header(s, "Why it's genuinely hard", "The constraints that shaped an honest design", 3)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
bullets(s, 0.7, 1.9, 12,
    [("Sparse, uneven sensors", "CPCB has a national network, but 5–40 stations per metro and only 1–3 in some Tier-2 cities"),
     ("No historical CPCB API", "the government feed is a live snapshot only — you cannot download the past to train a forecaster"),
     ("Messy ward boundaries", "clean municipal ward GeoJSONs are not uniformly available across India — the real nationwide bottleneck"),
     ("District-office reality", "must run on near-zero budget with existing infra — no new hardware, no enterprise cloud spend"),
     ("Free-tier AI limits", "generous-sounding LLM free tiers are tightly rate-limited per model, per account")],
    size=16, gap=14)
rect(s, 0.7, 6.35, 11.9, 0.75, RGBColor(0xEA, 0xF1, 0xFB))
txt(s, 0.95, 6.5, 11.5, 0.5,
    [[("Every one of these became a design decision you can defend to a sharp judge — not a limitation we hid.", 14, BLUE, True)]],
    anchor=MSO_ANCHOR.MIDDLE)

# ============================ SLIDE 4 — SOLUTION ============================
s = slide(); header(s, "Our Solution", "VAAYU turns sparse station data into decisions", 4)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
row = [("🗺️", "Hotspot maps", "~1 km grid interpolated from stations, for every city with a monitor"),
       ("🔮", "24h spike forecast", "tomorrow's max PM2.5 + probability of breaching the 60 µg/m³ safe limit"),
       ("🧭", "Likely drivers", "heuristic attribution — stagnation / traffic / accumulation"),
       ("🗣️", "Local-language advisories", "citizen health guidance in English + Hindi + regional language"),
       ("📄", "Weekly MP report", "per-constituency: hotspots, trends, recommended interventions"),
       ("💬", "Ask VAAYU", "natural-language Q&A grounded in the live forecast")]
x0, y0, cw, ch, gx, gy = 0.6, 1.75, 3.95, 1.55, 0.15, 0.2
for i, (ic, ti, bo) in enumerate(row):
    r, c = divmod(i, 3)
    l = x0 + c * (cw + gx); t = y0 + r * (ch + gy)
    rect(s, l, t, cw, ch, CARD, line=RGBColor(0xE1,0xE7,0xEF))
    txt(s, l + 0.2, t + 0.15, 1, 0.6, [[(ic, 24, BLUE, False)]])
    txt(s, l + 0.95, t + 0.2, cw - 1.1, 0.5, [[(ti, 15, INK, True)]])
    txt(s, l + 0.22, t + 0.78, cw - 0.4, 0.7, [[(bo, 11.5, MUTED, False)]])
txt(s, 0.6, 5.6, 12, 0.8,
    [[("Live in 7 cities today: ", 15, INK, True),
      ("Bengaluru · Delhi · Mumbai · Chennai · Kolkata · Hyderabad · Pune", 15, BLUE, True)],
     [("Adding a new city = ", 13, MUTED, False), ("one line of YAML", 13, GREEN, True),
      (" — no code, no redeploy.", 13, MUTED, False)]])

# ============================ SLIDE 5 — DEMO WALKTHROUGH ============================
s = slide(); header(s, "See it live", "The 60-second demo any judge can run", 5)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
steps = [("1", "Pick a city", "Choose Bengaluru from the selector — the map redraws instantly to its ~1 km grid."),
         ("2", "Read tomorrow", "Toggle to 'Tomorrow'. Cells colour by forecast PM2.5; faded cells = low confidence, stated openly."),
         ("3", "Click a hotspot", "A panel shows the 24h forecast, breach probability, and the likely driver for that neighbourhood."),
         ("4", "Get the advisory", "A citizen health advisory appears in English, Hindi and the local language."),
         ("5", "Switch cities live", "Jump to Delhi — same platform, same models, no redeploy. The nationwide moment."),
         ("6", "Ask & report", "Type a question into 'Ask VAAYU'; download the weekly MP report for the constituency.")]
x0, y0, cw, ch, gx, gy = 0.6, 1.85, 3.95, 1.7, 0.15, 0.2
for i, (n, ti, bo) in enumerate(steps):
    r, c = divmod(i, 3)
    l = x0 + c * (cw + gx); t = y0 + r * (ch + gy)
    rect(s, l, t, cw, ch, CARD, line=RGBColor(0xE1,0xE7,0xEF))
    rect(s, l, t, cw, 0.06, BLUE)
    circ = rect(s, l + 0.2, t + 0.22, 0.5, 0.5, BLUE, shape=MSO_SHAPE.OVAL)
    txt(s, l + 0.2, t + 0.29, 0.5, 0.4, [[(n, 16, WHITE, True)]], align=PP_ALIGN.CENTER)
    txt(s, l + 0.85, t + 0.28, cw - 1.0, 0.5, [[(ti, 14.5, INK, True)]])
    txt(s, l + 0.22, t + 0.85, cw - 0.42, 0.75, [[(bo, 11, MUTED, False)]])
txt(s, 0.6, 5.75, 12, 0.6,
    [[("🔗  Try it now: ", 14, BLUE, True), ("vaayu-api-k2ueldoewq-el.a.run.app", 14, INK, False),
      ("   — no login, runs on cached BigQuery data so it never depends on a live API at pitch time.", 12.5, MUTED, False)]])

# ============================ SLIDE 6 — HOW IT WORKS ============================
s = slide(); header(s, "How it works", "A config-driven pipeline, end to end", 6)
rect(s, 0, 1.41, SW, SH - 1.41, WHITE)
def flowbox(l, t, w, h, title, sub, color):
    rect(s, l, t, w, h, color)
    txt(s, l + 0.12, t + 0.1, w - 0.2, h - 0.2,
        [[(title, 12.5, WHITE, True)], [(sub, 9.5, RGBColor(0xE6,0xEE,0xF7), False)]],
        anchor=MSO_ANCHOR.MIDDLE)
def arrow(l, t):
    txt(s, l, t, 0.5, 0.4, [[("➜", 18, MUTED, True)]], align=PP_ALIGN.CENTER)
flowbox(0.6, 1.8, 2.5, 0.95, "cities.yaml", "city registry (bbox, stations)", CYAN)
arrow(3.15, 2.0)
flowbox(3.65, 1.8, 2.6, 0.95, "Cloud Scheduler", "hourly + daily triggers", NAVY2)
arrow(6.3, 2.0)
flowbox(6.8, 1.8, 3.0, 0.95, "Cloud Run Jobs: ingest", "CPCB · Open-Meteo · CAMS", NAVY2)
arrow(9.85, 2.0)
flowbox(10.35, 1.8, 2.35, 0.95, "BigQuery", "raw + features", BLUE)
# row 2
flowbox(0.6, 3.15, 3.0, 0.95, "BQML models", "breach classifier + PM2.5 regressor", BLUE)
arrow(3.65, 3.35)
flowbox(4.15, 3.15, 3.0, 0.95, "IDW interpolation", "grid surface + confidence", NAVY2)
arrow(7.2, 3.35)
flowbox(7.7, 3.15, 2.4, 0.95, "3 AI agents", "sentinel · oracle · vaani", GREEN)
arrow(10.15, 3.35)
flowbox(10.65, 3.15, 2.05, 0.95, "FastAPI + UI", "Leaflet map", NAVY)
# stack strip
rect(s, 0.6, 4.55, 12.1, 1.9, LIGHT)
txt(s, 0.85, 4.7, 11.6, 0.4, [[("STACK", 12, BLUE, True)]])
txt(s, 0.85, 5.1, 11.8, 1.2,
    [[("Cloud Run (service + jobs) · Cloud Scheduler · BigQuery + BQML · Gemini API (AI Studio, not Vertex) · FastAPI · Leaflet · Secret Manager", 14, INK, False)],
     [("Region asia-south1 — data stays in India.  Every component sits inside the GCP free tier.", 13, MUTED, False, True)]])

# ============================ SLIDE 6 — THE ML ============================
s = slide(); header(s, "The forecast model — honestly", "Reported the way a technical judge respects", 7)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
txt(s, 0.6, 1.7, 12, 0.6,
    [[("Two global gradient-boosted models (breach probability + next-24h max PM2.5), temporal split, test fully held out.", 14, INK, False)]])
# metrics table
tbl_l, tbl_t = 0.6, 2.45
rect(s, tbl_l, tbl_t, 6.6, 0.5, NAVY)
txt(s, tbl_l + 0.15, tbl_t + 0.08, 3.2, 0.4, [[("Metric (TEST set)", 13, WHITE, True)]])
txt(s, tbl_l + 3.6, tbl_t + 0.08, 1.6, 0.4, [[("VAAYU", 13, CYAN, True)]], align=PP_ALIGN.CENTER)
txt(s, tbl_l + 5.1, tbl_t + 0.08, 1.4, 0.4, [[("Persistence", 13, WHITE, True)]], align=PP_ALIGN.CENTER)
rows = [("Breach AUC-PR", "0.993", "0.991"),
        ("Breach recall", "0.971", "0.849"),
        ("Next-24h max PM2.5 MAE", "25.2", "34.7")]
for i, (m, a, b) in enumerate(rows):
    ty = tbl_t + 0.5 + i * 0.5
    rect(s, tbl_l, ty, 6.6, 0.5, WHITE if i % 2 == 0 else RGBColor(0xEE,0xF3,0xF9))
    txt(s, tbl_l + 0.15, ty + 0.09, 3.3, 0.4, [[(m, 12.5, INK, False)]])
    txt(s, tbl_l + 3.6, ty + 0.09, 1.6, 0.4, [[(a, 13, GREEN, True)]], align=PP_ALIGN.CENTER)
    txt(s, tbl_l + 5.1, ty + 0.09, 1.4, 0.4, [[(b, 12.5, MUTED, False)]], align=PP_ALIGN.CENTER)
# the real win card
rect(s, 7.5, 2.45, 5.2, 2.5, NAVY)
txt(s, 7.75, 2.65, 4.8, 0.5, [[("WHERE IT EARNS ITS KEEP", 12, CYAN, True)]])
txt(s, 7.75, 3.1, 4.8, 1.8,
    [[("Predicting NEW breaches", 16, WHITE, True)],
     [("On clean-air hours, persistence catches ", 13, WHITE, False), ("0%", 13, AMBER, True),
      (" of breaches that then occur.", 13, WHITE, False)],
     [("VAAYU catches ", 13, WHITE, False), ("81%", 20, GREEN, True),
      (" — that's the advance warning an MP can act on.", 13, WHITE, False)]])
txt(s, 0.6, 5.35, 12.1, 1.6,
    [[("We publish the weak numbers too.", 14, BLUE, True)],
     [("In the monsoon training window, southern cities (Bengaluru, Chennai) genuinely have near-zero breaches — so their per-city scores are unstable or n/a. We show that openly rather than cherry-picking. Where the model doesn't beat persistence, we say so.", 12.5, MUTED, False)]])

# ============================ SLIDE 7 — AGENTS ============================
s = slide(); header(s, "Three grounded AI agents", "Powered by Gemini (AI Studio) — answer only from the data", 8)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
card(s, 0.6, 1.85, 3.9, 3.0, "🛰️  sentinel", "Ingestion QA. Monitors feed freshness per station across all cities and flags stale (>3h) or anomalous readings — so a broken feed never silently corrupts a forecast.", accent=CYAN)
card(s, 4.7, 1.85, 3.9, 3.0, "🔮  oracle", "Forecast Q&A. Answers natural-language questions from the MP dashboard, grounded strictly in a live BigQuery snapshot: 'which city is worst tomorrow?', 'compare Delhi and Mumbai'.", accent=BLUE)
card(s, 8.8, 1.85, 3.9, 3.0, "🗣️  vaani", "Advisories + reports. Citizen health advisories in English + Hindi + the regional language, and the weekly per-constituency MP report — all grounded in the forecast JSON.", accent=GREEN)
rect(s, 0.6, 5.15, 12.1, 1.4, NAVY)
txt(s, 0.85, 5.3, 11.7, 0.4, [[("🌐  Multilingual, and it actually works", 14, CYAN, True)]])
txt(s, 0.85, 5.75, 11.8, 0.7,
    [[("20 / 20 advisories live across all 7 cities in ", 13, WHITE, False),
      ("English · Hindi · Kannada · Marathi · Tamil · Bengali · Telugu", 13, WHITE, True),
      (" — each grounded in that city's forecast, zero hallucination.", 13, RGBColor(0xC9,0xD6,0xE5), False)]])

# ============================ SLIDE 8 — ENGINEERING ============================
s = slide(); header(s, "Engineering that makes it deployable", "The parts that survive a district-office reality", 9)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
card(s, 0.6, 1.85, 5.9, 1.75, "🧩  Config-driven onboarding",
     "onboard_city.py <city> validates coverage, backfills a year of weather + CAMS history — the city appears everywhere. No code change.", accent=BLUE)
card(s, 6.7, 1.85, 6.0, 1.75, "🔁  Idempotent pipelines",
     "Staging + MERGE on every ingest; re-running never duplicates a row. Fault-tolerant hourly job survives a flaky government feed.", accent=CYAN)
card(s, 0.6, 3.8, 5.9, 2.35, "♻️  Gemini free-tier survival — for ₹0",
     "A model + account fallback chain: on quota exhaustion, cascade through 8 Gemini models, then roll to the next of 3 AI Studio accounts ≈ 24 independent free quota pools. Took advisories from stuck-at-5/20 to a full 20/20 in one run.", accent=GREEN)
card(s, 6.7, 3.8, 6.0, 2.35, "🎯  Honest by construction",
     "Every map cell shows a distance-to-nearest-station confidence tier — IDW from sparse sensors is an approximation, and the UI says so. Grid mode is the honest nationwide default; ward mode is additive only where a boundary is validated.", accent=AMBER)

# ============================ SLIDE 9 — COST ============================
s = slide(); header(s, "Cost", "The constraint we treated as load-bearing", 10)
rect(s, 0, 1.41, SW, SH - 1.41, NAVY)
txt(s, 0.6, 2.0, 12, 1.4,
    [[("₹0", 84, GREEN, True), ("   spent", 34, WHITE, True)]], align=PP_ALIGN.LEFT)
txt(s, 0.65, 3.5, 12, 0.6, [[("against a ₹500 hard cap for the entire build.", 20, RGBColor(0xC9,0xD6,0xE5), False)]])
items = [("Cloud Run", "min-instances=0 → no idle cost; hourly + daily jobs well within free GB-seconds"),
         ("BigQuery + BQML", "<10 GB storage, <1 TB queries/month — the whole multi-city dataset fits free"),
         ("Gemini", "AI Studio free tier (NOT enterprise Vertex AI) — kept off the GCP bill entirely"),
         ("Everything else", "Scheduler, Secret Manager, public data APIs — all free tier")]
y = 4.35
for h, b in items:
    txt(s, 0.7, y, 12,
        0.45, [[("✔  ", 14, GREEN, True), (h + ":  ", 14, WHITE, True), (b, 13, RGBColor(0xC9,0xD6,0xE5), False)]])
    y += 0.55
txt(s, 0.7, y + 0.05, 12, 0.5,
    [[("Zero new hardware · existing CPCB infrastructure · near-zero ongoing cost.", 14, CYAN, True)]])

# ============================ SLIDE 10 — DIFFERENTIATOR ============================
s = slide(); header(s, "Why VAAYU stands apart", "Honesty as a feature, not an afterthought", 11)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
bullets(s, 0.7, 1.9, 12,
    [("No CPCB history? Say so, and handle it", "train on labelled CAMS reanalysis, kept in a separate table, cross-validated against live CPCB as it accrues"),
     ("Confidence varies by city — and we show it", "a dense-network Delhi cell and a sparse Tier-2 cell are not presented as equally certain"),
     ("Attribution is labelled 'likely drivers'", "a transparent weather heuristic — never dressed up as measured source apportionment"),
     ("Weak metrics are published with fix paths", "the evaluation appendix reports where we lose to persistence, not just where we win"),
     ("Deployability over ML flashiness", 'every decision survives: "could this run in a district office next month?"')],
    size=16, gap=16)

# ============================ SLIDE 11 — FUTURE SCOPE ============================
s = slide(); header(s, "Future scope", "The roadmap from pilot to nationwide", 12)
rect(s, 0, 1.41, SW, SH - 1.41, LIGHT)
col1 = [("Ward mode (Tier B)", "aggregate the grid to real municipal wards where a boundary is validated — Bengaluru's BBMP wards next"),
        ("More cities, on demand", "config-driven onboarding scales to any CPCB-covered city as ward data is confirmed"),
        ("Retrain on real CPCB", "as live history accumulates, shift the model off CAMS onto ground truth")]
col2 = [("Richer features", "OSM road-density & land-use per station; Sentinel-5P satellite NO₂ overlay"),
        ("Citizen participation", "photo-reports of burning/dust/traffic feeding attribution; Kannada/Hindi voice advisories (TTS)"),
        ("Cross-city intelligence", "'compare my constituency to similar-sized cities' for the MP dashboard")]
txt(s, 0.7, 1.85, 5.9, 0.4, [[("NEAR TERM", 13, BLUE, True)]])
bullets(s, 0.7, 2.3, 5.9, col1, size=13.5, gap=13)
txt(s, 6.9, 1.85, 5.8, 0.4, [[("STRETCH", 13, GREEN, True)]])
bullets(s, 6.9, 2.3, 5.8, col2, size=13.5, gap=13, mcolor=GREEN)
rect(s, 0.7, 6.2, 12.0, 0.8, RGBColor(0xEA,0xF1,0xFB))
txt(s, 0.95, 6.35, 11.6, 0.5,
    [[("The architecture already assumes all of this — new cities and ward files drop in without touching the model.", 13.5, BLUE, True)]],
    anchor=MSO_ANCHOR.MIDDLE)

# ============================ SLIDE 12 — IMPACT / CLOSE ============================
s = slide()
rect(s, 0, 0, SW, SH, NAVY)
rect(s, 0, 2.4, SW, 0.05, BLUE)
txt(s, 0.9, 0.9, 11.5, 0.8, [[("VAAYU, in one line", 16, CYAN, True)]])
txt(s, 0.9, 1.4, 11.6, 1.1,
    [[("Tells any MP's office which neighbourhoods breach tomorrow, ", 23, WHITE, True),
      ("why", 23, AMBER, True), (", and ", 23, WHITE, True),
      ("what to do", 23, AMBER, True),
      (" — on existing public infrastructure, at near-zero cost.", 23, WHITE, True)]])
stats = [("7", "cities live"), ("₹0", "build cost"), ("24h", "spike forecast"), ("7", "languages"), ("81%", "new breaches caught")]
x = 0.9
for v, l in stats:
    rect(s, x, 2.9, 2.25, 1.35, NAVY2)
    txt(s, x, 3.05, 2.25, 0.7, [[(v, 30, GREEN, True)]], align=PP_ALIGN.CENTER)
    txt(s, x, 3.75, 2.25, 0.4, [[(l, 12, RGBColor(0xC9,0xD6,0xE5), False)]], align=PP_ALIGN.CENTER)
    x += 2.4
txt(s, 0.9, 4.75, 11.6, 0.5, [[("Live, deployed, and open source — today.", 16, WHITE, True)]])
txt(s, 0.9, 5.45, 11.8, 1.3,
    [[("🔗  ", 14, CYAN, True), ("vaayu-api-k2ueldoewq-el.a.run.app", 15, WHITE, False)],
     [("💻  ", 14, CYAN, True), ("github.com/darshanbhavsar01/VAAYU-Air-Quality-Decision-Intelligence-Platform", 13, WHITE, False)],
     [("🙏  ", 14, CYAN, True), ("Thank you — questions welcome.", 15, CYAN, True)]])

prs.save(r"d:\Users\DELL 3576\Darshan\VAAYU\VAAYU_Pitch_Deck.pptx")
print("saved:", len(prs.slides.__iter__.__self__._sldIdLst), "slides")
