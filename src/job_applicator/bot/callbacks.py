from aiogram.filters.callback_data import CallbackData

from job_applicator.enums import JobStatus


class JobCallback(CallbackData, prefix="job"):
    action: JobStatus
    job_id: int


class CoverLetterCallback(CallbackData, prefix="cl"):
    action: str
    job_id: int
