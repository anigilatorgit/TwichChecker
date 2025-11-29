from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import re
import datetime

from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.models import User
from database.orm_query import (
    orm_get_user, 
    orm_add_object, 
    orm_get_user_channels,
    orm_add_channel,
    orm_check_subscription_active,
    orm_get_user_subscription,
    orm_get_subscription_settings,
    orm_create_subscription
)
from sqlalchemy.ext.asyncio import AsyncSession

from kbrds.inline import get_main_inline_kb, get_callback_btns
from kbrds.reply import menu_reply_markup
from handlers.states import AddChannel
from services.twitch_checker import extract_channel_name
import config

user_router = Router()


@user_router.message(F.text == "/start")
@user_router.message(F.text == "💎Меню")
async def start_command(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    user = await orm_get_user(user_id=user_id, session=session)
    if not user:
        user = User(user_id=user_id)
        await orm_add_object(obj=user, session=session)

    has_subscription = await orm_check_subscription_active(session, user_id)
    kbrd = get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_subscription)
    await message.answer(
        f"Приветствую в боте, {message.from_user.first_name}! 👋\n\n"
        "Выберите действие:",
        reply_markup=kbrd
    )
    await message.answer(
        "💎 Используйте кнопку ниже для возврата в меню:",
        reply_markup=menu_reply_markup
    )


@user_router.callback_query(F.data == "profile")
async def show_profile(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    user = await orm_get_user(user_id=user_id, session=session)
    
    if not user:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    
    channels = await orm_get_user_channels(session=session, user_id=user_id)
    channels_count = len(channels)
    
    has_subscription = await orm_check_subscription_active(session, user_id)
    subscription = await orm_get_user_subscription(session, user_id)
    
    subscription_info = ""
    if has_subscription and subscription:
        end_date = subscription.end_date.strftime('%d.%m.%Y %H:%M')
        subscription_info = f"\n💎 <b>Подписка активна</b>\n📅 Действует до: {end_date}"
    else:
        subscription_info = "\n❌ <b>Подписка не активна</b>\n💎 Оформите подписку для неограниченного количества каналов"
    
    profile_text = (
        f"👤 <b>Профиль пользователя</b>\n\n"
        f"🆔 ID: <code>{user.user_id}</code>\n"
        f"📅 Дата регистрации: {user.reg_date.strftime('%d.%m.%Y %H:%M')}\n"
        f"📺 Отслеживаемых каналов: {channels_count}"
        f"{subscription_info}"
    )
    
    has_photo = callback.message.photo is not None
    
    try:
        user_photos = await callback.bot.get_user_profile_photos(user_id=user_id, limit=1)
        if user_photos.total_count > 0:
            photo = user_photos.photos[0][-1]
            photo_file = await callback.bot.get_file(photo.file_id)
            
            if has_photo:
                has_sub = await orm_check_subscription_active(session, user_id)
                try:
                    await callback.message.edit_caption(
                        caption=profile_text,
                        reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
                    )
                except:
                    await callback.message.delete()
                    has_sub = await orm_check_subscription_active(session, user_id)
                    await callback.message.answer_photo(
                        photo=photo_file.file_id,
                        caption=profile_text,
                        reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
                    )
            else:
                try:
                    await callback.message.delete()
                except:
                    pass
                await callback.message.answer_photo(
                    photo=photo_file.file_id,
                    caption=profile_text,
                    reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL)
                )
        else:
            if has_photo:
                try:
                    await callback.message.delete()
                except:
                    pass
                has_sub = await orm_check_subscription_active(session, user_id)
                await callback.message.answer(
                    profile_text,
                    reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
                )
            else:
                has_sub = await orm_check_subscription_active(session, user_id)
                try:
                    await callback.message.edit_text(
                        profile_text,
                        reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
                    )
                except:
                    await callback.message.answer(
                        profile_text,
                        reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
                    )
    except Exception as e:
        if has_photo:
            try:
                await callback.message.delete()
            except:
                pass
        has_sub = await orm_check_subscription_active(session, user_id)
        try:
            await callback.message.edit_text(
                profile_text,
                reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
            )
        except:
            await callback.message.answer(
                profile_text,
                reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
            )
    
    await callback.answer()


