import pytz
from telegram.ext import JobQueue

from models import Reminder


class ReminderScheduler:
    def __init__(self, job_queue: JobQueue, callback):
        self.job_queue = job_queue
        self.callback = callback

    def job_name(self, reminder_id: int) -> str:
        return f"reminder::{reminder_id}"

    def cancel(self, reminder_id: int) -> None:
        name = self.job_name(reminder_id)
        current_jobs = self.job_queue.get_jobs_by_name(name)
        for job in current_jobs:
            job.schedule_removal()

    def schedule(self, reminder: Reminder) -> None:
        self.cancel(reminder.id)
        if not reminder.active:
            return

        tz = pytz.timezone(reminder.timezone or "UTC")
        job_name = self.job_name(reminder.id)
        data = {"reminder_id": reminder.id}

        if reminder.schedule_type in {"fixed_time", "weekly"} and reminder.time_of_day:
            days = None
            if reminder.schedule_type == "weekly" and reminder.days_of_week:
                day_map = {
                    "mon": 0,
                    "tue": 1,
                    "wed": 2,
                    "thu": 3,
                    "fri": 4,
                    "sat": 5,
                    "sun": 6,
                }
                days = tuple(
                    day_map[d.strip().lower()]
                    for d in reminder.days_of_week.split(",")
                    if d.strip().lower() in day_map
                )
                days = days or None
            self.job_queue.run_daily(
                self.callback,
                time=reminder.time_of_day,
                days=days,
                data=data,
                name=job_name,
                job_kwargs={"timezone": tz},
            )
        elif reminder.schedule_type == "interval" and reminder.interval_hours:
            self.job_queue.run_repeating(
                self.callback,
                interval=reminder.interval_hours * 3600,
                first=0,
                data=data,
                name=job_name,
            )
        else:
            # Fallback: daily at stored time or after 1h
            self.job_queue.run_repeating(
                self.callback,
                interval=3600,
                first=0,
                data=data,
                name=job_name,
            )
