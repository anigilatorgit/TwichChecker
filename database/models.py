import datetime
from typing import List, Optional

from sqlalchemy import DateTime, func, ForeignKey, Column, Integer, String, Float, JSON, PickleType, Table
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    ...


user_channel_association = Table(
    'user_channel_association',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('user.id'), primary_key=True),
    Column('channel_id', Integer, ForeignKey('twitch_channel.id'), primary_key=True)
)


class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(nullable=False)
    reg_date: Mapped[datetime.datetime] = mapped_column(nullable=False, server_default=func.now())
    is_banned: Mapped[bool] = mapped_column(default=False, nullable=False)

    channels: Mapped[List["TwitchChannel"]] = relationship(
        "TwitchChannel",
        secondary=user_channel_association,
        back_populates="users"
    )
    subscription: Mapped[Optional["Subscription"]] = relationship(
        "Subscription",
        back_populates="user",
        uselist=False
    )


class TwitchChannel(Base):
    __tablename__ = 'twitch_channel'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_url: Mapped[str] = mapped_column(nullable=False, unique=True)
    channel_name: Mapped[str] = mapped_column(nullable=False, unique=True)
    is_live: Mapped[bool] = mapped_column(default=False, nullable=False)
    last_checked: Mapped[datetime.datetime] = mapped_column(nullable=True)
    added_date: Mapped[datetime.datetime] = mapped_column(nullable=False, server_default=func.now())

    users: Mapped[List["User"]] = relationship(
        "User",
        secondary=user_channel_association,
        back_populates="channels"
    )


class Subscription(Base):
    __tablename__ = 'subscription'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    start_date: Mapped[datetime.datetime] = mapped_column(nullable=False, server_default=func.now())
    end_date: Mapped[datetime.datetime] = mapped_column(nullable=False)
    payment_id: Mapped[Optional[str]] = mapped_column(nullable=True)
    
    user: Mapped["User"] = relationship("User", back_populates="subscription")


class SubscriptionSettings(Base):
    __tablename__ = 'subscription_settings'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    price: Mapped[float] = mapped_column(default=50.0, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(nullable=False, server_default=func.now(), onupdate=func.now())