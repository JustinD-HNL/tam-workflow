"""OAuth app configuration model — stores client_id/secret per integration in the DB."""

from typing import Optional

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin


class OAuthAppConfig(Base, TimestampMixin):
    """Stores OAuth app credentials (client_id, client_secret) per integration.

    This allows users to configure OAuth apps through the UI instead of .env files.
    Values are stored encrypted.
    """

    __tablename__ = "oauth_app_configs"

    integration_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    client_id_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    client_secret_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    # Extra config (e.g., Slack app_token for Socket Mode), stored encrypted as JSON string
    extra_config_encrypted: Mapped[Optional[str]] = mapped_column(Text)
