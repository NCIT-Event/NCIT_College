"""auth-service data: users, role grants and refresh tokens.

Granting a role to an email that has never signed in creates the user with
status "invited"; the first Google sign-in with that email activates it.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    TypeDecorator,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """Timezone-aware datetimes on every database (SQLite drops the zone)."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    avatar_url: Mapped[str] = mapped_column(String(500), default="")
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    # internal = @ncit.edu.np Google account; external = applicant/alumni via email code (Phase 5)
    kind: Mapped[str] = mapped_column(String(16), default="internal")
    # invited | active | suspended
    status: Mapped[str] = mapped_column(String(16), default="invited", index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    grants: Mapped[list["RoleGrant"]] = relationship(
        back_populates="user", cascade="all, delete-orphan", foreign_keys="RoleGrant.user_id"
    )

    def active_grants(self, now: datetime | None = None) -> list["RoleGrant"]:
        now = now or utcnow()
        return [g for g in self.grants if g.expires_at is None or g.expires_at > now]


class RoleGrant(Base):
    __tablename__ = "role_grants"
    __table_args__ = (UniqueConstraint("user_id", "role", "scope", name="uq_grant_user_role_scope"),)

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32))
    scope: Mapped[str] = mapped_column(String(64), default="*")
    granted_by: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    user: Mapped[User] = relationship(back_populates="grants", foreign_keys=[user_id])

    def as_claim(self) -> dict:
        return {"role": self.role, "scope": self.scope}


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    # every rotation of one sign-in shares a family; reuse of an old token revokes the family
    family_id: Mapped[str] = mapped_column(Uuid(as_uuid=False), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    replaced_by: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    ip: Mapped[str] = mapped_column(String(64), default="")


class OneTimeCode(Base):
    """A 6-digit sign-in code emailed to an applicant or alumnus (they have no college account).

    Only a keyed hash of the code is stored. A code works once, for 10 minutes,
    and is dead after 5 wrong guesses.
    """

    __tablename__ = "one_time_codes"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), index=True)
    purpose: Mapped[str] = mapped_column(String(16))  # applicant | alumni
    code_hash: Mapped[str] = mapped_column(String(64))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    ip: Mapped[str] = mapped_column(String(64), default="")
