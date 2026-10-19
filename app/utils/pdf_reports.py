"""
app/utils/pdf_reports.py
========================
Reusable PDF report generators for SchoolPortal.
Requires: reportlab >= 5.0, Pillow >= 10.0

All public functions return an ``io.BytesIO`` buffer positioned at byte 0,
ready to pass directly to ``flask.send_file``.
"""
import io
from datetime import date as _date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.pdfgen import canvas as _rl_canvas

# -- Brand palette (SchoolPortal design system) --------------------------------
NAVY    = colors.HexColor("#111c3a")
BLUE    = colors.HexColor("#4568f5")
BLUE_LT = colors.HexColor("#edf1ff")
MUTED   = colors.HexColor("#7b8499")
BORDER  = colors.HexColor("#dde2ef")
ROW_ALT = colors.HexColor("#f8fafc")
WHITE   = colors.white


# -- Numbered-page canvas ------------------------------------------------------
class _NumberedCanvas(_rl_canvas.Canvas):
    """Adds Page X of Y and a confidentiality footer to every page."""

    def __init__(self, *args, **kwargs):
        _rl_canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            _rl_canvas.Canvas.showPage(self)
        _rl_canvas.Canvas.save(self)

    def _draw_footer(self, total):
        width, _ = self._pagesize
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(MUTED)
        self.drawString(1.5 * cm, 0.9 * cm, "SchoolPortal -- Confidential")
        self.drawRightString(
            width - 1.5 * cm, 0.9 * cm,
            "Page {} of {}".format(self._pageNumber, total),
        )
        self.restoreState()


# -- Shared helpers ------------------------------------------------------------
def _styles():
    return {
        "brand": ParagraphStyle(
            "brand", fontName="Helvetica-Bold", fontSize=11,
            textColor=BLUE, spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=16,
            textColor=NAVY, spaceAfter=2,
        ),
        "caption": ParagraphStyle(
            "caption", fontName="Helvetica", fontSize=9,
            textColor=MUTED, spaceAfter=10,
        ),
        "exam_heading": ParagraphStyle(
            "exam_heading", fontName="Helvetica-Bold", fontSize=11,
            textColor=NAVY, spaceBefore=14, spaceAfter=4,
        ),
        "note": ParagraphStyle(
            "note", fontName="Helvetica-Oblique", fontSize=8,
            textColor=MUTED, spaceBefore=6,
        ),
    }


def _doc_header(story, title, caption=None):
    s = _styles()
    story.append(Paragraph("SchoolPortal", s["brand"]))
    story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY, spaceAfter=8))
    story.append(Paragraph(title, s["h1"]))
    if caption:
        story.append(Paragraph(caption, s["caption"]))


