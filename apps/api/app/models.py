from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class User(Base, Timestamped):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(32), default="member")


class Session(Base, Timestamped):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Conversation(Base, Timestamped):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")


class Message(Base, Timestamped):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Memory(Base, Timestamped):
    __tablename__ = "memories"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="fact")
    content: Mapped[str] = mapped_column(Text)
    source_conversation_id: Mapped[int | None] = mapped_column(ForeignKey("conversations.id"), nullable=True)


class Project(Base, Timestamped):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")


class Task(Base, Timestamped):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(240))
    status: Mapped[str] = mapped_column(String(32), default="todo")
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    due_date: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Mission(Base, Timestamped):
    __tablename__ = "missions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(240))
    objective: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="planned")
    result: Mapped[str | None] = mapped_column(Text, nullable=True)


class MissionStep(Base, Timestamped):
    __tablename__ = "mission_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    mission_id: Mapped[int] = mapped_column(ForeignKey("missions.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(240))
    tool_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    permission_level: Mapped[str] = mapped_column(String(32), default="READ_ONLY")
    status: Mapped[str] = mapped_column(String(32), default="pending")


class Approval(Base, Timestamped):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mission_id: Mapped[int | None] = mapped_column(ForeignKey("missions.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(240))
    reason: Mapped[str] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")


class Activity(Base, Timestamped):
    __tablename__ = "activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mission_id: Mapped[int | None] = mapped_column(ForeignKey("missions.id"), nullable=True)
    tool: Mapped[str | None] = mapped_column(String(80), nullable=True)
    action: Mapped[str] = mapped_column(String(240))
    result: Mapped[str] = mapped_column(Text, default="")
    permission_decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)


class Upgrade(Base, Timestamped):
    """A user-owned, approval-gated proposal to modify this installation."""
    __tablename__ = "upgrades"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    feature_request: Mapped[str] = mapped_column(Text)
    plan: Mapped[str] = mapped_column(Text)
    affected_files: Mapped[str] = mapped_column(Text, default="[]")
    risk: Mapped[str] = mapped_column(String(32), default="medium")
    patch: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="proposed", index=True)
    branch_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    checkpoint_sha: Mapped[str | None] = mapped_column(String(80), nullable=True)
    verification_log: Mapped[str] = mapped_column(Text, default="")
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class UpgradeEvent(Base):
    __tablename__ = "upgrade_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    upgrade_id: Mapped[int] = mapped_column(ForeignKey("upgrades.id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
