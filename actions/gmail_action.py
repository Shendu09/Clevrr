from __future__ import annotations

import requests

from .base_action import ActionResult, BaseAction


class GmailAction(BaseAction):
    @property
    def service_name(self) -> str:
        return "google-oauth2"

    @property
    def required_scopes(self) -> list[str]:
        return [
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
        ]

    def send_email(self, to: str, subject: str, body: str) -> ActionResult:
        return self.run("send_email", to=to, subject=subject, body=body)

    def read_inbox(self, max_results: int = 5) -> ActionResult:
        return self.run("read_inbox", max_results=max_results)

    def _execute(self, token: str, **kwargs) -> str:
        if "to" in kwargs:
            to = kwargs["to"]
            subject = kwargs.get("subject", "")
            body = kwargs.get("body", "")
            try:
                import base64
                from email.mime.text import MIMEText

                msg = MIMEText(body)
                msg["to"] = to
                msg["subject"] = subject
                raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
                response = requests.post(
                    "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"raw": raw},
                    timeout=10,
                )
                if response.status_code == 200:
                    return f"Email sent to {to}: '{subject}'"
                return f"Gmail API returned {response.status_code}"
            except Exception as exc:
                return f"[DEMO] Would send email to {to}: {exc}"

        return "[DEMO] Inbox: 3 unread messages"
