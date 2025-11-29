from sqlalchemy import select, insert, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


from database.models import User, TwitchChannel, user_channel_association, Subscription, SubscriptionSettings
import datetime


async def orm_add_object(obj, session: AsyncSession):

    session.add(obj)
    await session.commit()


async def orm_get_user(session: AsyncSession, user_id: int):

    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    return result.scalar()


async def orm_get_user_channels(session: AsyncSession, user_id: int):

    user = await orm_get_user(session=session, user_id=user_id)
    if not user:
        return []
    query = select(User).options(selectinload(User.channels)).where(User.id == user.id)
    result = await session.execute(query)
    user_with_channels = result.scalar()
    return list(user_with_channels.channels) if user_with_channels else []


async def orm_add_channel(session: AsyncSession, user_id: int, channel_url: str, channel_name: str):

    query = select(User).options(selectinload(User.channels)).where(User.user_id == user_id)
    result = await session.execute(query)
    user = result.scalar()
    
    if not user:
        return None

    query = select(TwitchChannel).where(
        (TwitchChannel.channel_url == channel_url) | (TwitchChannel.channel_name == channel_name)
    )
    result = await session.execute(query)
    existing_channel = result.scalar()
    
    if existing_channel:

        query = select(TwitchChannel).options(selectinload(TwitchChannel.users)).where(TwitchChannel.id == existing_channel.id)
        result = await session.execute(query)
        existing_channel = result.scalar()
        
        if user in existing_channel.users:
            return None 

        stmt = insert(user_channel_association).values(
            user_id=user.id,
            channel_id=existing_channel.id
        )
        await session.execute(stmt)
        await session.commit()
        return existing_channel
    else:
        channel = TwitchChannel(
            channel_url=channel_url,
            channel_name=channel_name
        )
        session.add(channel)
        await session.flush()
        
        stmt = insert(user_channel_association).values(
            user_id=user.id,
            channel_id=channel.id
        )
        await session.execute(stmt)
        await session.commit()
        return channel


async def orm_get_all_channels(session: AsyncSession):
    query = select(TwitchChannel).options(selectinload(TwitchChannel.users))
    result = await session.execute(query)
    return list(result.scalars().all())


async def orm_update_channel_status(session: AsyncSession, channel_id: int, is_live: bool):
    import datetime
    query = select(TwitchChannel).where(TwitchChannel.id == channel_id)
    result = await session.execute(query)
    channel = result.scalar()
    if channel:
        channel.is_live = is_live
        channel.last_checked = datetime.datetime.now()
        await session.commit()


async def orm_delete_channel(session: AsyncSession, channel_id: int, user_id: int):
    query = select(User).where(User.user_id == user_id)
    result = await session.execute(query)
    user = result.scalar()
    
    if not user:
        return False
    
    query = select(TwitchChannel).where(TwitchChannel.id == channel_id)
    result = await session.execute(query)
    channel = result.scalar()
    
    if not channel:
        return False
    
    channel_name = channel.channel_name
    
    check_link_query = select(user_channel_association).where(
        user_channel_association.c.user_id == user.id,
        user_channel_association.c.channel_id == channel_id
    )
    result = await session.execute(check_link_query)
    link_exists = result.first()
    
    if not link_exists:
        return False
    
    stmt = delete(user_channel_association).where(
        user_channel_association.c.user_id == user.id,
        user_channel_association.c.channel_id == channel_id
    )
    result = await session.execute(stmt)
    await session.flush()
    
    check_query = select(user_channel_association.c.user_id).where(
        user_channel_association.c.channel_id == channel_id
    )
    result = await session.execute(check_query)
    remaining_users = result.fetchall()
    
    if len(remaining_users) == 0:
        delete_channel_stmt = delete(TwitchChannel).where(TwitchChannel.id == channel_id)
        await session.execute(delete_channel_stmt)
        print(f"🗑️ Канал {channel_name} удален из БД, так как его больше никто не отслеживает")
    
    await session.commit()
    return True


async def orm_get_user_subscription(session: AsyncSession, user_id: int):
    query = select(User).options(selectinload(User.subscription)).where(User.user_id == user_id)
    result = await session.execute(query)
    user = result.scalar()
    if not user:
        return None
    return user.subscription


async def orm_check_subscription_active(session: AsyncSession, user_id: int) -> bool:
    subscription = await orm_get_user_subscription(session, user_id)
    if not subscription:
        return False
    if not subscription.is_active:
        return False
    if subscription.end_date < datetime.datetime.now():
        subscription.is_active = False
        await session.commit()
        return False
    return True


async def orm_create_subscription(session: AsyncSession, user_id: int, days: int = 30, payment_id: str = None):
    user = await orm_get_user(session, user_id)
    if not user:
        return None
    
    end_date = datetime.datetime.now() + datetime.timedelta(days=days)
    
    existing = await orm_get_user_subscription(session, user_id)
    if existing:
        existing.is_active = True
        existing.start_date = datetime.datetime.now()
        existing.end_date = end_date
        if payment_id:
            existing.payment_id = payment_id
    else:
        subscription = Subscription(
            user_id=user.id,
            is_active=True,
            end_date=end_date,
            payment_id=payment_id
        )
        session.add(subscription)
    
    await session.commit()
    return True


async def orm_get_subscription_settings(session: AsyncSession):
    query = select(SubscriptionSettings).order_by(SubscriptionSettings.id.desc()).limit(1)
    result = await session.execute(query)
    settings = result.scalar()
    if not settings:
        settings = SubscriptionSettings(price=50.0)
        session.add(settings)
        await session.commit()
    return settings


async def orm_update_subscription_price(session: AsyncSession, price: float):
    query = select(SubscriptionSettings).order_by(SubscriptionSettings.id.desc()).limit(1)
    result = await session.execute(query)
    settings = result.scalar()
    if not settings:
        settings = SubscriptionSettings(price=price)
        session.add(settings)
    else:
        settings.price = price
        settings.updated_at = datetime.datetime.now()
    await session.commit()
    return settings


async def orm_ban_user(session: AsyncSession, user_id: int, reason: str = "Нарушение правил"):
    user = await orm_get_user(session, user_id)
    if not user:
        return None
    user.is_banned = True
    await session.commit()
    return user


async def orm_unban_user(session: AsyncSession, user_id: int):
    user = await orm_get_user(session, user_id)
    if not user:
        return None
    user.is_banned = False
    await session.commit()
    return user


async def orm_get_all_users(session: AsyncSession):
    query = select(User).options(selectinload(User.subscription), selectinload(User.channels))
    result = await session.execute(query)
    return list(result.scalars().all())


async def orm_get_statistics(session: AsyncSession):
    from sqlalchemy import func
    
    total_users_query = select(func.count(User.id))
    total_users = (await session.execute(total_users_query)).scalar()
    
    active_subscriptions_query = select(func.count(Subscription.id)).where(
        Subscription.is_active == True,
        Subscription.end_date > datetime.datetime.now()
    )
    active_subscriptions = (await session.execute(active_subscriptions_query)).scalar()
    
    total_channels_query = select(func.count(TwitchChannel.id))
    total_channels = (await session.execute(total_channels_query)).scalar()
    
    banned_users_query = select(func.count(User.id)).where(User.is_banned == True)
    banned_users = (await session.execute(banned_users_query)).scalar()
    
    return {
        "total_users": total_users or 0,
        "active_subscriptions": active_subscriptions or 0,
        "total_channels": total_channels or 0,
        "banned_users": banned_users or 0
    }
