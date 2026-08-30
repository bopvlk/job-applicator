import random
import string
import time

from aiogram import Router
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlmodel import select

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
    # 1. Clear any active FSM state
    await state.clear()

    # 2. Update user status in CockroachDB to stop notifications
    with get_session() as s:
        statement = select(User).where(User.telegram_chat_id == message.chat.id)
        user = s.exec(statement).first()
        if user:
            user.verified = 0
            user.telegram_chat_id = None
            s.commit()

    # 3. Optional: Delete the user's "/stop" message bubble in Telegram
    try:
        await message.delete()
    except Exception:
        pass  # Ignore if bot lacks permission to delete messages

    await message.answer(
        "🛑 <b>Job Hunter AI stopped.</b>\n"
        "You will no longer receive automated job search notifications. Type /start anytime to re-authenticate.",
        parse_mode="HTML"
    )

@router.message(Auth.email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()
    if email not in config.trusted_emails:
        await message.answer("You're not on the trusted list. Please try again.")
        return
    otp = _gen_otp()
    with get_session() as s:
        user = s.get(User, email) or User(email=email)
        if user.verified == 1:
            await message.answer("You already verified")
            return
        user.telegram_chat_id = message.chat.id
        user.otp = otp
        user.otp_expires = int(time.time()) + 10 * 60
        user.verified = 0
        s.add(user)
        s.commit()
    await send_otp(email, otp)
    await state.update_data(email=email)
    await state.set_state(Auth.otp)
    await message.answer("Code has been sent to your email. Enter it here:")

@router.message(Auth.otp)
async def process_otp(message: Message, state: FSMContext):
    email = await state.get_value("email")
    with get_session() as s:
        user = s.get(User, email)
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
    email = await state.get_value("email")
    with get_session() as s:
        user = s.get(User, email)
        if user:
            user.desired_title = message.text.strip()
            s.commit()
    await state.clear()
    await message.answer(f"Saved: {user.desired_title}. Authorization complete!")