def _info_table(rows, col_widths):
    """Two-column label | value info card."""
    t = Table(rows, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME",      (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("TEXTCOLOR",     (0, 0), (-1, -1), NAVY),
        ("BACKGROUND",    (0, 0), (-1, -1), ROW_ALT),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    return t


def _fmt(value):
    """Format a numeric marks value: 78.0 -> '78', 78.5 -> '78.5'."""
    if value is None:
        return "--"
    f = float(value)
    return str(int(f)) if f == int(f) else "{:.2f}".format(f)


def _pct(value):
    return "{:.1f}%".format(float(value)) if value is not None else "--"


def _money(value):
    if value is None:
        return "0.00"
    return "{:,.2f}".format(float(value))


# =============================================================================
# Report A -- Class Results (landscape A4)
# =============================================================================
def generate_class_results_pdf(exam, students, subjects, result_map, summary):
    """
    Build a landscape A4 PDF showing every active student's marks for one exam.

    Parameters
    ----------
    exam        : Exam ORM object (exam.classroom must be accessible)
    students    : list[Student] -- active students ordered by full_name
    subjects    : list[Subject] -- subjects assigned to the class, ordered by name
    result_map  : dict  {student_id: {subject_id: ExamResult}}
    summary     : dict  with keys:
                    total_students        int
                    students_with_results int
                    class_average         float | None

    Returns
    -------
    io.BytesIO  (positioned at byte 0)
    """
    buf = io.BytesIO()
    psize = landscape(A4)
    usable_w = psize[0] - 3.0 * cm   # 1.5 cm margin each side

    doc = SimpleDocTemplate(
        buf, pagesize=psize,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2.0 * cm, bottomMargin=2.0 * cm,
    )
    story = []
    s = _styles()

    # Header
    _doc_header(
        story,
        "Class Result Report -- {}".format(exam.name),
        "Generated: {}".format(_date.today().strftime("%d %B %Y")),
    )

    # Exam detail card
    info_rows = [
        ["Exam Name",     exam.name,
         "Class",         exam.classroom.name],
        ["Exam Date",     str(exam.exam_date),
         "Max / Subject", str(exam.total_marks)],
        ["Status",        "Published" if exam.is_published else "Draft", "", ""],
    ]
    story.append(_info_table(info_rows, [3.0 * cm, 5.5 * cm, 3.0 * cm, 5.5 * cm]))
    story.append(Spacer(1, 10))

    # Summary banner
    no_res = summary["total_students"] - summary["students_with_results"]
    summ_data = [[
        "Total Students: {}".format(summary["total_students"]),
        "With Marks: {}".format(summary["students_with_results"]),
        "Without Marks: {}".format(no_res),
        "Class Average: {}".format(_pct(summary.get("class_average"))),
    ]]
    summ_tbl = Table(summ_data, colWidths=[usable_w / 4] * 4)
    summ_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLUE_LT),
        ("TEXTCOLOR",     (0, 0), (-1, -1), NAVY),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOX",           (0, 0), (-1, -1), 0.5, BLUE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summ_tbl)
    story.append(Spacer(1, 12))

    if not students:
        story.append(Paragraph(
            "No active students are enrolled in this class.", s["caption"]
        ))
        doc.build(story, canvasmaker=_NumberedCanvas)
        buf.seek(0)
        return buf

    # Result matrix table
    n_sub   = len(subjects)
    fixed_w = 4.5 * cm + 2.0 * cm + 3 * 1.8 * cm   # name + roll + Total/Max/%
    sub_w   = max((usable_w - fixed_w) / n_sub, 2.0 * cm) if n_sub else 0

    col_widths = (
        [4.5 * cm, 2.0 * cm]
        + [sub_w] * n_sub
        + [1.8 * cm, 1.8 * cm, 1.8 * cm]
    )

    header_row = (
        ["Student", "Roll No"]
        + [sub.name for sub in subjects]
        + ["Total", "Max", "%"]
    )
    table_rows = [header_row]

    for student in students:
        s_res     = result_map.get(student.id, {})
        total_obt = 0.0
        subs_rec  = 0
        row       = [student.full_name, student.roll_number]
        for subject in subjects:
            r = s_res.get(subject.id)
            if r is not None:
                row.append(_fmt(r.marks))
                total_obt += float(r.marks)
                subs_rec  += 1
            else:
                row.append("--")
        if subs_rec > 0:
            max_m = subs_rec * exam.total_marks
            row += [_fmt(total_obt), str(max_m), _pct(total_obt / max_m * 100)]
        else:
            row += ["--", "--", "--"]
        table_rows.append(row)

    tbl = Table(table_rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        # Header
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        # Body
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
        ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
        # Alignment
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",         (0, 1), (1, -1), "LEFT"),
        # Grid
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Note: '--' indicates no marks were recorded for that subject. "
        "Totals and percentages only count subjects with recorded marks.",
        s["note"],
    ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf


# =============================================================================
# Report B -- Individual Student Results (portrait A4)
# =============================================================================
def generate_student_results_pdf(student, exams_data):
    """
    Build a portrait A4 PDF with one student's marks across all class exams.

    Parameters
    ----------
    student     : Student ORM object (student.classroom must be accessible)
    exams_data  : list[dict]  -- each dict must have:
                    exam           Exam ORM object
                    subject_rows   list[{subject: Subject, result: ExamResult|None}]
                    total_obtained float | None
                    max_marks      int | None
                    percentage     float | None
                    has_results    bool

    Returns
    -------
    io.BytesIO  (positioned at byte 0)
    """
    buf = io.BytesIO()
    usable_w = A4[0] - 3.0 * cm   # ~18 cm with 1.5 cm margins

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2.0 * cm, bottomMargin=2.0 * cm,
    )
    story = []
    s = _styles()

    # Header
    _doc_header(
        story,
        "Student Result Report",
        "Generated: {}".format(_date.today().strftime("%d %B %Y")),
    )

    # Student info card
    classroom_name = (
        student.classroom.name
        if getattr(student, "classroom", None) else "Unassigned"
    )
    info_rows = [
        ["Student Name", student.full_name],
        ["Roll Number",  student.roll_number],
        ["Class",        classroom_name],
    ]
    story.append(_info_table(info_rows, [3.5 * cm, usable_w - 3.5 * cm]))
    story.append(Spacer(1, 14))

    # Subject | Marks | Max | % | Grade | Remarks
    fixed_cols_w = (5.5 + 2.0 + 2.0 + 1.8 + 1.5) * cm
    col_w = [
        5.5 * cm, 2.0 * cm, 2.0 * cm, 1.8 * cm, 1.5 * cm,
        usable_w - fixed_cols_w,
    ]

    any_results_found = False

    for ed in exams_data:
        exam = ed["exam"]
        story.append(Paragraph(
            "{}  .  {}  .  {}".format(
                exam.name,
                exam.exam_date,
                "Published" if exam.is_published else "Draft",
            ),
            s["exam_heading"],
        ))

        if not ed["has_results"]:
            story.append(Paragraph(
                "No marks have been recorded for this student in this exam.",
                s["note"],
            ))
            continue

        any_results_found = True
        rows = [["Subject", "Marks", "Max", "%", "Grade", "Remarks"]]

        for sr in ed["subject_rows"]:
            r = sr["result"]
            if r is not None:
                m = float(r.marks)
                rows.append([
                    sr["subject"].name,
                    _fmt(r.marks),
                    str(exam.total_marks),
                    _pct(m / exam.total_marks * 100),
                    r.grade or "--",
                    r.remarks or "--",
                ])
            else:
                rows.append([
                    sr["subject"].name, "--", str(exam.total_marks),
                    "--", "--", "--",
                ])

        # Totals row
        rows.append([
            "Total",
            _fmt(ed["total_obtained"]),
            str(ed["max_marks"]) if ed["max_marks"] is not None else "--",
            _pct(ed["percentage"]),
            "", "",
        ])

        tbl = Table(rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            # Header row
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            # Body rows
            ("FONTNAME",      (0, 1), (-1, -2), "Helvetica"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -2), [WHITE, ROW_ALT]),
            ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
            # Totals row
            ("BACKGROUND",    (0, -1), (-1, -1), BLUE_LT),
            ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
            # Alignment
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",         (0, 1), (0, -1), "LEFT"),
            ("ALIGN",         (-1, 1), (-1, -1), "LEFT"),
            # Grid
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)

    if not exams_data or not any_results_found:
        story.append(Spacer(1, 12))
        story.append(Paragraph(
            "No exam results have been recorded for this student.",
            s["caption"],
        ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf


# =============================================================================
# Report C -- Individual Student Attendance (portrait A4)
# =============================================================================
def generate_student_attendance_pdf(student, classroom, month_str, records, totals, total_days, attendance_percentage):
    """
    Build a portrait A4 PDF with one student's monthly attendance records.
    """
    buf = io.BytesIO()
    usable_w = A4[0] - 3.0 * cm   # ~18 cm with 1.5 cm margins

    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2.0 * cm, bottomMargin=2.0 * cm,
    )
    story = []
    s = _styles()

    # Header
    _doc_header(
        story,
        "Student Attendance Report",
        "Generated: {}".format(_date.today().strftime("%d %B %Y")),
    )

    # Student info card
    info_rows = [
        ["Student Name", student.full_name, "Roll Number", student.roll_number],
        ["Class", classroom.name if classroom else "Unassigned", "Month", month_str],
    ]
    story.append(_info_table(info_rows, [3.2 * cm, 5.8 * cm, 3.2 * cm, usable_w - (3.2 + 5.8 + 3.2) * cm]))
    story.append(Spacer(1, 10))

    # Summary metrics banner (5 boxes)
    col_w_summ = usable_w / 5
    summ_data = [[
        "Recorded: {}".format(total_days),
        "Present: {}".format(totals.get("Present", 0)),
        "Absent: {}".format(totals.get("Absent", 0)),
        "Late: {}".format(totals.get("Late", 0)),
        "Rate: {}".format(_pct(attendance_percentage)),
    ]]
    summ_tbl = Table(summ_data, colWidths=[col_w_summ] * 5)
    summ_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLUE_LT),
        ("TEXTCOLOR",     (0, 0), (-1, -1), NAVY),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOX",           (0, 0), (-1, -1), 0.5, BLUE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(summ_tbl)
    story.append(Spacer(1, 12))

    # Records table
    if not records:
        story.append(Paragraph(
            "No attendance records were recorded for this student in the selected month.",
            s["caption"],
        ))
    else:
        table_rows = [["Attendance Date", "Classroom", "Status"]]
        for r in records:
            cls_name = r.classroom.name if r.classroom else (classroom.name if classroom else "--")
            table_rows.append([str(r.attendance_date), cls_name, r.status])

        rec_col_w = [5.5 * cm, 6.5 * cm, usable_w - (5.5 + 6.5) * cm]
        tbl = Table(table_rows, colWidths=rec_col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",         (0, 1), (1, -1), "LEFT"),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Note: Attendance percentage formula is (Present + Late) / total recorded days x 100. "
            "Unrecorded calendar days are not counted as absent.",
            s["note"],
        ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf


# =============================================================================
# Report D -- Class Attendance (landscape A4)
# =============================================================================
def generate_class_attendance_pdf(classroom, month_str, students, student_summaries, class_summary):
    """
    Build a landscape A4 PDF with monthly attendance breakdown for all students in a class.
    """
    buf = io.BytesIO()
    psize = landscape(A4)
    usable_w = psize[0] - 3.0 * cm   # ~26.7 cm with 1.5 cm margins

    doc = SimpleDocTemplate(
        buf, pagesize=psize,
        leftMargin=1.5 * cm, rightMargin=1.5 * cm,
        topMargin=2.0 * cm, bottomMargin=2.0 * cm,
    )
    story = []
    s = _styles()

    # Header
    _doc_header(
        story,
        "Class Attendance Report -- {}".format(classroom.name),
        "Generated: {}".format(_date.today().strftime("%d %B %Y")),
    )

    # Class detail card
    teacher_name = classroom.class_teacher.full_name if classroom.class_teacher else "Not assigned"
    info_rows = [
        ["Class", classroom.name, "Class Teacher", teacher_name],
        ["Month", month_str,      "Total Enrolled", str(len(students))],
    ]
    story.append(_info_table(info_rows, [3.2 * cm, 7.0 * cm, 3.2 * cm, usable_w - (3.2 + 7.0 + 3.2) * cm]))
    story.append(Spacer(1, 10))

    # Summary metrics banner
    col_w_summ = usable_w / 4
    summ_data = [[
        "Total Students: {}".format(class_summary.get("total_students", len(students))),
        "Recorded Sessions: {}".format(class_summary.get("total_sessions", 0)),
        "With Attendance: {}".format(class_summary.get("students_with_records", 0)),
        "Class Attendance Rate: {}".format(_pct(class_summary.get("class_attendance_percentage"))),
    ]]
    summ_tbl = Table(summ_data, colWidths=[col_w_summ] * 4)
    summ_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BLUE_LT),
        ("TEXTCOLOR",     (0, 0), (-1, -1), NAVY),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 9),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOX",           (0, 0), (-1, -1), 0.5, BLUE),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summ_tbl)
    story.append(Spacer(1, 12))

    if not students:
        story.append(Paragraph(
            "No active students are enrolled in this class.",
            s["caption"],
        ))
    else:
        # Table of student records
        col_w = [
            7.0 * cm, 3.2 * cm, 3.0 * cm, 3.0 * cm, 3.0 * cm, 3.5 * cm,
            usable_w - (7.0 + 3.2 + 3.0 + 3.0 + 3.0 + 3.5) * cm,
        ]
        table_rows = [["Student Name", "Roll No", "Present", "Absent", "Late", "Total Days", "Attendance %"]]
        for st in students:
            summ = student_summaries.get(st.id, {"Present": 0, "Absent": 0, "Late": 0, "total_days": 0, "percentage": None})
            table_rows.append([
                st.full_name,
                st.roll_number,
                str(summ["Present"]),
                str(summ["Absent"]),
                str(summ["Late"]),
                str(summ["total_days"]),
                _pct(summ["percentage"]),
            ])

        tbl = Table(table_rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",         (0, 1), (0, -1), "LEFT"),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Note: Attendance percentages are calculated from recorded days only ((Present + Late) / total recorded days x 100). "
            "Unrecorded calendar days are not counted as absent.",
            s["note"],
        ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf


# =============================================================================
# Report E -- Student Fee Statement (portrait A4)
# =============================================================================
def generate_student_fee_pdf(student, classroom, fee_records, payments, summary):
    """
    Build a portrait A4 PDF showing a student's full fee statement, invoice breakdown,
    payment transaction history, and outstanding balance summary.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )
    s = _styles()
    story = []

    _doc_header(
        story,
        "Student Fee Statement",
        "Official student billing statement and payment ledger -- Issued on {}".format(
            _date.today().strftime("%B %d, %Y")
        ),
    )

    class_name = classroom.name if classroom else (student.classroom.name if student.classroom else "N/A")
    info_rows = [
        [
            Paragraph("<b>Student Name:</b>", s["caption"]),
            Paragraph(student.full_name, s["caption"]),
            Paragraph("<b>Roll Number:</b>", s["caption"]),
            Paragraph(student.roll_number, s["caption"]),
        ],
        [
            Paragraph("<b>Classroom:</b>", s["caption"]),
            Paragraph(class_name, s["caption"]),
            Paragraph("<b>Overall Status:</b>", s["caption"]),
            Paragraph(summary.get("status", "N/A"), s["caption"]),
        ],
        [
            Paragraph("<b>Total Assessed:</b>", s["caption"]),
            Paragraph(_money(summary.get("total_assessed", 0)), s["caption"]),
            Paragraph("<b>Total Paid:</b>", s["caption"]),
            Paragraph(_money(summary.get("total_paid", 0)), s["caption"]),
        ],
        [
            Paragraph("<b>Remaining Balance:</b>", s["caption"]),
            Paragraph("<b>{}</b>".format(_money(summary.get("total_balance", 0))), s["caption"]),
            Paragraph("<b>Total Invoices:</b>", s["caption"]),
            Paragraph(str(len(fee_records)), s["caption"]),
        ],
    ]
    col_w_info = [3.2 * cm, 5.8 * cm, 3.2 * cm, 5.8 * cm]
    tbl_info = Table(info_rows, colWidths=col_w_info)
    tbl_info.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("BACKGROUND",    (0, 0), (-1, -1), ROW_ALT),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl_info)
    story.append(Spacer(1, 14))

    # Fee Invoices Section
    story.append(Paragraph("Fee Invoices & Charges", s["exam_heading"]))
    if not fee_records:
        story.append(Paragraph("No fee records found for this student.", s["caption"]))
    else:
        # Col widths sum: 4.5 + 2.5 + 2.5 + 2.8 + 2.8 + 2.9 = 18.0 cm
        col_w_fees = [4.5 * cm, 2.5 * cm, 2.5 * cm, 2.8 * cm, 2.8 * cm, 2.9 * cm]
        fee_rows = [["Fee Title", "Billing Month", "Due Date", "Assessed", "Paid", "Balance"]]
        for f in fee_records:
            fee_rows.append([
                f.title,
                f.billing_month.strftime("%Y-%m") if f.billing_month else "--",
                f.due_date.strftime("%Y-%m-%d") if f.due_date else "--",
                _money(f.amount),
                _money(f.paid_amount),
                _money(f.balance),
            ])
        tbl_fees = Table(fee_rows, colWidths=col_w_fees, repeatRows=1)
        tbl_fees.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",         (0, 1), (0, -1), "LEFT"),
            ("ALIGN",         (3, 1), (5, -1), "RIGHT"),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl_fees)

    story.append(Spacer(1, 14))

    # Payment Transactions Section
    story.append(Paragraph("Payment Transactions & Receipts", s["exam_heading"]))
    if not payments:
        story.append(Paragraph("No payment transactions have been recorded for this student.", s["caption"]))
    else:
        # Col widths sum: 3.5 + 2.8 + 4.5 + 3.6 + 3.6 = 18.0 cm
        col_w_pay = [3.5 * cm, 2.8 * cm, 4.5 * cm, 3.6 * cm, 3.6 * cm]
        pay_rows = [["Receipt #", "Date", "For Fee", "Method", "Amount Paid"]]
        for p in payments:
            pay_rows.append([
                p.receipt_reference or "RCP-{:04d}".format(p.id),
                p.payment_date.strftime("%Y-%m-%d") if p.payment_date else "--",
                p.fee_record.title if p.fee_record else "--",
                p.payment_method or "Cash",
                _money(p.amount),
            ])
        tbl_pay = Table(pay_rows, colWidths=col_w_pay, repeatRows=1)
        tbl_pay.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), BLUE),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",         (2, 1), (2, -1), "LEFT"),
            ("ALIGN",         (4, 1), (4, -1), "RIGHT"),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl_pay)

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Note: Official computer-generated statement. Outstanding amounts should be cleared prior to scheduled due dates.",
        s["note"],
    ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf


# =============================================================================
# Report F -- Class Fee Summary (landscape A4)
# =============================================================================
def generate_class_fee_pdf(classroom, student_fee_data, class_summary):
    """
    Build a landscape A4 PDF displaying class-wide fee collection totals and
    student-by-student assessed, paid, and balance breakdown.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )
    s = _styles()
    story = []

    _doc_header(
        story,
        "Class Fee Collection Report -- {}".format(classroom.name),
        "Classroom fee summary and collection status -- Generated on {}".format(
            _date.today().strftime("%B %d, %Y")
        ),
    )

    # Class summary banner
    summary_rows = [
        [
            Paragraph("<b>Classroom:</b>", s["caption"]),
            Paragraph(classroom.name, s["caption"]),
            Paragraph("<b>Total Assessed:</b>", s["caption"]),
            Paragraph(_money(class_summary.get("total_assessed", 0)), s["caption"]),
        ],
        [
            Paragraph("<b>Enrolled Students:</b>", s["caption"]),
            Paragraph(str(class_summary.get("total_students", len(student_fee_data))), s["caption"]),
            Paragraph("<b>Total Collected:</b>", s["caption"]),
            Paragraph(_money(class_summary.get("total_paid", 0)), s["caption"]),
        ],
        [
            Paragraph("<b>Invoices Issued:</b>", s["caption"]),
            Paragraph(str(class_summary.get("total_invoices", 0)), s["caption"]),
            Paragraph("<b>Outstanding Balance:</b>", s["caption"]),
            Paragraph("<b>{}</b>".format(_money(class_summary.get("total_balance", 0))), s["caption"]),
        ],
        [
            Paragraph("<b>Class Teacher:</b>", s["caption"]),
            Paragraph(classroom.class_teacher.full_name if classroom.class_teacher else "None assigned", s["caption"]),
            Paragraph("<b>Collection Rate:</b>", s["caption"]),
            Paragraph("<b>{}</b>".format(_pct(class_summary.get("collection_rate", 0))), s["caption"]),
        ],
    ]
    col_w_sum = [4.5 * cm, 8.85 * cm, 4.5 * cm, 8.85 * cm]
    tbl_sum = Table(summary_rows, colWidths=col_w_sum)
    tbl_sum.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("BACKGROUND",    (0, 0), (-1, -1), ROW_ALT),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl_sum)
    story.append(Spacer(1, 14))

    # Student Table
    if not student_fee_data:
        story.append(Paragraph("No active students found in this classroom.", s["caption"]))
    else:
        # Col widths sum: 5.5 + 3.0 + 2.2 + 4.0 + 4.0 + 4.0 + 4.0 = 26.7 cm
        col_w = [5.5 * cm, 3.0 * cm, 2.2 * cm, 4.0 * cm, 4.0 * cm, 4.0 * cm, 4.0 * cm]
        table_rows = [["Student Name", "Roll No", "Invoices", "Total Assessed", "Total Paid", "Balance Due", "Status"]]
        for item in student_fee_data:
            table_rows.append([
                item["student"].full_name,
                item["student"].roll_number,
                str(item["invoices_count"]),
                _money(item["total_assessed"]),
                _money(item["total_paid"]),
                _money(item["total_balance"]),
                item["status"],
            ])

        tbl = Table(table_rows, colWidths=col_w, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
            ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("ALIGN",         (0, 1), (0, -1), "LEFT"),
            ("ALIGN",         (3, 1), (5, -1), "RIGHT"),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ]))
        story.append(tbl)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Note: Status indicates overall student fee clearance. "
            "Collection Rate = (Total Collected / Total Assessed) x 100.",
            s["note"],
        ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf


