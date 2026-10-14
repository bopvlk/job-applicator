import json
import logging

from aiogram import Router
from aiogram.types import CallbackQuery, Message

from job_applicator.bot.callbacks import CoverLetterCallback, JobCallback
from job_applicator.services.analysis import generate_cover_letters
from job_applicator.storage.db import get_session
from job_applicator.storage.models import Job, User

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(JobCallback.filter())
async def process_job_status(callback: CallbackQuery, callback_data: JobCallback):
    user_id = callback.from_user.id if callback.from_user else 0
    with get_session() as s:
        job = s.get(Job, callback_data.job_id)
        if job:
            job.status = callback_data.action
            s.commit()
            logger.info(
                "User updated job application status",
                extra={
                    "event": "job_status_updated",
                    "user_id": user_id,
                    "job_id": job.id,
                    "new_status": callback_data.action.value,
                },
            )

    await callback.answer(f"Set as {callback_data.action.value}")
    if isinstance(callback.message, Message) and callback.message.text:
        await callback.message.edit_text(
            text=f"{callback.message.text}\n\n<b>📌 Status:</b> {callback_data.action.value}",
            parse_mode="HTML",
        )


@router.callback_query(CoverLetterCallback.filter())
async def process_generate_cover_letters(callback: CallbackQuery, callback_data: CoverLetterCallback):
    """Generate 3 tailored cover letters on-demand using custom prompt and candidate profile."""
    user_id = callback.from_user.id if callback.from_user else 0
    logger.info(
        "User requested on-demand cover letter generation",
        extra={"event": "cover_letter_requested", "user_id": user_id, "job_id": callback_data.job_id},
    )
    await callback.answer("⏳ Generating 3 tailored cover letters with Gemini...")

    with get_session() as s:
        job = s.get(Job, callback_data.job_id)
        if not job or not callback.message:
            return

        user = s.get(User, job.user_chat_id)
        if not user:
            return

        # Check if already generated and cached
        letters_text = ""
        if job.cover_letter:
            try:
                data = json.loads(job.cover_letter)
                letters_text = (
                    f"⚡ <b>Variant 1 (Concise & Hook):</b>\n<code>{data.get('variant_1')}</code>\n\n"
                    f"🛠️ <b>Variant 2 (Technical Angle):</b>\n<code>{data.get('variant_2')}</code>\n\n"
                    f"📈 <b>Variant 3 (Impact & Delivery):</b>\n<code>{data.get('variant_3')}</code>"
                )
            except Exception:
                letters_text = f"<code>{job.cover_letter}</code>"

        if not letters_text:
            # Generate live using Gemini
            variants = await generate_cover_letters(
                job_title=job.title or "Software Engineer",
                job_content=job.raw_text or job.company_summary or "",
                user=user,
            )
            if variants:
                job.cover_letter = json.dumps(variants)
                s.commit()
                letters_text = (
                    f"⚡ <b>Variant 1 (Concise & Hook):</b>\n<code>{variants['variant_1']}</code>\n\n"
                    f"🛠️ <b>Variant 2 (Technical Angle):</b>\n<code>{variants['variant_2']}</code>\n\n"
                    f"📈 <b>Variant 3 (Impact & Delivery):</b>\n<code>{variants['variant_3']}</code>"
                )
                logger.info(
                    "Cover letters successfully generated and cached",
                    extra={"event": "cover_letters_generated", "user_id": user_id, "job_id": job.id},
                )
            else:
                letters_text = "⚠️ <i>Failed to generate cover letters. Please try again.</i>"
                logger.error(
                    "Cover letter generation returned None",
                    extra={"event": "cover_letter_gen_failed", "user_id": user_id, "job_id": job.id},
                )

    if isinstance(callback.message, Message) and callback.message.text:
        updated_text = (
            f"{callback.message.text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📝 <b>Generated Cover Letters (Tap to Copy):</b>\n\n"
            f"{letters_text}"
        )
        if len(updated_text) > 4000:
            await callback.message.reply(f"📝 <b>Cover Letters:</b>\n\n{letters_text}", parse_mode="HTML")
        else:
            await callback.message.edit_text(
                text=updated_text,
                parse_mode="HTML",
                reply_markup=callback.message.reply_markup,
            )
