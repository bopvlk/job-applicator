import logging

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from job_applicator.bot.callbacks import CoverLetterCallback, JobCallback
from job_applicator.clients import bot
from job_applicator.enums import JobStatus
from job_applicator.storage.models import Job

logger = logging.getLogger(__name__)


def build_job_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Generate Cover Letters",
                    callback_data=CoverLetterCallback(action="gen", job_id=job_id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Applied",
                    callback_data=JobCallback(action=JobStatus.APPLIED, job_id=job_id).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=JobCallback(action=JobStatus.REJECTED, job_id=job_id).pack(),
                ),
            ],
        ]
    )


async def send_job_notification(chat_id: int, job: Job) -> None:
    """Format and send an interactive multi-factor job card to the user's Telegram chat."""
    text = (
        f"🎯 <b><a href='{job.uri}'>{job.title or 'Job Opening'}</a></b>\n"
        f"<b>🏢 Company:</b> {job.company or 'Direct Posting'}\n\n"
        f"📊 <b>Overall Fit: {job.match_pct}%</b>\n"
        f"• 🛠️ <b>Stack Match:</b> {job.stack_match_pct or job.match_pct}%\n"
        f"• 📈 <b>Seniority Match:</b> {job.seniority_match_pct or job.match_pct}%\n"
        f"• 📍 <b>Location/Terms:</b> {job.location_match_pct or job.match_pct}%\n\n"
        f"<b>🏢 Summary:</b>\n{job.company_summary or 'No summary provided.'}\n\n"
        f"<b>⚠️ Red Flags:</b>\n{job.red_flags or 'None found'}\n\n"
        f"<i>💡 Click below to generate 3 tailored cover letters on-demand!</i>"
    )

    logger.info(
        "Dispatching Telegram notification card",
        extra={
            "event": "telegram_card_dispatched",
            "user_id": chat_id,
            "job_id": job.id,
            "match_score": job.match_pct,
            "url": job.uri,
        },
    )

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=build_job_keyboard(job.id or 0),
        disable_web_page_preview=True,
    )
