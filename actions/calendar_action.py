from __future__ import annotations

import requests

from .base_action import ActionResult, BaseAction


class CalendarAction(BaseAction):
    @property
    def service_name(self) -> str:
        return "google-oauth2"

    @property
    def required_scopes(self) -> list[str]:
        return ["https://www.googleapis.com/auth/calendar.events"]

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        description: str = "",
    ) -> ActionResult:
        return self.run(
            "create_event",
            title=title,
            start=start,
            end=end,
            description=description,
        )

    def _execute(self, token: str, **kwargs) -> str:
        title = kwargs.get("title", "")
        start = kwargs.get("start", "")
        end = kwargs.get("end", "")
        description = kwargs.get("description", "")
        response = requests.post(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "summary": title,
                "description": description,
                "start": {"dateTime": start, "timeZone": "UTC"},
                "end": {"dateTime": end, "timeZone": "UTC"},
            },
            timeout=10,
        )
        if response.status_code == 200:
            return f"Event created: {title} at {start}"
        return f"[DEMO] Would create event: {title} at {start}"
