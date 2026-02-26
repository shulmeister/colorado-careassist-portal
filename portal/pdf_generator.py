"""
PDF generator for CareAssist offline forms.
Produces clean, branded PDFs for:
  - Client Assessments  (all C01-C06 sections + signatures)
  - Monitoring Visits
  - Incident Reports
"""
import base64
import io
from datetime import date as _date
from typing import Any, Dict, List, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# ── Brand colors ──────────────────────────────────────────────────────────────
BRAND_BLUE = colors.HexColor("#1a4f7a")
BRAND_LIGHT = colors.HexColor("#e8f0f7")
SECTION_BG = colors.HexColor("#f0f4f8")
SIG_BOX_BG = colors.HexColor("#fafafa")

# ── Style helpers ─────────────────────────────────────────────────────────────
_base = getSampleStyleSheet()

STYLE_TITLE = ParagraphStyle(
    "CCATitle",
    parent=_base["Heading1"],
    fontSize=18,
    textColor=BRAND_BLUE,
    spaceAfter=2,
    alignment=TA_CENTER,
    fontName="Helvetica-Bold",
)
STYLE_SUBTITLE = ParagraphStyle(
    "CCASubtitle",
    parent=_base["Normal"],
    fontSize=10,
    textColor=colors.gray,
    spaceAfter=16,
    alignment=TA_CENTER,
)
STYLE_SECTION = ParagraphStyle(
    "CCASection",
    parent=_base["Heading2"],
    fontSize=11,
    textColor=colors.white,
    spaceBefore=10,
    spaceAfter=4,
    fontName="Helvetica-Bold",
    leftIndent=6,
)
STYLE_LABEL = ParagraphStyle(
    "CCALabel",
    parent=_base["Normal"],
    fontSize=9,
    textColor=colors.HexColor("#555555"),
    fontName="Helvetica-Bold",
)
STYLE_VALUE = ParagraphStyle(
    "CCAValue",
    parent=_base["Normal"],
    fontSize=9,
    textColor=colors.black,
    fontName="Helvetica",
    wordWrap="LTR",
)
STYLE_SIG_LABEL = ParagraphStyle(
    "CCASigLabel",
    parent=_base["Normal"],
    fontSize=8,
    textColor=colors.HexColor("#777777"),
    fontName="Helvetica",
    alignment=TA_CENTER,
)
STYLE_FOOTER = ParagraphStyle(
    "CCAFooter",
    parent=_base["Normal"],
    fontSize=8,
    textColor=colors.gray,
    alignment=TA_CENTER,
)


# ── Builder utilities ─────────────────────────────────────────────────────────