# =============================================================================
# Report G -- Complete Student Academic Profile (portrait A4)
# =============================================================================
def generate_student_overall_profile_pdf(student, attendance_summary, exams_data, fee_summary):
    """
    Build a portrait A4 PDF compiling a student's complete academic dossier:
    Personal Information, Attendance Record, Examination Marks & Results,
    and Financial/Fee Status.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.5 * cm,
        rightMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.8 * cm,
    )
    usable_w = A4[0] - 3.0 * cm  # 18.0 cm
    s = _styles()
    story = []

    _doc_header(
        story,
        "Student Overall Profile & Academic Dossier",
        "Comprehensive Student Report Card -- Generated on {}".format(
            _date.today().strftime("%B %d, %Y")
        ),
    )

    class_name = student.classroom.name if student.classroom else "Unassigned"
    email_user = student.user.username if student.user else "Not Linked"

    # Section 1: Demographics Table (18.0 cm total)
    info_rows = [
        [
            Paragraph("<b>Student Name:</b>", s["caption"]),
            Paragraph(student.full_name, s["caption"]),
            Paragraph("<b>Roll Number:</b>", s["caption"]),
            Paragraph(student.roll_number, s["caption"]),
        ],
        [
            Paragraph("<b>Classroom:</b>", s["caption"]),
            Paragraph(class_name, s["caption"]),
            Paragraph("<b>Account User:</b>", s["caption"]),
            Paragraph(email_user, s["caption"]),
        ],
        [
            Paragraph("<b>Gender:</b>", s["caption"]),
            Paragraph(student.gender or "Not specified", s["caption"]),
            Paragraph("<b>Date of Birth:</b>", s["caption"]),
            Paragraph(student.date_of_birth.strftime("%Y-%m-%d") if student.date_of_birth else "Not provided", s["caption"]),
        ],
        [
            Paragraph("<b>Phone:</b>", s["caption"]),
            Paragraph(student.phone or "Not provided", s["caption"]),
            Paragraph("<b>Enrollment Status:</b>", s["caption"]),
            Paragraph("Active" if student.is_active else "Inactive", s["caption"]),
        ],
        [
            Paragraph("<b>Address:</b>", s["caption"]),
            Paragraph(student.address or "Not provided", s["caption"]),
            Paragraph("<b>Student ID:</b>", s["caption"]),
            Paragraph(str(student.id), s["caption"]),
        ],
    ]
    col_w_info = [3.2 * cm, 5.8 * cm, 3.2 * cm, 5.8 * cm]
    tbl_info = Table(info_rows, colWidths=col_w_info)
    tbl_info.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("BACKGROUND",    (0, 0), (-1, -1), ROW_ALT),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl_info)
    story.append(Spacer(1, 12))

    # Section 2: Attendance Summary
    story.append(Paragraph("1. Attendance Performance Record", s["exam_heading"]))
    att_rate = attendance_summary.get("percentage")
    att_rows = [
        [
            "Recorded Sessions",
            "Present Days",
            "Absent Days",
            "Late Days",
            "Attendance Rate",
        ],
        [
            str(attendance_summary.get("total_days", 0)),
            str(attendance_summary.get("Present", 0)),
            str(attendance_summary.get("Absent", 0)),
            str(attendance_summary.get("Late", 0)),
            _pct(att_rate),
        ],
    ]
    col_w_att = [3.6 * cm, 3.6 * cm, 3.6 * cm, 3.6 * cm, 3.6 * cm]
    tbl_att = Table(att_rows, colWidths=col_w_att)
    tbl_att.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE]),
        ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl_att)
    story.append(Spacer(1, 12))

    # Section 3: Exams & Academic Results
    story.append(Paragraph("2. Academic Examination Results", s["exam_heading"]))
    has_any_results = any(ed.get("has_results") for ed in exams_data) if exams_data else False
    if not has_any_results:
        story.append(Paragraph("No examination marks or results recorded for this student.", s["caption"]))
    else:
        # Col widths sum: 5.5 + 4.5 + 2.5 + 2.5 + 3.0 = 18.0 cm
        col_w_res = [5.5 * cm, 4.5 * cm, 2.5 * cm, 2.5 * cm, 3.0 * cm]
        res_rows = [["Examination", "Subject", "Marks", "Out Of", "Grade / Status"]]
        for ed in exams_data:
            exam = ed["exam"]
            for sub_row in ed.get("subject_rows", []):
                sub = sub_row["subject"]
                res = sub_row["result"]
                if res is not None:
                    res_rows.append([
                        exam.name,
                        sub.name,
                        _fmt(res.marks),
                        str(exam.total_marks),
                        res.grade or "--",
                    ])
        if len(res_rows) == 1:
            story.append(Paragraph("No examination results available.", s["caption"]))
        else:
            tbl_res = Table(res_rows, colWidths=col_w_res, repeatRows=1)
            tbl_res.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
                ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 8),
                ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, ROW_ALT]),
                ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("ALIGN",         (0, 1), (1, -1), "LEFT"),
                ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
                ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
                ("TOPPADDING",    (0, 0), (-1, -1), 3.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ]))
            story.append(tbl_res)
    story.append(Spacer(1, 12))

    # Section 4: Fees and Financial Standing
    story.append(Paragraph("3. Fee Assessment & Financial Standing", s["exam_heading"]))
    fee_rows = [
        [
            "Total Invoices",
            "Total Assessed",
            "Total Paid",
            "Outstanding Balance",
            "Clearance Status",
        ],
        [
            str(fee_summary.get("invoices_count", 0)),
            _money(fee_summary.get("total_assessed", 0)),
            _money(fee_summary.get("total_paid", 0)),
            _money(fee_summary.get("total_balance", 0)),
            fee_summary.get("status", "N/A"),
        ],
    ]
    col_w_fee = [3.6 * cm, 3.6 * cm, 3.6 * cm, 3.6 * cm, 3.6 * cm]
    tbl_fee = Table(fee_rows, colWidths=col_w_fee)
    tbl_fee.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE]),
        ("TEXTCOLOR",     (0, 1), (-1, -1), NAVY),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ("INNERGRID",     (0, 0), (-1, -1), 0.25, BORDER),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl_fee)
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Confidential document issued by SchoolPortal administration. Official verified copy.",
        s["note"],
    ))

    doc.build(story, canvasmaker=_NumberedCanvas)
    buf.seek(0)
    return buf

