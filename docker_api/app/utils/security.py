from __future__ import annotations

from typing import Iterable, List
from fastapi import HTTPException


# Simple allowlist to avoid destructive commands
ALLOWED_CMDS = {
    "ls",
    "cat",
    "tail",
    "head",
    "wc",
    "stat",
    "df",
    "du",
    "uptime",
    "env",
    "printenv",
    "id",
    "whoami",
    "ps",
    "top",
    "grep",
    "awk",
    "sed",
    "cut",
    "sort",
    "uniq",
    "free",
    "ip",
    "ss",
    "netstat",
    "ping",
    "traceroute",
    "curl",
    "wget",
}

DENY_WORDS = {
    "rm",
    "shutdown",
    "reboot",
    "poweroff",
    "halt",
    "mkfs",
    "dd",
    ":(){:|:&};:",
    "sudo",
    "kill",
    "mount",
    "umount",
    "chown",
    "chmod",
    "useradd",
    "userdel",
    "groupadd",
    "groupdel",
    "passwd",
    "service",
    "systemctl",
    "docker",
    "podman",
}

SHELL_META = {"|", "&", ";", ">", "<", "&&", "||"}


def validate_command(cmd: Iterable[str]) -> None:
    parts: List[str] = list(cmd)
    if not parts:
        raise HTTPException(status_code=400, detail="Empty command not allowed")

    # No interactive flags
    for p in parts:
        if any(x in p for x in SHELL_META):
            raise HTTPException(
                status_code=400, detail="Pipelining/redirection not allowed"
            )

    base = parts[0]
    base_clean = base.split("/")[-1]
    if base_clean not in ALLOWED_CMDS:
        raise HTTPException(
            status_code=400, detail=f"Command '{base_clean}' is not allowed"
        )

    joined = " ".join(parts).lower()
    if any(word in joined for word in DENY_WORDS):
        raise HTTPException(status_code=400, detail="Dangerous command blocked")
