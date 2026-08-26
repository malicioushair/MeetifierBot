from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from .i18n import t
from .keyboards import FLOW_BACK_DATA, FLOW_CANCEL_DATA, flow_nav_keyboard, organizer_main_menu, participant_main_menu


async def discard_flow(
    target: Message | CallbackQuery,
    state: FSMContext,
    locale: str,
    *,
    role: str,
) -> None:
    await state.clear()
    menu = organizer_main_menu(locale) if role == "org" else participant_main_menu(locale)
    text = t(locale, "flow_cancelled")
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text)
        except Exception:
            pass
        await target.message.answer(text, reply_markup=menu)
        await target.answer()
    else:
        await target.answer(text, reply_markup=menu)


def prompt_markup(locale: str):
    return flow_nav_keyboard(locale)


__all__ = [
    "FLOW_BACK_DATA",
    "FLOW_CANCEL_DATA",
    "discard_flow",
    "prompt_markup",
]
