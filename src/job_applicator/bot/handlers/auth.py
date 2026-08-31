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
    await state.clear()
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if user and user.verified == 1:
            await message.answer(
                f"👋 <b>Welcome back!</b>\n\n"
                f"• <b>Email:</b> {user.email}\n"
                f"• <b>Current Role:</b> {user.desired_title or 'Not set'}\n\n"
                f"To change your target role, send /set_title\n"
                f"To pause notifications, send /stop",
                parse_mode="HTML",
            )
            return

    await state.set_state(Auth.email)
    await message.answer(
        "👋 <b>Welcome to Job Applicator AI!</b>\n\nPlease enter your email address to authenticate:",
        parse_mode="HTML",
    )


@router.message(Command("set_title", "title", "role"))
async def cmd_set_title(message: Message, state: FSMContext):
    """Allow user to update their target job title anytime."""
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if not user or user.verified != 1:
            await message.answer("⚠️ You must be authenticated first. Type /start to begin.")
            return

    await state.set_state(Auth.desired_title)
    await message.answer(
        f"🎯 Current target role: <b>{user.desired_title or 'None'}</b>\n\n"
        "Please type your new target job title (e.g. <i>Senior Go Developer</i>, <i>Backend Engineer</i>):",
        parse_mode="HTML",
    )


@router.message(Command("status"))
async def cmd_status(message: Message):
    """Display current user configuration and status."""
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if not user or user.verified != 1:
            await message.answer("⚠️ You are not authenticated. Type /start to get started.")
            return

        status_text = "🟢 Active" if user.verified == 1 else "🔴 Paused"
        await message.answer(
            f"📊 <b>Your Job Applicator Status:</b>\n\n"
            f"• <b>Status:</b> {status_text}\n"
            f"• <b>Email:</b> <code>{user.email}</code>\n"
            f"• <b>Target Role:</b> <b>{user.desired_title}</b>\n\n"
            f"<i>Commands:</i>\n"
            f"/set_title - Change target job title\n"
            f"/stop - Pause search notifications",
            parse_mode="HTML",
        )


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
        "🛑 <b>Job Applicator AI paused.</b>\n\n"
        "You will no longer receive automated job search notifications.\n"
        "Type /start anytime to re-activate.",
        parse_mode="HTML",
    )


@router.message(Auth.email)
async def process_email(message: Message, state: FSMContext):
    if not message.text:
        return
    email = message.text.strip().lower()
    if email not in [e.lower() for e in config.trusted_emails]:
        await message.answer("⛔ You are not on the trusted list. Please try again with a valid authorized email.")
        return

    otp = _gen_otp()
    with get_session() as s:
        user = s.get(User, message.chat.id) or User(telegram_chat_id=message.chat.id)
        user.email = email
        user.otp = otp
        user.otp_expires = int(time.time()) + 10 * 60
        user.verified = 0
        s.add(user)
        s.commit()

    await send_otp(email, otp)
    await state.set_state(Auth.otp)
    await message.answer(
        f"📬 A 6-digit verification code has been sent to <b>{email}</b>. Enter it here:",
        parse_mode="HTML",
    )


@router.message(Auth.otp)
async def process_otp(message: Message, state: FSMContext):
    text = message.text.strip() if message.text else ""
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if not user or user.otp != text or (user.otp_expires or 0) < int(time.time()):
            await message.answer("❌ Invalid or expired verification code. Please check your email and try again.")
            return
        user.otp = None
        user.otp_expires = None
        user.verified = 1
        s.commit()

    await state.set_state(Auth.desired_title)
    await message.answer(
        "✅ <b>Email verified!</b>\n\n"
        "Now, enter the exact job title you want to search for (e.g. <i>Golang Developer</i>):",
        parse_mode="HTML",
    )


@router.message(Auth.desired_title)
async def process_desired_title(message: Message, state: FSMContext):
    if not message.text:
        return
    new_title = message.text.strip()
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if user:
            user.desired_title = new_title
            user.verified = 1
            s.commit()

    await state.clear()
    await message.answer(
        f"🎯 <b>Target role saved:</b> <code>{new_title}</code>\n\n"
        f"🚀 <b>Setup complete!</b> ApplyBot is now actively hunting for jobs matching your role.\n"
        f"You will receive notifications with tailored cover letters as soon as matches are found.",
        parse_mode="HTML",
    )


@router.message()
async def handle_unknown_message(message: Message):
    """Fallback handler for unknown messages."""
    await message.answer(
        "🤔 I didn't recognize that command.\n\n"
        "<b>Available commands:</b>\n"
        "• /start — Authenticate & start bot\n"
        "• /set_title — Change target job role\n"
        "• /status — View search status & settings\n"
        "• /stop — Pause search notifications",
        parse_mode="HTML",
    )
