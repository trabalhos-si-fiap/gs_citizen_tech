from app.infrastructure.repositories import AuthRepository, ReportRepository
from app.models.auth import AuthUser


class PrivacyService:
    def __init__(
        self,
        auth_repository: AuthRepository,
        report_repository: ReportRepository,
    ) -> None:
        self._auth_repository = auth_repository
        self._report_repository = report_repository

    def get_account(self, user_id: int) -> AuthUser:
        return self._auth_repository.get_user(user_id)

    def update_email(self, user_id: int, email: str) -> AuthUser:
        return self._auth_repository.update_email(user_id, email)

    def export_data(self, user_id: int) -> dict[str, object]:
        account = self._auth_repository.get_user(user_id)
        export = self._report_repository.export_user_data(user_id)
        export["account"] = {
            "id": str(account.id),
            "email": account.email,
            "role": account.role,
            "consent_version": account.consent_version,
            "created_at": account.created_at.isoformat(),
        }
        return export

    def delete_account(self, user_id: int) -> None:
        self._report_repository.delete_user_data(user_id)
        self._auth_repository.delete_account(user_id)
