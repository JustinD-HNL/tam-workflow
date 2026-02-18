"""Generic key-value app settings, persisted in the database."""

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class AppSetting(Base, TimestampMixin):
    """Simple key-value store for app-wide settings (e.g. template URLs)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
