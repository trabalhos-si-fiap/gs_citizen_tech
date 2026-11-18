from dataclasses import dataclass


@dataclass(frozen=True)
class VisualVerificationDecision:
    status: str
    approved: bool
    audit_reason: str


class VisualVerificationService:
    def __init__(self, enabled: bool, provider: str) -> None:
        self._enabled = enabled
        self._provider = provider.strip()

    def verify(self) -> VisualVerificationDecision:
        if not self._enabled:
            return VisualVerificationDecision(
                status="disabled",
                approved=False,
                audit_reason="Verificação visual desativada por política.",
            )
        if not self._provider:
            return VisualVerificationDecision(
                status="unavailable",
                approved=False,
                audit_reason="Nenhum provedor aprovado foi configurado.",
            )
        return VisualVerificationDecision(
            status="manual_review",
            approved=False,
            audit_reason="A análise visual externa requer revisão humana.",
        )
