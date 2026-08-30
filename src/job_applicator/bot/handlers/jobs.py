from aiogram import F, Router
from aiogram.types import CallbackQuery

from job_applicator.enums import JobStatus
from job_applicator.storage.db import get_session
from job_applicator.storage.models import Job

router = Router()


@router.callback_query(F.data.startswith("job:"))
async def process_job_status(callback: CallbackQuery):
    # callback.data виглядає як "job:applied:12"
    if not callback.data or not callback.message:
        return

    _, action, job_id_str = callback.data.split(":")
    job_id = int(job_id_str)
    new_status = JobStatus.APPLIED if action == "applied" else JobStatus.REJECTED

    with get_session() as s:
        job = s.get(Job, job_id)
        if job:
            job.status = new_status
            s.commit()

    await callback.answer(f"Позначено як: {new_status.value}")
    await callback.message.edit_text(
        text=f"{callback.message.text}\n\n<b>📌 Статус:</b> {new_status.value}",
        parse_mode="HTML",
    )
