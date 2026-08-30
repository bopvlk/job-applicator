from aiogram import Router
from aiogram.types import CallbackQuery

from job_applicator.bot.callbacks import JobCallback
from job_applicator.storage.db import get_session
from job_applicator.storage.models import Job

router = Router()


@router.callback_query(JobCallback.filter())
async def process_job_status(callback: CallbackQuery, callback_data: JobCallback):
    with get_session() as s:
        job = s.get(Job, callback_data.job_id)
        if job:
            job.status = callback_data.action
            s.commit()

    await callback.answer(f"Set as {callback_data.action.value}")
    if callback.message:
        await callback.message.edit_text(
            text=f"{callback.message.text}\n\n<b>📌 Status:</b> {callback_data.action.value}",
            parse_mode="HTML",
        )
