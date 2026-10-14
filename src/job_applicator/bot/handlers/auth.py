import io
import logging
import random
import string
import time

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.state import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Document, Message
from sqlmodel import func, select

from job_applicator.clients import bot
from job_applicator.config import config
from job_applicator.enums import JobStatus
from job_applicator.scheduler import run_pipeline_for_user
from job_applicator.services.analysis import parse_resume_pdf
from job_applicator.services.email import send_otp
from job_applicator.storage.db import get_session
from job_applicator.storage.models import Job, User

logger = logging.getLogger(__name__)

router = Router()


class Auth(StatesGroup):
    email = State()
    otp = State()
    desired_title = State()
    resume_upload = State()


def _gen_otp(length: int = 6) -> str:
    return "".join(random.choices(string.digits, k=length))


@router.message(Command("start"), StateFilter(None))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if user and user.verified == 1:
            logger.info(
                "Authenticated user reopened bot",
                extra={"event": "user_start_authenticated", "user_id": message.chat.id},
            )
            await message.answer(
                f"👋 <b>Welcome back!</b>\n\n"
                f"• <b>Email:</b> <code>{user.email}</code>\n"
                f"• <b>Target Role:</b> <b>{user.desired_title or 'Not set'}</b>\n"
                f"• <b>Min Score:</b> {user.min_match_score}%\n\n"
                f"<i>Commands:</i>\n"
                f"• /search_now — Trigger live job search right now\n"
                f"• /profile — View full profile & live application stats\n"
                f"• /upload_resume — Upload PDF resume to auto-fill skills\n"
                f"• /set_title — Change target job role\n"
                f"• /stop — Pause search notifications",
                parse_mode="HTML",
            )
            return

    logger.info(
        "New user started authentication flow", extra={"event": "auth_flow_started", "user_id": message.chat.id}
    )
    await state.set_state(Auth.email)
    await message.answer(
        "👋 <b>Welcome to Job Applicator AI!</b>\n\nPlease enter your email address to authenticate:",
        parse_mode="HTML",
    )


@router.message(Command("search_now", "hunt"))
async def cmd_search_now(message: Message):
    """Trigger an immediate on-demand job search for this user."""
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if not user or user.verified != 1:
            await message.answer("⚠️ You must be authenticated first. Type /start to begin.")
            return

    logger.info(
        "User triggered on-demand live search",
        extra={"event": "on_demand_search_triggered", "user_id": message.chat.id, "role": user.desired_title},
    )
    progress_msg = await message.answer(
        f"🔍 <b>Hunting for jobs now...</b>\n\n"
        f"• <b>Role:</b> {user.desired_title}\n"
        f"• <b>Skills:</b> {', '.join(user.top_skills) if user.top_skills else 'Default'}\n\n"
        f"<i>Searching Tavily ➔ Deduplicating via Qdrant ➔ Evaluating with Gemini...</i>",
        parse_mode="HTML",
    )

    try:
        found, sent, discarded = await run_pipeline_for_user(user)
        await progress_msg.edit_text(
            f"✅ <b>Live Search Completed!</b>\n\n"
            f"• 📥 <b>Raw Postings Found:</b> {found}\n"
            f"• 🎯 <b>High Matches Dispatched:</b> {sent}\n"
            f"• 🚫 <b>Skipped (Duplicates / Low Match):</b> {discarded}\n\n"
            f"<i>Check the cards above to generate tailored cover letters!</i>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(
            "Error during on-demand search",
            exc_info=True,
            extra={"event": "on_demand_search_failed", "user_id": message.chat.id, "error": str(e)},
        )
        await progress_msg.edit_text(
            "❌ <b>Search encountered an error.</b> Please try again in a minute.", parse_mode="HTML"
        )


