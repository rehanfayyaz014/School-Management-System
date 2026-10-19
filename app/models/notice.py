from datetime import date, datetime, timezone

from app import db


class Notice(db.Model):
    __tablename__ = "notices"
    __table_args__ = (
        db.CheckConstraint(
            "audience IN ('all', 'teacher', 'student')",
            name="ck_notice_audience"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    audience = db.Column(db.String(20), nullable=False, default="all")
    notice_date = db.Column(db.Date, nullable=False, default=date.today)
    expires_on = db.Column(db.Date, nullable=True)
    is_published = db.Column(db.Boolean, nullable=False, default=True)
    created_by_user_id = db.Column(
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

    created_by = db.relationship("User", back_populates="notices")