def _section_header(title: str):
    """Returns a Table that renders as a coloured section banner."""
    t = Table([[Paragraph(title, STYLE_SECTION)]], colWidths=[7.0 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _kv_table(rows: List[Tuple[str, Any]], cols: int = 2):
    """
    Renders a grid of (label, value) pairs.
    cols=2 means 2 pairs per row (4 table columns).
    cols=1 means 1 pair per row spanning full width.
    """
    if not rows:
        return None

    if cols == 1:
        col_widths = [1.8 * inch, 5.2 * inch]
        data = [
            [Paragraph(label, STYLE_LABEL), Paragraph(str(val or "—"), STYLE_VALUE)]
            for label, val in rows
        ]
    else:
        col_widths = [1.4 * inch, 2.1 * inch, 1.4 * inch, 2.1 * inch]
        data = []
        for i in range(0, len(rows), 2):
            left_label, left_val = rows[i]
            if i + 1 < len(rows):
                right_label, right_val = rows[i + 1]
            else:
                right_label, right_val = "", ""
            data.append([
                Paragraph(left_label, STYLE_LABEL),
                Paragraph(str(left_val or "—"), STYLE_VALUE),
                Paragraph(right_label, STYLE_LABEL),
                Paragraph(str(right_val or "—"), STYLE_VALUE),
            ])

    t = Table(data, colWidths=col_widths, repeatRows=0)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, SECTION_BG]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _text_block(text: str):
    """Full-width text block for long narrative fields."""
    t = Table(
        [[Paragraph(str(text or "—"), STYLE_VALUE)]],
        colWidths=[7.0 * inch],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SECTION_BG),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _sig_image(b64_str: str, width: float = 2.0 * inch, height: float = 0.55 * inch):
    """Decode a base64 data-URI PNG and return a reportlab Image, or None."""
    if not b64_str or not isinstance(b64_str, str):
        return None
    try:
        if "," in b64_str:
            _, data = b64_str.split(",", 1)
        else:
            data = b64_str
        img_bytes = base64.b64decode(data)
        buf = io.BytesIO(img_bytes)
        return Image(buf, width=width, height=height)
    except Exception:
        return None


def _sig_block(
    sigs: List[Tuple[str, str, str, str]],
    ncols: int = 3,
):
    """
    Render a row of signature boxes.
    sigs: list of (label, b64_image_or_None, typed_name, date_str)
    ncols: 2 or 3 per row
    """
    if not sigs:
        return None

    col_w = 7.0 * inch / ncols
    rows_out = []

    for i in range(0, len(sigs), ncols):
        chunk = sigs[i:i + ncols]
        while len(chunk) < ncols:
            chunk.append(("", None, "", ""))

        # Image row
        img_row = []
        for label, b64, typed, dt in chunk:
            img = _sig_image(b64) if b64 else None
            if img:
                cell = [img]
            elif typed:
                cell = [Paragraph(typed, STYLE_VALUE)]
            else:
                cell = [Paragraph("", STYLE_VALUE)]
            img_row.append(cell)

        # Label + typed name + date row
        info_row = []
        for label, b64, typed, dt in chunk:
            lines = []
            if label:
                lines.append(Paragraph(label, STYLE_SIG_LABEL))
            if typed and b64:  # typed name only shown when we also have the image
                lines.append(Paragraph(typed, STYLE_SIG_LABEL))
            if dt:
                lines.append(Paragraph(f"Date: {dt}", STYLE_SIG_LABEL))
            info_row.append(lines if lines else [Paragraph("", STYLE_SIG_LABEL)])

        rows_out.append(img_row)
        rows_out.append(info_row)

    col_widths = [col_w] * ncols
    t = Table(rows_out, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SIG_BOX_BG),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#eeeeee")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def _add(story, *items):
    for item in items:
        if item is not None:
            story.append(item)


def _footer():
    return [
        Spacer(1, 16),
        HRFlowable(width="100%", thickness=0.5, color=colors.gray),
        Paragraph(
            f"Generated by Colorado CareAssist Portal · {_date.today().isoformat()}",
            STYLE_FOOTER,
        ),
    ]


# ── Public generators ─────────────────────────────────────────────────────────

def generate_client_assessment_pdf(data: Dict[str, Any], meta: Dict[str, Any]) -> bytes:
    """
    Generate a complete PDF for a client assessment including all C01-C06 form
    sections and all captured signatures.
    meta: {client_name, assessment_date, taken_by, referral_source}
    data: raw form_data dict (109+ fields)
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    story = []

    def hdr():
        return [
            Paragraph("Colorado CareAssist", STYLE_TITLE),
            Paragraph("CLIENT ASSESSMENT", STYLE_SUBTITLE),
            HRFlowable(width="100%", thickness=1.5, color=BRAND_BLUE),
            Spacer(1, 8),
        ]

    _add(story, *hdr())

    # ── 1. Assessment Info ────────────────────────────────────────────────────
    _add(story, _section_header("Assessment Information"))
    _add(story, _kv_table([
        ("Client Name", meta.get("client_name")),
        ("Assessment Date", meta.get("assessment_date")),
        ("Taken By", meta.get("taken_by")),
        ("Referral Source", meta.get("referral_source") or data.get("referral")),
        ("Assessment Address", data.get("assessment_address")),
        ("Assessment Time", data.get("assessment_time")),
    ]))

    # ── 2. Client Information ─────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Client Information"))
    _add(story, _kv_table([
        ("Date of Birth", data.get("client_dob")),
        ("Cell Phone", data.get("client_cell_phone")),
        ("Address", data.get("client_address")),
        ("Home Phone", data.get("client_home_phone")),
        ("Email", data.get("client_email")),
        ("Transport", data.get("radio_transport")),
    ]))

    # ── 3. Contacts & Emergency ───────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Contacts & Emergency"))
    _add(story, _kv_table([
        ("Primary Contact", data.get("contact_name")),
        ("Contact Phone", data.get("contact_phone")),
        ("Relation", data.get("relation_to_contact")),
        ("Care Contact", data.get("care_contact")),
        ("Care Contact Phone", data.get("care_contact_phone")),
        ("Other Contact", data.get("other_contact")),
        ("Other Phone", data.get("other_contact_phone")),
        ("Emergency Contact", data.get("emergency_contact")),
        ("Emergency Phone", data.get("emergency_phone")),
        ("", ""),
    ]))

    # ── 4. Medical & Current Situation ────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Medical & Current Situation"))
    _add(story, _kv_table([
        ("Diagnosis", data.get("diagnosis")),
        ("Smokes", data.get("smokes")),
        ("Pets", data.get("pets")),
        ("", ""),
    ]))
    if data.get("current_situation"):
        _add(story, Paragraph("Current Situation:", STYLE_LABEL), _text_block(data["current_situation"]))
    if data.get("about_home"):
        _add(story, Paragraph("About the Home:", STYLE_LABEL), _text_block(data["about_home"]))

    # ── 5. Client Preferences ─────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Client Preferences"))
    if data.get("likes"):
        _add(story, Paragraph("Likes:", STYLE_LABEL), _text_block(data["likes"]))
    if data.get("dislikes"):
        _add(story, Paragraph("Dislikes:", STYLE_LABEL), _text_block(data["dislikes"]))
    if data.get("caregiver_pref"):
        _add(story, Paragraph("Caregiver Preference:", STYLE_LABEL), _text_block(data["caregiver_pref"]))
    if data.get("addl_preferences"):
        _add(story, Paragraph("Additional Preferences:", STYLE_LABEL), _text_block(data["addl_preferences"]))

    # ── 6. Care Plan ──────────────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Care Plan"))
    if data.get("care_goal"):
        _add(story, Paragraph("Care Goal:", STYLE_LABEL), _text_block(data["care_goal"]))
    if data.get("care_plan"):
        _add(story, Paragraph("Care Plan:", STYLE_LABEL), _text_block(data["care_plan"]))
    if data.get("required_tasks"):
        _add(story, Paragraph("Required Tasks:", STYLE_LABEL), _text_block(data["required_tasks"]))
    if data.get("proposed_schedule"):
        _add(story, Paragraph("Proposed Schedule:", STYLE_LABEL), _text_block(data["proposed_schedule"]))

    # ── 7. Advance Directives ─────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Advance Directives"))
    _add(story, _kv_table([
        ("DNR", data.get("ad_dnr")),
        ("MOST", data.get("ad_most")),
        ("Medical POA", data.get("ad_mpoa")),
        ("POA", data.get("ad_poa")),
    ]))

    # ── 8. Payer / Financial ──────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Payer & Financial"))
    _add(story, _kv_table([
        ("Payer Name", data.get("payer_name")),
        ("Payment Type", data.get("radio_pay_type")),
        ("Payment Provider", data.get("payment_provider")),
        ("Payer Phone", data.get("payer_phone")),
        ("Payer Email", data.get("payer_email")),
        ("Payer Address", data.get("payer_address")),
        ("Bill Rate", data.get("bill_rate")),
        ("Receipt Method", data.get("radio_receipt_method")),
        ("Daily Benefit Max", data.get("daily_benefit_max")),
        ("Life Benefit Max", data.get("life_benefit_max")),
    ]))

    # ── C01: Billing Notes ────────────────────────────────────────────────────
    if data.get("c01_notes"):
        _add(story, Spacer(1, 4), _section_header("Billing Notes (C01)"))
        _add(story, _text_block(data["c01_notes"]))

    # ═══════════════════════════════════════════════════════════════════════════
    # C02: Service Agreement / Payment Authorization
    # ═══════════════════════════════════════════════════════════════════════════
    _add(story, PageBreak())
    _add(story, *hdr())
    _add(story, _section_header("Service Agreement — Payment Authorization (C02)"))
    _add(story, _kv_table([
        ("Client Name", data.get("c02_client_name")),
        ("Diagnosis", data.get("c02_diagnosis")),
        ("Referral", data.get("c02_referral")),
        ("Payment Method", data.get("radio_c02_pay")),
        ("Payment Type", data.get("radio_pay_type")),
        ("Bill Rate", data.get("bill_rate")),
        ("Signature Date", data.get("c02_sig_date")),
        ("Signed By", data.get("c02_sig_name")),
    ]))
    _add(story, Spacer(1, 6))
    _add(story, _sig_block([
        ("Client Signature", data.get("sig_c02"), data.get("sigtyped_c02"), data.get("c02_sig_date")),
    ], ncols=2))

    # ═══════════════════════════════════════════════════════════════════════════
    # C03: Consumer-Directed Services Agreement
    # ═══════════════════════════════════════════════════════════════════════════
    _add(story, Spacer(1, 12), _section_header("Consumer-Directed Services Agreement (C03)"))
    _add(story, _kv_table([
        ("Consumer Name", data.get("c03_consumer_name")),
        ("Consumer Date", data.get("c03_consumer_date")),
        ("Start Date", data.get("c03_start_date")),
        ("Worker Name", data.get("c03_worker_name")),
    ]))
    _add(story, Spacer(1, 6))
    _add(story, _sig_block([
        ("Consumer Signature", data.get("sig_c03_consumer"), data.get("sigtyped_c03_consumer"), data.get("c03_consumer_date")),
    ], ncols=2))

    # ═══════════════════════════════════════════════════════════════════════════
    # C04: Service Agreement — Agency & Client Signatures
    # ═══════════════════════════════════════════════════════════════════════════
    _add(story, Spacer(1, 12), _section_header("Service Agreement — Signatures (C04)"))
    _add(story, _kv_table([
        ("Agency Date", data.get("c04_agency_date")),
        ("Client Date", data.get("c04_client_date")),
    ]))
    _add(story, Spacer(1, 6))
    _add(story, _sig_block([
        ("Agency Signature", data.get("sig_c04_agency"), data.get("sigtyped_c04_agency"), data.get("c04_agency_date")),
        ("Client Signature", data.get("sig_c04_client"), data.get("sigtyped_c04_client"), data.get("c04_client_date")),
    ], ncols=2))

    # ═══════════════════════════════════════════════════════════════════════════
    # C05: Service Order / Financial Agreement
    # ═══════════════════════════════════════════════════════════════════════════
    _add(story, PageBreak())
    _add(story, *hdr())
    _add(story, _section_header("Service Order & Financial Agreement (C05)"))
    _add(story, _kv_table([
        ("Client Name", data.get("c05_client_name")),
        ("Client Address", data.get("c05_client_address")),
        ("Agent Name", data.get("c05_agent_name")),
        ("HIPAA Auth", data.get("c05_hipaa_auth")),
        ("Effective Month", data.get("c05_eff_month")),
        ("Effective Day", data.get("c05_eff_day")),
        ("City", data.get("c05_eff_city")),
        ("Rate", data.get("c05_rate")),
        ("Rate Type", data.get("c05_rate_type")),
        ("Hours / Visit", data.get("c05_hours")),
        ("Visits / Period", data.get("c05_visits")),
        ("Period", data.get("c05_period")),
        ("Deposit", data.get("c05_deposit")),
        ("Additional Services", data.get("c05_additional")),
        ("Other", data.get("c05_other")),
        ("", ""),
    ]))
    _add(story, Spacer(1, 6))
    _add(story, _sig_block([
        ("Consumer Signature", data.get("sig_c05_consumer"), data.get("sigtyped_c05_consumer"), data.get("c05_consumer_date")),
        ("Financial Signature", data.get("sig_c05_financial"), data.get("sigtyped_c05_financial"), data.get("c05_financial_date")),
        ("Agency Signature", data.get("sig_c05_agency"), data.get("sigtyped_c05_agency"), data.get("c05_agency_date")),
    ], ncols=3))

    # ═══════════════════════════════════════════════════════════════════════════
    # C06: Additional Agreement
    # ═══════════════════════════════════════════════════════════════════════════
    _add(story, Spacer(1, 12), _section_header("Additional Agreement (C06)"))
    _add(story, _kv_table([
        ("Client Name", data.get("c06_client_name")),
        ("Agency Date", data.get("c06_agency_date")),
        ("Client Date", data.get("c06_client_date")),
        ("", ""),
    ]))
    _add(story, Spacer(1, 6))
    _add(story, _sig_block([
        ("Agency Signature", data.get("sig_c06_agency"), data.get("sigtyped_c06_agency"), data.get("c06_agency_date")),
        ("Client Signature", data.get("sig_c06_client"), data.get("sigtyped_c06_client"), data.get("c06_client_date")),
    ], ncols=2))

    _add(story, *_footer())

    doc.build(story)
    return buf.getvalue()


def generate_monitoring_visit_pdf(data: Dict[str, Any], meta: Dict[str, Any]) -> bytes:
    """
    Generate a PDF for a monitoring visit.
    meta: {client_name, visit_date, submitted_by}
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    story = []

    _add(story,
         Paragraph("Colorado CareAssist", STYLE_TITLE),
         Paragraph("MONITORING VISIT REPORT", STYLE_SUBTITLE),
         HRFlowable(width="100%", thickness=1.5, color=BRAND_BLUE),
         Spacer(1, 8),
         )

    # ── Visit Info ────────────────────────────────────────────────────────────
    _add(story, _section_header("Visit Information"))
    _add(story, _kv_table([
        ("Client", meta.get("client_name")),
        ("Visit Date", meta.get("visit_date")),
        ("Submitted By", meta.get("submitted_by")),
        ("", ""),
    ]))

    # ── Care Plan ─────────────────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Care Plan Compliance"))
    _add(story, _kv_table([
        ("Care Plan Followed", data.get("care_plan_followed")),
        ("Client Satisfied", data.get("client_satisfied")),
    ], cols=1))
    if data.get("care_plan_comments"):
        _add(story, Paragraph("Care Plan Comments:", STYLE_LABEL), _text_block(data["care_plan_comments"]))
    if data.get("satisfaction_comments"):
        _add(story, Paragraph("Satisfaction Comments:", STYLE_LABEL), _text_block(data["satisfaction_comments"]))

    # ── Caregiver 1 ───────────────────────────────────────────────────────────
    cg1 = data.get("caregiver1_name", "").strip()
    if cg1:
        _add(story, Spacer(1, 4), _section_header(f"Primary Caregiver: {cg1}"))
        _add(story, _kv_table([
            ("Companionship", data.get("caregiver1_companionship")),
            ("Housekeeping", data.get("caregiver1_housekeeping")),
            ("Meal Preparation", data.get("caregiver1_meal_prep")),
            ("Personal Care", data.get("caregiver1_personal_care")),
            ("Caring", data.get("caregiver1_caring")),
            ("Professional", data.get("caregiver1_professional")),
        ]))
        if data.get("caregiver1_comments"):
            _add(story, Paragraph("Comments:", STYLE_LABEL), _text_block(data["caregiver1_comments"]))

    # ── Caregiver 2 ───────────────────────────────────────────────────────────
    cg2 = data.get("caregiver2_name", "").strip()
    if cg2:
        _add(story, Spacer(1, 4), _section_header(f"Second Caregiver: {cg2}"))
        _add(story, _kv_table([
            ("Companionship", data.get("caregiver2_companionship")),
            ("Housekeeping", data.get("caregiver2_housekeeping")),
            ("Meal Preparation", data.get("caregiver2_meal_prep")),
            ("Personal Care", data.get("caregiver2_personal_care")),
            ("Caring", data.get("caregiver2_caring")),
            ("Professional", data.get("caregiver2_professional")),
        ]))
        if data.get("caregiver2_comments"):
            _add(story, Paragraph("Comments:", STYLE_LABEL), _text_block(data["caregiver2_comments"]))

    # ── Overall ───────────────────────────────────────────────────────────────
    if data.get("overall_comments"):
        _add(story, Spacer(1, 4), _section_header("Overall Comments"))
        _add(story, _text_block(data["overall_comments"]))

    _add(story, *_footer())
    doc.build(story)
    return buf.getvalue()


def generate_incident_report_pdf(data: Dict[str, Any], meta: Dict[str, Any]) -> bytes:
    """
    Generate a PDF for an incident report.
    meta: {client_name, incident_date, client_birth_date}
    """
    def _radio(key):
        return data.get(key) or data.get(f"radio_{key}", "")

    def _fmt_time(t):
        if not t:
            return ""
        try:
            h, m = t.split(":")[:2]
            h = int(h)
            s = "AM" if h < 12 else "PM"
            h = h % 12 or 12
            return f"{h}:{m} {s}"
        except Exception:
            return t

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    story = []

    _add(story,
         Paragraph("Colorado CareAssist", STYLE_TITLE),
         Paragraph("GENERAL INCIDENT REPORT", STYLE_SUBTITLE),
         HRFlowable(width="100%", thickness=1.5, color=BRAND_BLUE),
         Spacer(1, 8),
         )

    # ── Incident Details ──────────────────────────────────────────────────────
    _add(story, _section_header("Incident Details"))
    _add(story, _kv_table([
        ("Client", meta.get("client_name")),
        ("Date of Birth", meta.get("client_birth_date")),
        ("Employee", data.get("employee_name")),
        ("Employee ID", data.get("employee_id")),
        ("Incident Date", meta.get("incident_date")),
        ("Incident Time", _fmt_time(data.get("incident_time"))),
        ("Reported Date", data.get("reported_date")),
        ("Reported Time", _fmt_time(data.get("reported_time"))),
        ("Location", data.get("location")),
        ("", ""),
    ]))

    # ── Reporting ─────────────────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Reported By / To"))
    _add(story, _kv_table([
        ("Reported By", data.get("reported_by_name")),
        ("Role", data.get("reported_by_role")),
        ("Reported To", data.get("reported_to_name")),
        ("Role", data.get("reported_to_role")),
    ]))

    # ── Other Individuals ─────────────────────────────────────────────────────
    others = [(data.get(f"other{i}_name", "").strip(), data.get(f"other{i}_role", "")) for i in range(1, 4)]
    others = [(n, r) for n, r in others if n]
    if others:
        _add(story, Spacer(1, 4), _section_header("Other Individuals Present"))
        _add(story, _kv_table(
            [("Name", f"{n} ({r})") for n, r in others],
            cols=1,
        ))

    # ── What Happened ─────────────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("What Happened"))
    _add(story, _kv_table([
        ("Resulted in Injury", _radio("resulted_in_injury")),
        ("", ""),
    ], cols=1))
    if data.get("witness_description"):
        _add(story, Paragraph("Witness Description:", STYLE_LABEL), _text_block(data["witness_description"]))
    if _radio("resulted_in_injury") == "Yes" and data.get("injury_description"):
        _add(story, Paragraph("Injury Description:", STYLE_LABEL), _text_block(data["injury_description"]))

    # ── Investigation ─────────────────────────────────────────────────────────
    _add(story, Spacer(1, 4), _section_header("Investigation & Findings"))
    _add(story, _kv_table([
        ("Preventable", _radio("was_preventable")),
        ("", ""),
    ], cols=1))
    if data.get("supervisor_comments"):
        _add(story, Paragraph("Supervisor Comments:", STYLE_LABEL), _text_block(data["supervisor_comments"]))
    if _radio("was_preventable") == "Yes" and data.get("corrective_actions"):
        _add(story, Paragraph("Corrective Actions:", STYLE_LABEL), _text_block(data["corrective_actions"]))

    # ── External Reporting ────────────────────────────────────────────────────
    if _radio("reported_to_external") == "Yes":
        _add(story, Spacer(1, 4), _section_header("External Agency Reporting"))
        _add(story, _kv_table([
            ("Agency", data.get("external_agency_name")),
            ("", ""),
            ("Reported By", data.get("external_reported_by")),
            ("Role", data.get("external_reported_role")),
        ]))

    # ── Manager Review ────────────────────────────────────────────────────────
    if data.get("manager_review"):
        _add(story, Spacer(1, 4), _section_header("Manager Review"))
        _add(story, _text_block(data["manager_review"]))

    _add(story, *_footer())
    doc.build(story)
    return buf.getvalue()
