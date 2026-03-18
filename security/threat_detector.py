import os
import re
from datetime import datetime
from pathlib import Path


class ThreatDetector:

    MALWARE_PATTERNS = [
        r'powershell.*-enc',
        r'powershell.*-w.*hidden',
        r'cmd.*\/c.*del',
        r'wscript.*\.vbs',
        r'regsvr32.*\/s',
        r'mshta.*http',
        r'certutil.*-decode',
        r'bitsadmin.*\/transfer',
        r'schtasks.*\/create',
        r'net.*user.*\/add',
        r'net.*localgroup.*administrators',
        r'icacls.*\/grant',
        r'takeown.*\/f',
    ]

    CREDENTIAL_PATTERNS = [
        r'password\s*[:=]\s*\S+',
        r'passwd\s*[:=]\s*\S+',
        r'secret\s*[:=]\s*\S+',
        r'token\s*[:=]\s*\S+',
        r'api.key\s*[:=]\s*\S+',
        r'[A-Za-z0-9+/]{40,}={0,2}',
    ]

    DANGEROUS_PATHS = [
        r'C:\\Windows\\System32',
        r'C:\\Windows\\SysWOW64',
        r'C:\\Windows\\security',
        r'C:\\boot',
        r'\\AppData\\Roaming\\Microsoft\\Credentials',
        r'\\AppData\\Local\\Microsoft\\Credentials',
        r'\.ssh',
        r'\.gnupg',
    ]

    def __init__(self):
        self.compiled_malware = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.MALWARE_PATTERNS
        ]
        self.compiled_creds = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.CREDENTIAL_PATTERNS
        ]
        self.compiled_paths = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.DANGEROUS_PATHS
        ]
        self.alerts = []
        Path("data").mkdir(parents=True, exist_ok=True)

    def scan(self, text: str) -> dict:
        threats = []

        for pattern in self.compiled_malware:
            if pattern.search(text):
                threats.append(
                    {
                        "type": "MALWARE",
                        "severity": "CRITICAL",
                        "pattern": pattern.pattern,
                        "description": "Potential malware command",
                    }
                )

        for pattern in self.compiled_creds:
            if pattern.search(text):
                threats.append(
                    {
                        "type": "CREDENTIAL_LEAK",
                        "severity": "HIGH",
                        "pattern": pattern.pattern,
                        "description": "Potential credential in command",
                    }
                )

        for pattern in self.compiled_paths:
            if pattern.search(text):
                threats.append(
                    {
                        "type": "DANGEROUS_PATH",
                        "severity": "HIGH",
                        "pattern": pattern.pattern,
                        "description": "Access to protected path",
                    }
                )

        result = {
            "clean": len(threats) == 0,
            "threats": threats,
            "threat_count": len(threats),
            "highest_severity": self._highest_severity(threats),
        }

        if threats:
            self._log_threat(text, result)

        return result

    def _highest_severity(self, threats: list) -> str:
        if not threats:
            return "NONE"
        order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        severities = [threat["severity"] for threat in threats]
        return max(severities, key=lambda value: order.index(value))

    def _log_threat(self, text: str, result: dict):
        alert = {
            "timestamp": datetime.now().isoformat(),
            "text": text[:100],
            "threats": result["threats"],
            "severity": result["highest_severity"],
        }
        self.alerts.append(alert)

        try:
            with open("data/threat_log.txt", "a", encoding="utf-8") as file:
                file.write(
                    f"{alert['timestamp']} | {alert['severity']} | {text[:80]}\\n"
                )
        except Exception:
            pass

    def get_threat_summary(self) -> dict:
        return {
            "total_scans": len(self.alerts),
            "critical": sum(
                1 for alert in self.alerts if alert["severity"] == "CRITICAL"
            ),
            "high": sum(
                1 for alert in self.alerts if alert["severity"] == "HIGH"
            ),
            "recent": self.alerts[-5:] if self.alerts else [],
        }
