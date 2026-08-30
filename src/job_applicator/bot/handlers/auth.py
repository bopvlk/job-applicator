import random
import string
import time

from aiogram import Router
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from job_applicator.config import config
from job_applicator.services.email import send_otp
from job_applicator.storage.db import get_session
from job_applicator.storage.models import User

router = Router()


class Auth(StatesGroup):
    email = State()
    otp = State()
    desired_title = State()


def _gen_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


@router.message(Command("start"), StateFilter(None))
async def cmd_start(message: Message, state: FSMContext):
    await state.set_state(Auth.email)
    await message.answer("Hello! Type in your email address to get in:")


@router.message(Command("stop"))
async def cmd_stop(message: Message, state: FSMContext):
    await state.clear()
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if user:
            user.verified = 0
            s.commit()

    try:
        await message.delete()
    except Exception:
        pass

    await message.answer(
        "🛑 <b>Job Hunter AI stopped.</b>\n"
        "You will no longer receive automated job search notifications. Type /start anytime to re-authenticate.",
        parse_mode="HTML",
    )


@router.message(Auth.email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if email not in config.trusted_emails:
        await message.answer("You're not on the trusted list. Please try again.")
        return

    otp = _gen_otp()
    with get_session() as s:
        user = s.get(User, message.chat.id) or User(telegram_chat_id=message.chat.id)
        if user.verified == 1:
            await message.answer("You are already verified!")
            return
        user.email = email
        user.otp = otp
        user.otp_expires = int(time.time()) + 10 * 60
        user.verified = 0
        s.add(user)
        s.commit()

    await send_otp(email, otp)
    await state.set_state(Auth.otp)
    await message.answer("Code has been sent to your email. Enter it here:")


@router.message(Auth.otp)
async def process_otp(message: Message, state: FSMContext):
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if not user or user.otp != message.text.strip() or (user.otp_expires or 0) < int(time.time()):
            await message.answer("Invalid or expired Code. Please try again.")
            return
        user.otp = None
        user.otp_expires = None
        user.verified = 1
        s.commit()

    await state.set_state(Auth.desired_title)
    await message.answer("Done! Now enter the job title you're looking for (desired_title):")


@router.message(Auth.desired_title)
async def process_desired_title(message: Message, state: FSMContext):
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if user:
            user.desired_title = message.text.strip()
            s.commit()

    await state.clear()
    await message.answer(f"Saved: {message.text.strip()}. Authorization complete!")
