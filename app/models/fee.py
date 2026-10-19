from datetime import date, datetime, timezone

from app import db


class FeeRecord(db.Model):
    __tablename__ = "fee_records"
    __table_args__ = (
        db.UniqueConstraint(
            "student_id", "title", "billing_month",
            name="uq_fee_student_title_month"
        ),
        db.CheckConstraint("amount > 0", name="ck_fee_amount_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False
    )
    title = db.Column(db.String(120), nullable=False)
    billing_month = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    notes = db.Column(db.String(250), nullable=True)
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

    student = db.relationship("Student", back_populates="fee_records")
    payments = db.relationship(
        "FeePayment",
        back_populates="fee_record",
        cascade="all, delete-orphan",
        order_by="FeePayment.payment_date.desc()"
    )
    created_by = db.relationship("User", back_populates="created_fee_records")

    @property
    def paid_amount(self):
        return sum((payment.amount for payment in self.payments), 0)

    @property
    def balance(self):
        return max(self.amount - self.paid_amount, 0)

    @property
    def status(self):
        if self.balance <= 0:
            return "Paid"
        if self.paid_amount > 0:
            return "Partial"
        if self.due_date < date.today():
            return "Overdue"
        return "Unpaid"


class FeePayment(db.Model):
    __tablename__ = "fee_payments"
    __table_args__ = (
        db.CheckConstraint("amount > 0", name="ck_fee_payment_amount_positive"),
    )

    id = db.Column(db.Integer, primary_key=True)
    fee_record_id = db.Column(
        db.Integer,
        db.ForeignKey("fee_records.id", ondelete="CASCADE"),
        nullable=False
    )
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=date.today)
    payment_method = db.Column(db.String(30), nullable=False, default="Cash")
    receipt_reference = db.Column(db.String(80), unique=True, nullable=True)
    notes = db.Column(db.String(250), nullable=True)
    received_by_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    fee_record = db.relationship("FeeRecord", back_populates="payments")
    received_by = db.relationship("User", back_populates="received_fee_payments")
