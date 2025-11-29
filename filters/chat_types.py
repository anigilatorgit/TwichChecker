from aiogram import Bot, types
from aiogram.filters import Filter

import config


class ChatTypeFilter(Filter):
    def __init__(self, chat_types: list[str]) -> None:
        self.chat_types = chat_types

    async def __call__(self, message: types.Message) -> bool:
        return message.chat.type in self.chat_types


class IsAdmin(Filter):
    async def __call__(self, obj: types.Message | types.CallbackQuery, bot: Bot) -> bool:
        user = getattr(obj, "from_user", None)
        return bool(user and user.id in config.ADMIN_ID)


