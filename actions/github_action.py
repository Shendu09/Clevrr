from __future__ import annotations

import requests

from .base_action import ActionResult, BaseAction


class GitHubAction(BaseAction):
    @property
    def service_name(self) -> str:
        return "github"

    @property
    def required_scopes(self) -> list[str]:
        return ["repo", "issues"]

    def create_issue(self, repo: str, title: str, body: str = "") -> ActionResult:
        return self.run("create_issue", repo=repo, title=title, body=body)

    def _execute(self, token: str, **kwargs) -> str:
        repo = kwargs.get("repo", "")
        title = kwargs.get("title", "")
        body = kwargs.get("body", "")
        response = requests.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            },
            json={"title": title, "body": body},
            timeout=10,
        )
        if response.status_code == 201:
            url = response.json().get("html_url", "")
            return f"Issue created: {url}"
        return f"GitHub returned {response.status_code}"