@user_router.callback_query(F.data == "add_channel")
async def add_channel_start(callback: types.CallbackQuery, state: FSMContext):
    has_photo = callback.message.photo is not None
    
    text = "📝 Отправьте ссылку на Twitch канал.\n\nПример: https://www.twitch.tv/username\nили: twitch.tv/username"
    
    if has_photo:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(
            text,
            disable_web_page_preview=True,
            reply_markup=menu_reply_markup
        )
    else:
        try:
            await callback.message.edit_text(
                text,
                disable_web_page_preview=True,
                reply_markup=menu_reply_markup
            )
        except:
            await callback.message.answer(
                text,
                disable_web_page_preview=True,
                reply_markup=menu_reply_markup
            )
    await state.set_state(AddChannel.waiting_for_url)
    await callback.answer()


@user_router.message(StateFilter(AddChannel.waiting_for_url))
async def add_channel_process(message: types.Message, state: FSMContext, session: AsyncSession):
    url = message.text.strip()
    
    if not re.search(r'twitch\.tv/', url, re.IGNORECASE):
        await message.answer(
            "❌ Это не похоже на ссылку на Twitch канал.\n"
            "Пожалуйста, отправьте корректную ссылку.\n\n"
            "Пример: https://www.twitch.tv/username",
            disable_web_page_preview=True,
            reply_markup=menu_reply_markup
        )
        return
    
    channel_name = extract_channel_name(url)
    if not channel_name:
        await message.answer(
            "❌ Не удалось извлечь имя канала из ссылки.\n"
            "Пожалуйста, проверьте ссылку и попробуйте снова.",
            disable_web_page_preview=True,
            reply_markup=menu_reply_markup
        )
        await state.clear()
        return
    
    user_id = message.from_user.id
    user = await orm_get_user(user_id=user_id, session=session)
    
    if user and user.is_banned:
        await message.answer(
            "❌ Вы заблокированы и не можете добавлять каналы.",
            disable_web_page_preview=True,
            reply_markup=menu_reply_markup
        )
        await state.clear()
        return
    
    has_subscription = await orm_check_subscription_active(session, user_id)
    channels = await orm_get_user_channels(session=session, user_id=user_id)
    
    if not has_subscription and len(channels) >= 1:
        settings = await orm_get_subscription_settings(session)
        await message.answer(
            f"❌ <b>Лимит каналов достигнут!</b>\n\n"
            f"Без подписки можно отслеживать только <b>1 канал</b>.\n\n"
            f"💎 Оформите подписку за <b>{settings.price:.0f}₽/месяц</b> для неограниченного количества каналов!",
            disable_web_page_preview=True,
            reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=False)
        )
        await state.clear()
        return
    
    channel = await orm_add_channel(
        session=session,
        user_id=user_id,
        channel_url=url,
        channel_name=channel_name
    )
    
    has_sub = await orm_check_subscription_active(session, user_id)
    
    if channel:
        await message.answer(
            f"✅ Канал <b>{channel_name}</b> успешно добавлен!\n\n"
            "Теперь вы будете получать уведомления о начале стрима.",
            reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub),
            disable_web_page_preview=True
        )
    else:
        await message.answer(
            f"⚠️ Канал <b>{channel_name}</b> уже добавлен в ваш список.",
            reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub),
            disable_web_page_preview=True
        )
    
    await state.clear()


