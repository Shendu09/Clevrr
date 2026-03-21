from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AuthConfig:
    domain: str = ""
    client_id: str = ""
    client_secret: str = ""
    audience: str = ""

    supported_services: list[str] = field(
        default_factory=lambda: ["google-oauth2", "github", "slack"]
    )
    high_risk_actions: list[str] = field(
        default_factory=lambda: [
            "delete_email",
            "push_to_main",
            "delete_event",
            "delete_file",
            "send_to_all",
        ]
    )

    @classmethod
    def from_env(cls) -> "AuthConfig":
        from dotenv import load_dotenv

        load_dotenv()

        required = [
            "AUTH0_DOMAIN",
            "AUTH0_CLIENT_ID",
            "AUTH0_CLIENT_SECRET",
            "AUTH0_AUDIENCE",
        ]
        missing = [key for key in required if not os.getenv(key)]
        if missing:
            raise RuntimeError(
                f"Missing Auth0 config: {missing}\n"
                "Add them to your .env file.\n"
                "Copy .env.example to .env to get started."
            )

        return cls(
            domain=os.getenv("AUTH0_DOMAIN", ""),
            client_id=os.getenv("AUTH0_CLIENT_ID", ""),
            client_secret=os.getenv("AUTH0_CLIENT_SECRET", ""),
            audience=os.getenv("AUTH0_AUDIENCE", ""),
        )

    @property
    def base_url(self) -> str:
        return f"https://{self.domain}"

    @property
    def token_url(self) -> str:
        return f"{self.base_url}/oauth/token"

    @property
    def mgmt_url(self) -> str:
        return f"{self.base_url}/api/v2"
