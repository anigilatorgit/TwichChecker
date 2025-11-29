from aiogram.fsm.state import StatesGroup, State


class OrderPayment(StatesGroup):
    price = State()
    waiting_for_text = State()

    async def clear(self) -> None:
        await self.set_state(state=None)
        await self.set_data({})


class AddChannel(StatesGroup):
    waiting_for_url = State()


class AdminGiveSubscription(StatesGroup):
    waiting_for_user_id_and_days = State()


class AdminBanUser(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_reason = State()


class AdminUnbanUser(StatesGroup):
    waiting_for_user_id = State()