@user_router.callback_query(F.data == "list_channels")
async def list_channels(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    channels = await orm_get_user_channels(session=session, user_id=user_id)
    
    keyboard = InlineKeyboardBuilder()
    
    if not channels:
        text = "📋 У вас пока нет отслеживаемых каналов.\n\nИспользуйте кнопку '➕ Добавить' для добавления канала."
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    else:
        text = "📋 <b>Ваши отслеживаемые каналы:</b>\n\n"
        for i, channel in enumerate(channels, 1):
            status_emoji = "🟢" if channel.is_live else "🔴"
            status_text = "ONLINE" if channel.is_live else "OFFLINE"
            text += f"{i}. {status_emoji} <b>{channel.channel_name}</b> - {status_text}\n"
            
            keyboard.row(
                InlineKeyboardButton(
                    text=f"{status_emoji} {channel.channel_name}",
                    url=channel.channel_url
                ),
                InlineKeyboardButton(
                    text="❌",
                    callback_data=f"delete_channel_{channel.id}"
                )
            )
        
        keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    
    has_photo = callback.message.photo is not None
    
    if has_photo:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(
            text,
            reply_markup=keyboard.as_markup()
        )
    else:
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboard.as_markup()
            )
        except:
            await callback.message.answer(
                text,
                reply_markup=keyboard.as_markup()
            )
    
    await callback.answer()


@user_router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, session: AsyncSession):
    has_photo = callback.message.photo is not None
    
    if has_photo:
        try:
            await callback.message.delete()
        except:
            pass
        has_sub = await orm_check_subscription_active(session, callback.from_user.id)
        await callback.message.answer(
            "Выберите действие:",
            reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
        )
    else:
        has_sub = await orm_check_subscription_active(session, callback.from_user.id)
        try:
            await callback.message.edit_text(
                "Выберите действие:",
                reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
            )
        except:
            await callback.message.answer(
                "Выберите действие:",
                reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
            )
    await callback.answer()


@user_router.callback_query(F.data.startswith("delete_channel_"))
async def delete_channel(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    
    try:
        channel_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка при удалении канала", show_alert=True)
        return
    
    from database.orm_query import orm_delete_channel, orm_get_user_channels
    deleted = await orm_delete_channel(session=session, channel_id=channel_id, user_id=user_id)
    
    if deleted:
        await callback.answer("✅ Канал удален", show_alert=False)
        
        channels = await orm_get_user_channels(session=session, user_id=user_id)
        
        await list_channels(callback, session)
    else:
        await callback.answer("❌ Канал не найден или у вас нет прав на его удаление", show_alert=True)


@user_router.callback_query(F.data == "subscription")
async def show_subscription(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    has_subscription = await orm_check_subscription_active(session, user_id)
    
    if has_subscription:
        subscription = await orm_get_user_subscription(session, user_id)
        end_date = subscription.end_date.strftime('%d.%m.%Y %H:%M')
        text = (
            f"💎 <b>У вас активная подписка!</b>\n\n"
            f"📅 Подписка действует до: {end_date}\n\n"
            f"✅ Вы можете отслеживать неограниченное количество каналов!"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
    else:
        settings = await orm_get_subscription_settings(session)
        text = (
            f"💎 <b>Подписка на бота</b>\n\n"
            f"📺 <b>Без подписки:</b>\n"
            f"• Можно отслеживать только <b>1 канал</b>\n\n"
            f"💎 <b>С подпиской:</b>\n"
            f"• Неограниченное количество каналов\n"
            f"• Приоритетная поддержка\n"
            f"• Все функции бота\n\n"
            f"💰 <b>Цена: {settings.price:.0f}₽/месяц</b>\n\n"
            f"💳 Оплата через <b>ЮMoney</b>"
        )
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="💳 Оплатить подписку", callback_data="pay_subscription"))
        keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main"))
        keyboard.adjust(1)
    
    has_photo = callback.message.photo is not None
    
    if has_photo:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(
            text,
            reply_markup=keyboard.as_markup()
        )
    else:
        try:
            await callback.message.edit_text(
                text,
                reply_markup=keyboard.as_markup()
            )
        except:
            await callback.message.answer(
                text,
                reply_markup=keyboard.as_markup()
            )
    
    await callback.answer()


@user_router.callback_query(F.data == "pay_subscription")
async def pay_subscription(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    settings = await orm_get_subscription_settings(session)
    
    from services.payment_service import create_payment
    
    payment = await create_payment(
        user_id=user_id,
        amount=settings.price,
        description=f"Подписка на бота на 30 дней"
    )
    
    if payment and payment.get("confirmation_url"):
        from database.orm_query import orm_get_user_subscription
        subscription = await orm_get_user_subscription(session, user_id)
        if subscription:
            subscription.payment_id = payment["payment_id"]
            await session.commit()
        else:
            from database.models import Subscription
            user = await orm_get_user(user_id=user_id, session=session)
            if user:
                temp_subscription = Subscription(
                    user_id=user.id,
                    is_active=False,
                    end_date=datetime.datetime.now(),
                    payment_id=payment["payment_id"]
                )
                session.add(temp_subscription)
                await session.commit()
        keyboard = InlineKeyboardBuilder()
        keyboard.add(InlineKeyboardButton(text="💳 Оплатить", url=payment["confirmation_url"]))
        keyboard.add(InlineKeyboardButton(text="✅ Проверить оплату", callback_data="check_payment_btn"))
        keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="subscription"))
        keyboard.adjust(1,)
        
        text = (
            f"💳 <b>Оплата подписки через ЮMoney</b>\n\n"
            f"💰 Сумма: <b>{settings.price:.0f}₽</b>\n"
            f"📅 Срок: <b>30 дней</b>\n\n"
            f"Нажмите кнопку ниже для перехода на страницу оплаты.\n"
            f"После оплаты нажмите '✅ Проверить оплату' для активации подписки."
        )
        
        has_photo = callback.message.photo is not None
        
        if has_photo:
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer(
                text,
                reply_markup=keyboard.as_markup()
            )
        else:
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=keyboard.as_markup()
                )
            except:
                await callback.message.answer(
                    text,
                    reply_markup=keyboard.as_markup()
                )
    else:
        await callback.answer("❌ Ошибка при создании платежа. Попробуйте позже.", show_alert=True)
    
    await callback.answer()


