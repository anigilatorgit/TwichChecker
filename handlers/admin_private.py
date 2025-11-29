from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from database.models import User
from database.orm_query import (
    orm_add_object, 
    orm_get_user,
    orm_get_all_users,
    orm_get_statistics,
    orm_get_subscription_settings,
    orm_update_subscription_price,
    orm_ban_user,
    orm_unban_user,
    orm_create_subscription,
    orm_check_subscription_active,
    orm_get_user_subscription
)
from filters.chat_types import IsAdmin
from sqlalchemy.ext.asyncio import AsyncSession
from handlers.states import AdminGiveSubscription, AdminBanUser, AdminUnbanUser
from kbrds.inline import get_main_inline_kb
import config
import re


admin_router = Router()
admin_router.message.filter(IsAdmin())
admin_router.callback_query.filter(IsAdmin())


@admin_router.message(F.text == "/admin")
async def admin_start(message: types.Message, session: AsyncSession):
    user_id = message.from_user.id
    user = await orm_get_user(user_id=user_id, session=session)
    if not user:
        user = User(user_id=user_id)
        await orm_add_object(obj=user, session=session)

    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton(text="💰 Управление ценой", callback_data="admin_price"))
    keyboard.add(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    keyboard.add(InlineKeyboardButton(text="💎 Выдать подписку", callback_data="admin_give_sub"))
    keyboard.adjust(1)
    
    await message.answer(
        f"🔐 <b>Админ-панель</b>\n\n"
        f"Выберите действие:",
        reply_markup=keyboard.as_markup()
    )


@admin_router.callback_query(F.data == "admin_stats")
async def admin_statistics(callback: types.CallbackQuery, session: AsyncSession):
    stats = await orm_get_statistics(session)
    
    text = (
        f"📊 <b>Статистика бота</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"💎 Активных подписок: <b>{stats['active_subscriptions']}</b>\n"
        f"📺 Всего каналов: <b>{stats['total_channels']}</b>\n"
        f"🚫 Заблокированных: <b>{stats['banned_users']}</b>"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    
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


@admin_router.callback_query(F.data == "admin_price")
async def admin_price_menu(callback: types.CallbackQuery, session: AsyncSession):
    settings = await orm_get_subscription_settings(session)
    
    text = (
        f"💰 <b>Управление ценой подписки</b>\n\n"
        f"Текущая цена: <b>{settings.price:.0f}₽/месяц</b>\n\n"
        f"Отправьте новую цену в рублях:"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    
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


@admin_router.message(F.text.regexp(r'^\d+(\.\d+)?$'))
async def admin_set_price(message: types.Message, session: AsyncSession, state: FSMContext):
    current_state = await state.get_state()
    
    if current_state in [AdminGiveSubscription.waiting_for_user_id_and_days, 
                         AdminBanUser.waiting_for_user_id, 
                         AdminBanUser.waiting_for_reason,
                         AdminUnbanUser.waiting_for_user_id]:
        return
    
    try:
        price = float(message.text)
        if price < 0:
            await message.answer("❌ Цена не может быть отрицательной")
            return
        
        await orm_update_subscription_price(session, price)
        await message.answer(f"✅ Цена подписки обновлена: <b>{price:.0f}₽/месяц</b>")
    except ValueError:
        await message.answer("❌ Неверный формат цены. Используйте число (например: 50 или 99.99)")


@admin_router.callback_query(F.data == "admin_users")
async def admin_users_menu(callback: types.CallbackQuery):
    text = (
        f"👥 <b>Управление пользователями</b>\n\n"
        f"Выберите действие:"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🚫 Забанить пользователя", callback_data="admin_ban"))
    keyboard.add(InlineKeyboardButton(text="✅ Разбанить пользователя", callback_data="admin_unban"))
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    
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


@admin_router.callback_query(F.data == "admin_ban")
async def admin_ban_start(callback: types.CallbackQuery, state: FSMContext):
    text = (
        f"🚫 <b>Забанить пользователя</b>\n\n"
        f"Отправьте ID пользователя в формате:\n"
        f"<code>USER_ID</code>\n\n"
        f"Пример: <code>123456789</code>"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users"))
    
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
    
    await state.set_state(AdminBanUser.waiting_for_user_id)
    await callback.answer()


@admin_router.message(StateFilter(AdminBanUser.waiting_for_user_id))
async def admin_ban_user_id(message: types.Message, state: FSMContext, session: AsyncSession):
    try:
        user_id = int(message.text.strip())
        user = await orm_get_user(user_id=user_id, session=session)
        
        if not user:
            await message.answer(f"❌ Пользователь <code>{user_id}</code> не найден")
            await state.clear()
            return
        
        if user.is_banned:
            await message.answer(f"⚠️ Пользователь <code>{user_id}</code> уже заблокирован")
            await state.clear()
            return
        
        await state.update_data(user_id=user_id)
        await state.set_state(AdminBanUser.waiting_for_reason)
        
        await message.answer(
            f"👤 Пользователь найден: <code>{user_id}</code>\n\n"
            f"Отправьте причину бана:"
        )
    except ValueError:
        await message.answer("❌ Неверный формат. Отправьте только ID пользователя (число)")


@admin_router.message(StateFilter(AdminBanUser.waiting_for_reason))
async def admin_ban_reason(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    reason = message.text.strip()
    data = await state.get_data()
    user_id = data.get("user_id")
    
    if not user_id:
        await message.answer("❌ Ошибка: не найден ID пользователя")
        await state.clear()
        return
    
    user = await orm_ban_user(session, user_id, reason)
    
    if user:
        await message.answer(
            f"✅ Пользователь <code>{user_id}</code> заблокирован\n\n"
            f"📝 Причина: {reason}"
        )
        
        try:
            await bot.send_message(
                chat_id=user_id,
                text=(
                    f"🚫 <b>Вы были заблокированы</b>\n\n"
                    f"📝 <b>Причина:</b> {reason}\n\n"
                    f"Если вы считаете, что это ошибка, обратитесь в поддержку."
                )
            )
        except Exception as e:
            print(f"⚠️ Не удалось отправить уведомление пользователю {user_id}: {e}")
    else:
        await message.answer(f"❌ Пользователь <code>{user_id}</code> не найден")
    
    await state.clear()


@admin_router.callback_query(F.data == "admin_unban")
async def admin_unban_start(callback: types.CallbackQuery, state: FSMContext):
    text = (
        f"✅ <b>Разбанить пользователя</b>\n\n"
        f"Отправьте ID пользователя в формате:\n"
        f"<code>USER_ID</code>\n\n"
        f"Пример: <code>123456789</code>"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_users"))
    
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
    
    await state.set_state(AdminUnbanUser.waiting_for_user_id)
    await callback.answer()


@admin_router.message(StateFilter(AdminUnbanUser.waiting_for_user_id))
async def admin_unban_user_id(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    try:
        user_id = int(message.text.strip())
        user = await orm_unban_user(session, user_id)
        
        if user:
            await message.answer(f"✅ Пользователь <code>{user_id}</code> разблокирован")
            
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Вы были разблокированы</b>\n\n"
                        f"Добро пожаловать обратно! Теперь вы можете использовать бота."
                    )
                )
            except Exception as e:
                print(f"⚠️ Не удалось отправить уведомление пользователю {user_id}: {e}")
        else:
            await message.answer(f"❌ Пользователь <code>{user_id}</code> не найден")
    except ValueError:
        await message.answer("❌ Неверный формат. Отправьте только ID пользователя (число)")
    
    await state.clear()


@admin_router.callback_query(F.data == "admin_give_sub")
async def admin_give_subscription(callback: types.CallbackQuery, state: FSMContext):
    text = (
        f"💎 <b>Выдача подписки</b>\n\n"
        f"Отправьте данные в формате:\n"
        f"<code>USER_ID КОЛИЧЕСТВО_ДНЕЙ</code>\n\n"
        f"Пример: <code>123456789 30</code>\n"
        f"Пример: <code>123456789 7</code>"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back"))
    
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
    
    await state.set_state(AdminGiveSubscription.waiting_for_user_id_and_days)
    await callback.answer()


@admin_router.message(StateFilter(AdminGiveSubscription.waiting_for_user_id_and_days))
async def admin_give_subscription_process(message: types.Message, state: FSMContext, session: AsyncSession, bot: Bot):
    try:
        parts = message.text.strip().split()
        if len(parts) != 2:
            await message.answer(
                "❌ Неверный формат.\n\n"
                "Используйте: <code>USER_ID КОЛИЧЕСТВО_ДНЕЙ</code>\n"
                "Пример: <code>123456789 30</code>"
            )
            return
        
        user_id = int(parts[0])
        days = int(parts[1])
        
        if days <= 0:
            await message.answer("❌ Количество дней должно быть больше 0")
            return
        
        if days > 365:
            await message.answer("❌ Максимальное количество дней: 365")
            return
        
        user = await orm_get_user(user_id=user_id, session=session)
        if not user:
            await message.answer(f"❌ Пользователь <code>{user_id}</code> не найден")
            await state.clear()
            return
        
        result = await orm_create_subscription(session, user_id, days=days)
        
        if result:
            subscription = await orm_get_user_subscription(session, user_id)
            end_date = subscription.end_date.strftime('%d.%m.%Y %H:%M')
            
            await message.answer(
                f"✅ Подписка выдана пользователю <code>{user_id}</code>\n\n"
                f"📅 Срок: <b>{days} дней</b>\n"
                f"📆 Действует до: <b>{end_date}</b>"
            )
            
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"💎 <b>Вам выдана подписка!</b>\n\n"
                        f"📅 Срок: <b>{days} дней</b>\n"
                        f"📆 Действует до: <b>{end_date}</b>\n\n"
                        f"✅ Теперь вы можете отслеживать неограниченное количество каналов!"
                    )
                )
            except Exception as e:
                print(f"⚠️ Не удалось отправить уведомление пользователю {user_id}: {e}")
        else:
            await message.answer(f"❌ Ошибка при выдаче подписки")
    except ValueError:
        await message.answer(
            "❌ Неверный формат.\n\n"
            "Используйте: <code>USER_ID КОЛИЧЕСТВО_ДНЕЙ</code>\n"
            "Пример: <code>123456789 30</code>"
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    
    await state.clear()


@admin_router.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    keyboard = InlineKeyboardBuilder()
    keyboard.add(InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"))
    keyboard.add(InlineKeyboardButton(text="💰 Управление ценой", callback_data="admin_price"))
    keyboard.add(InlineKeyboardButton(text="👥 Управление пользователями", callback_data="admin_users"))
    keyboard.add(InlineKeyboardButton(text="💎 Выдать подписку", callback_data="admin_give_sub"))
    keyboard.adjust(1)
    
    try:
        await callback.message.edit_text(
            f"🔐 <b>Админ-панель</b>\n\n"
            f"Выберите действие:",
            reply_markup=keyboard.as_markup()
        )
    except:
        await callback.message.answer(
            f"🔐 <b>Админ-панель</b>\n\n"
            f"Выберите действие:",
            reply_markup=keyboard.as_markup()
        )
    
    await callback.answer()
