from datetime import datetime, timezone

from app import db


class Subject(db.Model):
    __tablename__ = "subjects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.String(250), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    assignments = db.relationship(
        "ClassSubjectAssignment",
        back_populates="subject",
        cascade="all, delete-orphan"
    )
    exam_results = db.relationship("ExamResult", back_populates="subject")

    def __repr__(self):
        return f"<Subject {self.name}>"
