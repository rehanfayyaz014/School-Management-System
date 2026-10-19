from datetime import datetime, timezone

from app import db


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id",
            "attendance_date",
            name="uq_attendance_student_date"
        ),
        db.CheckConstraint(
            "status IN ('Present', 'Absent', 'Late')",
            name="ck_attendance_status"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False
    )
    class_id = db.Column(
        db.Integer,
        db.ForeignKey("classrooms.id", ondelete="CASCADE"),
        nullable=False
    )
    attendance_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    recorded_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    student = db.relationship("Student", back_populates="attendance_records")
    classroom = db.relationship(
        "Classroom",
        back_populates="attendance_records"
    )
    recorded_by = db.relationship(
        "User",
        back_populates="attendance_records"
    )
