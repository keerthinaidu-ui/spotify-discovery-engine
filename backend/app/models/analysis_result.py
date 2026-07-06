import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, JSONTextCompat


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feedback_item_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("feedback_items.id"), nullable=True, index=True
    )
    result_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    label: Mapped[str | None] = mapped_column(String(256), nullable=True)
    payload_json: Mapped[str | None] = mapped_column(JSONTextCompat, nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    analyzed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
