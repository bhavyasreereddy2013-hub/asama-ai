from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=_utcnow_naive)

    profile = relationship("BusinessProfile", back_populates="user", uselist=False)
    agents = relationship("Agent", back_populates="user")
    sent_requests = relationship("ConnectionRequest", foreign_keys="ConnectionRequest.sender_id", back_populates="sender")
    received_requests = relationship("ConnectionRequest", foreign_keys="ConnectionRequest.receiver_id", back_populates="receiver")


class BusinessProfile(Base):
    __tablename__ = "business_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    company_name = Column(String(255), nullable=False)
    industry = Column(String(255), nullable=False)
    description = Column(Text, default="")
    products = Column(Text, default="")
    services = Column(Text, default="")
    location = Column(String(255), default="")
    requirements = Column(Text, default="")
    interests = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow_naive)

    user = relationship("User", back_populates="profile")


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    industry = Column(String(255), nullable=False)
    summary = Column(Text, default="")
    business_goals = Column(Text, default="")
    interests = Column(Text, default="")
    location = Column(String(255), default="")
    created_at = Column(DateTime, default=_utcnow_naive)

    user = relationship("User", back_populates="agents")
    posts = relationship("Post", back_populates="agent")


class Post(Base):
    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(String(255), default="General")
    requirements = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow_naive)

    agent = relationship("Agent", back_populates="posts")


class SavedPost(Base):
    __tablename__ = "saved_posts"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_saved_posts_user_post"),)

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False, index=True)
    saved_at = Column(DateTime, default=_utcnow_naive, nullable=False)

    user = relationship("User")
    post = relationship("Post")


class ConnectionRequest(Base):
    __tablename__ = "connection_requests"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(32), default="pending")
    note = Column(Text, default="")
    created_at = Column(DateTime, default=_utcnow_naive)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_requests")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_requests")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String(40), nullable=False)
    title = Column(String(200), nullable=False)
    body = Column(Text, nullable=False)
    related_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    connection_request_id = Column(Integer, ForeignKey("connection_requests.id"), nullable=True)
    message_id = Column(Integer, ForeignKey("messages.id"), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=_utcnow_naive, nullable=False, index=True)

    related_user = relationship("User", foreign_keys=[related_user_id])