@user_router.callback_query(F.data == "check_payment_btn")
async def check_payment_callback(callback: types.CallbackQuery, session: AsyncSession):
    user_id = callback.from_user.id
    subscription = await orm_get_user_subscription(session, user_id)
    
    if subscription and subscription.payment_id:
        from services.payment_service import check_payment_status
        payment_status = await check_payment_status(subscription.payment_id)
        
        if payment_status:
            has_sub = await orm_check_subscription_active(session, user_id)
            if not has_sub:
                await orm_create_subscription(session, user_id, subscription.payment_id)
                has_sub = True
                await callback.message.edit_text(
                    "✅ <b>Платеж подтвержден!</b>\n\n"
                    "Ваша подписка активирована на 30 дней.",
                    reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
                )
            else:
                await callback.answer("✅ Ваша подписка уже активна!", show_alert=True)
        else:
            await callback.answer(
                "⏳ Платеж еще не подтвержден. Если вы уже оплатили, подождите несколько минут.",
                show_alert=True
            )
    else:
        await callback.answer("❌ У вас нет активных платежей для проверки.", show_alert=True)
    
    await callback.answer()


@user_router.message(F.text == "/check_payment")
async def check_payment_command(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    subscription = await orm_get_user_subscription(session, user_id)
    
    if subscription and subscription.payment_id:
        from services.payment_service import check_payment_status
        payment_status = await check_payment_status(subscription.payment_id)
        
        if payment_status:
            has_sub = await orm_check_subscription_active(session, user_id)
            if not has_sub:
                await orm_create_subscription(session, user_id, subscription.payment_id)
                await message.answer(
                    "✅ <b>Платеж подтвержден!</b>\n\n"
                    "Ваша подписка активирована на 30 дней.",
                    reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=True)
                )
            else:
                await message.answer("✅ Ваша подписка уже активна!")
        else:
            await message.answer(
                "⏳ Платеж еще не подтвержден.\n\n"
                "Если вы уже оплатили, подождите несколько минут или напишите в поддержку."
            )
    else:
        await message.answer("❌ У вас нет активных платежей для проверки.")


@user_router.message()
async def handle_user_message(message: types.Message, session: AsyncSession):
    has_sub = await orm_check_subscription_active(session, message.from_user.id)
    await message.answer(
        "Используйте кнопки для навигации:",
        reply_markup=get_main_inline_kb(support_url=config.SUPPORT_URL, has_subscription=has_sub)
    )
