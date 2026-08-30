from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from job_applicator.bot.app import bot
from job_applicator.bot.callbacks import JobCallback
from job_applicator.enums import JobStatus
from job_applicator.storage.models import Job


def build_job_keyboard(job_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Applied",
                    callback_data=JobCallback(action=JobStatus.APPLIED, job_id=job_id).pack(),
                ),
                InlineKeyboardButton(
                    text="❌ Reject",
                    callback_data=JobCallback(action=JobStatus.REJECTED, job_id=job_id).pack(),
                ),
            ]
        ]
    )


async def send_job_notification(chat_id: int, job: Job) -> None:
    """Format and send a job card to the user's Telegram chat."""
    text = (
        f"<b>🎯 <a href='{job.uri}'>{job.title}</a></b>\n"
        f"<b>Match Score:</b> {job.match_pct}%\n\n"
        f"<b>🏢 Summary:</b>\n{job.company_summary}\n\n"
        f"<b>⚠️ Red Flags:</b>\n{job.red_flags or 'None'}\n\n"
        f"<b>📝 Draft Cover Letter:</b>\n<code>{job.cover_letter}</code>"
    )

    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=build_job_keyboard(job.id),
        disable_web_page_preview=True,
    )