@router.message(Command("profile"))
async def cmd_profile(message: Message):
    """Display full candidate profile and live application statistics."""
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if not user or user.verified != 1:
            await message.answer("⚠️ You are not authenticated. Type /start to get started.")
            return

        # Calculate statistics from Job table
        total_sent = s.exec(select(func.count(Job.id)).where(Job.user_chat_id == user.telegram_chat_id)).one()
        applied_count = s.exec(
            select(func.count(Job.id)).where(Job.user_chat_id == user.telegram_chat_id, Job.status == JobStatus.APPLIED)
        ).one()
        rejected_count = s.exec(
            select(func.count(Job.id)).where(
                Job.user_chat_id == user.telegram_chat_id, Job.status == JobStatus.REJECTED
            )
        ).one()
        pending_count = s.exec(
            select(func.count(Job.id)).where(Job.user_chat_id == user.telegram_chat_id, Job.status == JobStatus.NEW)
        ).one()

    skills_text = ", ".join(user.top_skills) if user.top_skills else "<i>Not set (Use /upload_resume)</i>"
    achievements_text = (
        "\n".join(f"  • {a}" for a in user.key_achievements) if user.key_achievements else "<i>Not set</i>"
    )

    await message.answer(
        f"👤 <b>Candidate Profile:</b>\n\n"
        f"• <b>Target Role:</b> <b>{user.desired_title or 'Not set'}</b>\n"
        f"• <b>Experience:</b> {user.years_experience or 0} years\n"
        f"• <b>Top Skills:</b> {skills_text}\n"
        f"• <b>Location/Terms:</b> {user.preferred_location or 'Remote'}\n"
        f"• <b>Min Salary:</b> {user.min_salary or 'Open'}\n"
        f"• <b>Min Match Score:</b> {user.min_match_score}%\n\n"
        f"🏆 <b>Key Achievements:</b>\n{achievements_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Application Statistics:</b>\n"
        f"• 📬 <b>Total Received:</b> {total_sent}\n"
        f"• ✅ <b>Applied:</b> {applied_count}\n"
        f"• ❌ <b>Rejected:</b> {rejected_count}\n"
        f"• ⏳ <b>Pending Review:</b> {pending_count}\n\n"
        f"<i>To update profile: send /upload_resume or /set_title</i>",
        parse_mode="HTML",
    )


@router.message(Command("upload_resume", "resume", "cv"))
async def cmd_upload_resume(message: Message, state: FSMContext):
    """Prompt user to upload a PDF resume."""
    with get_session() as s:
        user = s.get(User, message.chat.id)
        if not user or user.verified != 1:
            await message.answer("⚠️ You must be authenticated first. Type /start to begin.")
            return

    await state.set_state(Auth.resume_upload)
    await message.answer(
        "📄 <b>Upload Your Resume (PDF)</b>\n\n"
        "Please send your resume file as a <b>.pdf document</b>.\n"
        "Gemini 2.5 will automatically scan it and extract your skills, experience, and achievements into your profile!",
        parse_mode="HTML",
    )


