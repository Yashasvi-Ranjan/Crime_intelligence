#!/usr/bin/env python3
"""Redact secrets, tokens and hostnames from an AEGIS trace / run capture before it is committed. Stdlib only.

  python scripts/redact_trace.py IN [OUT]        redact a .json or .jsonl file (OUT defaults to IN with .redacted before the suffix)
  python scripts/redact_trace.py IN --check      do not write; exit 1 if IN still contains anything that looks sensitive

What is removed (replaced by a [REDACTED_*] marker):
  * values of keys named like password / secret / token / api key / authorization / cookie / credential (strings only,
    so integer counters such as prompt_tokens survive)
  * `Authorization: ...` / `Bearer ...` values, `password=...`-style assignments, JWTs, and common API key shapes (sk-, nvapi-, ghp_, AKIA...)
  * the exact values of ZETARIS_PASSWORD, ZETARIS_API_TOKEN, ZETARIS_USERNAME, NIGHTSHIFT_API_KEY if they are in the environment
  * credentials inside URLs, hostnames and ports of URLs, bare IPv4 addresses, host.docker.internal / *.local / *.internal names,
    e-mail addresses, and home-directory user names (/Users/<name>, /home/<name>)
What is kept on purpose: UUID query ids, receipt ids, model names, record ids (INC-..., CCTV-...), counts, timings.
The redactor is a safety net, not a guarantee: read the output before committing it.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, List, Tuple

SENSITIVE_KEY = re.compile(r"(pass(word|wd)?|secret|token|api[_-]?key|authorization|cookie|credential|bearer|private[_-]?key)", re.I)
# integer/boolean counters under these names are not secrets (prompt_tokens, max_tokens ...); only str values are redacted anyway
ENV_SECRETS = ("ZETARIS_PASSWORD", "ZETARIS_API_TOKEN", "ZETARIS_USERNAME", "NIGHTSHIFT_API_KEY")

# (compiled pattern, replacement). Order matters: URLs before bare hosts/IPs.
PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\b(authorization\s*[:=]\s*)(bearer\s+|basic\s+)?[^\s\"',;]+"), r"\1[REDACTED_AUTH]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}"), "[REDACTED_JWT]"),
    (re.compile(r"\b(?:sk|nvapi|ghp|gho|ghs|xox[abprs])[-_][A-Za-z0-9_-]{16,}"), "[REDACTED_KEY]"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)\b((?:pass(?:word|wd)?|secret|token|api[_-]?key)\s*[:=]\s*)(?!\[REDACTED)[^\s\"',;&]+"), r"\1[REDACTED_SECRET]"),
    # scheme://user:pass@host:port/path  ->  scheme://[REDACTED_HOST]/path   (userinfo, host and port all go)
    (re.compile(r"(?i)\b([a-z][a-z0-9+.-]*://)(?:[^/\s@\"']*@)?(?!\[REDACTED)[^/\s:\"'?#]+(?::\d+)?"), r"\1[REDACTED_HOST]"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "[REDACTED_IP]"),
    (re.compile(r"(?i)\b[a-z0-9-]+(?:\.[a-z0-9-]+)*\.(?:internal|local|lan|localdomain|trycloudflare\.com|onrender\.com|vercel\.app|ngrok(?:-free)?\.(?:app|io|dev))\b"), "[REDACTED_HOST]"),
    (re.compile(r"\blocalhost(?::\d+)?\b"), "[REDACTED_HOST]"),
    (re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"(/Users/|/home/)[^/\s\"']+"), r"\1[REDACTED_USER]"),
]

# For --check: things that must not survive redaction.
LEFTOVER: List[Tuple[str, re.Pattern]] = [
    ("bearer token", re.compile(r"(?i)\bbearer\s+(?!\[REDACTED)[A-Za-z0-9._~+/=-]{8,}")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.")),
    ("API key shape", re.compile(r"\b(?:sk|nvapi|ghp|gho|ghs)[-_][A-Za-z0-9_-]{16,}|\bAKIA[0-9A-Z]{16}\b")),
    ("secret assignment", re.compile(r"(?i)\b(?:pass(?:word|wd)?|secret|token|api[_-]?key)\s*[:=]\s*(?!\[REDACTED)[^\s\"',;&]{3,}")),
    ("URL host", re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://(?!\[REDACTED)[^\s\"'/]+")),
    ("IPv4 address", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
    ("e-mail", re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")),
    ("home path", re.compile(r"(?:/Users/|/home/)(?!\[REDACTED)[^/\s\"']+")),
]


def env_literals(env: "os._Environ[str] | dict | None" = None) -> List[str]:
    env = os.environ if env is None else env
    return [v for k in ENV_SECRETS if len(v := (env.get(k) or "").strip()) >= 4]


def redact_text(text: str, literals: Iterable[str] = ()) -> str:
    # longest first so a literal that contains another is replaced whole
    for lit in sorted(set(literals), key=len, reverse=True):
        text = text.replace(lit, "[REDACTED_SECRET]")
    for pat, repl in PATTERNS:
        text = pat.sub(repl, text)
    return text


def redact_obj(obj: Any, literals: Iterable[str] = ()) -> Any:
    literals = list(literals)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if isinstance(v, str) and SENSITIVE_KEY.search(str(k)):
                out[k] = "[REDACTED_SECRET]" if v else v
            else:
                out[k] = redact_obj(v, literals)
        return out
    if isinstance(obj, list):
        return [redact_obj(v, literals) for v in obj]
    if isinstance(obj, str):
        return redact_text(obj, literals)
    return obj


def redact_file_text(raw: str, literals: Iterable[str] = ()) -> str:
    """Redact a JSON document or a JSONL stream; anything that does not parse as JSON is redacted as plain text."""
    literals = list(literals)
    try:
        return json.dumps(redact_obj(json.loads(raw), literals), indent=2, ensure_ascii=False) + "\n"
    except ValueError:
        pass
    lines = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            lines.append(json.dumps(redact_obj(json.loads(line), literals), ensure_ascii=False))
        except ValueError:
            lines.append(redact_text(line, literals))
    return "\n".join(lines) + "\n"


def findings(text: str, literals: Iterable[str] = ()) -> List[str]:
    found = [f"literal secret from environment ({len(l)} chars)" for l in literals if l in text]
    for name, pat in LEFTOVER:
        if pat.search(text):
            found.append(name)
    return found


def main(argv: List[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    check = "--check" in argv
    if not args:
        print(__doc__)
        return 2
    src = Path(args[0])
    raw = src.read_text(encoding="utf-8")
    lits = env_literals()
    if check:
        bad = findings(raw, lits)
        for b in bad:
            print(f"{src}: still contains {b}", file=sys.stderr)
        print(f"{src}: {'NOT clean' if bad else 'clean (no known secret shapes)'}")
        return 1 if bad else 0
    dst = Path(args[1]) if len(args) > 1 else src.with_name(src.stem + ".redacted" + src.suffix)
    out = redact_file_text(raw, lits)
    bad = findings(out, lits)
    if bad:
        print("refusing to write: redaction left " + ", ".join(bad), file=sys.stderr)
        return 1
    dst.write_text(out, encoding="utf-8")
    print(f"wrote {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
