import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import config
from handlers.user_private import user_router
from handlers.admin_private import admin_router
from middlewares.db import DataBaseSession

from database.engine import create_db, session_maker
from services.stream_monitor import start_monitoring

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(admin_router)
dp.include_router(user_router)


async def on_startup():
    await create_db()
    print("База данных инициализирована")
    
    try:
        me = await bot.get_me()
        print(f"Бот подключен: @{me.username}")
    except Exception as e:
        print(f"⚠️ Ошибка подключения к боту: {e}")
        print("⚠️ Продолжаю запуск, но бот может не работать...")
    
    await start_monitoring(bot)
    print("✅ Бот запущен и мониторинг стримов активирован")


async def on_shutdown():
    print('bot leg')


async def main():
    from kbrds.reply import menu_reply_markup
    
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    dp.update.middleware(DataBaseSession(session_pool=session_maker))
    await bot.delete_webhook(drop_pending_updates=True)
    await bot.delete_my_commands(scope=types.BotCommandScopeAllPrivateChats())
    
    await dp.start_polling(bot)


asyncio.run(main())