@router.message(Auth.resume_upload, F.document)
async def process_resume_document(message: Message, state: FSMContext):
    """Download PDF in memory and parse via Gemini multimodal API."""
    doc: Document = message.document  # type: ignore
    if not doc.file_name or not doc.file_name.lower().endswith(".pdf"):
        await message.answer("⚠️ Please send a valid <b>.pdf</b> document.")
        return

    progress = await message.answer("⏳ <b>Scanning resume with Gemini 2.5 Multimodal AI...</b>", parse_mode="HTML")

    try:
        file = await bot.get_file(doc.file_id)
        file_path = file.file_path
        if not file_path:
            await progress.edit_text("❌ Failed to download file from Telegram.")
            return

        pdf_bytes_io = io.BytesIO()
        await bot.download_file(file_path, pdf_bytes_io)
        pdf_bytes = pdf_bytes_io.getvalue()

        # Parse with Gemini
        profile_data = await parse_resume_pdf(pdf_bytes)
        if not profile_data:
            await progress.edit_text(
                "❌ Failed to parse resume content. Please ensure the PDF is text-readable.", parse_mode="HTML"
            )
            return

        with get_session() as s:
            user = s.get(User, message.chat.id)
            if user:
                user.years_experience = profile_data.get("years_experience")
                user.top_skills = profile_data.get("top_skills", [])
                user.key_achievements = profile_data.get("key_achievements", [])
                user.preferred_location = profile_data.get("preferred_location")
                user.min_salary = profile_data.get("min_salary")
                user.bio_summary = profile_data.get("bio_summary")
                s.commit()

        await state.clear()
        logger.info(
            "Resume successfully parsed and saved",
            extra={
                "event": "resume_parsed_saved",
                "user_id": message.chat.id,
                "skills_count": len(profile_data.get("top_skills", [])),
            },
        )
        await progress.edit_text(
            f"✅ <b>Resume Successfully Scanned!</b>\n\n"
            f"• <b>Experience:</b> {profile_data.get('years_experience')} years\n"
            f"• <b>Skills:</b> {', '.join(profile_data.get('top_skills', []))}\n"
            f"• <b>Location:</b> {profile_data.get('preferred_location') or 'Remote'}\n\n"
            f"<i>Type /profile to see full profile details.</i>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(
            "Resume upload handler error",
            exc_info=True,
            extra={"event": "resume_upload_error", "user_id": message.chat.id, "error": str(e)},
        )
        await progress.edit_text("❌ An error occurred during resume scanning.", parse_mode="HTML")


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
            f"• <b>Target Role:</b> <b>{user.desired_title}</b>\n"
            f"• <b>Min Match Score:</b> {user.min_match_score}%\n\n"
            f"<i>Commands:</i>\n"
            f"/search_now - Trigger live hunt right now\n"
            f"/profile - View candidate profile & stats\n"
            f"/upload_resume - Scan PDF resume\n"
            f"/set_title - Change target role\n"
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
            logger.info(
                "User paused job search notifications",
                extra={"event": "user_search_paused", "user_id": message.chat.id},
            )

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
        logger.warning(
            "Unauthorized email attempt",
            extra={"event": "auth_unauthorized_email", "email": email, "user_id": message.chat.id},
        )
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

    logger.info("Sent OTP verification code", extra={"event": "otp_sent", "email": email, "user_id": message.chat.id})
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
            logger.warning("Invalid or expired OTP entered", extra={"event": "otp_failed", "user_id": message.chat.id})
            await message.answer("❌ Invalid or expired verification code. Please check your email and try again.")
            return
        user.otp = None
        user.otp_expires = None
        user.verified = 1
        s.commit()

    logger.info(
        "User successfully verified OTP",
        extra={"event": "user_verified", "user_id": message.chat.id, "email": user.email},
    )
    await state.set_state(Auth.desired_title)
    await message.answer(
        "✅ <b>Email verified!</b>\n\n"
        "Now, enter the exact job title you want to search for (e.g. <i>Senior Golang Developer</i>):",
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
    logger.info(
        "User updated target role", extra={"event": "user_role_updated", "user_id": message.chat.id, "role": new_title}
    )
    await message.answer(
        f"🎯 <b>Target role saved:</b> <code>{new_title}</code>\n\n"
        f"🚀 <b>Setup complete!</b> Job Applicator AI is actively hunting for matching jobs.\n"
        f"💡 Tip: Send /upload_resume to scan your CV or /search_now to hunt right now!",
        parse_mode="HTML",
    )


@router.message()
async def handle_unknown_message(message: Message):
    """Fallback handler for unknown messages."""
    await message.answer(
        "🤔 I didn't recognize that command.\n\n"
        "<b>Available commands:</b>\n"
        "• /search_now — Trigger live job search right now\n"
        "• /profile — View candidate profile & application stats\n"
        "• /upload_resume — Scan PDF resume\n"
        "• /set_title — Change target job role\n"
        "• /status — View search status & settings\n"
        "• /stop — Pause search notifications",
        parse_mode="HTML",
    )
