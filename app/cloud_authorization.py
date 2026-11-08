"""Per-job operator approval. No HTTP, Telegram, or model route issues approvals."""
import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime


def job_fingerprint(system_prompt, user_prompt, max_tokens):
    return hashlib.sha256(json.dumps([system_prompt, user_prompt, max_tokens], ensure_ascii=True).encode()).hexdigest()


@dataclass
class PaidJobApproval:
    approval_id: str
    operator: str
    fingerprint: str
    expires_at: datetime
    target: str = ''
    _used: bool = field(default=False, init=False)

    def consume(self, system_prompt, user_prompt, max_tokens, target=''):
        if (not self.approval_id.strip() or not self.operator.strip() or self._used or
                self.expires_at.tzinfo is None or self.expires_at <= datetime.now(UTC) or
                self.fingerprint != job_fingerprint(system_prompt, user_prompt, max_tokens) or self.target != target):
            raise PermissionError('A fresh operator approval for this exact paid job is required')
        self._used = True
