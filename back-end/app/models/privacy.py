from pydantic import BaseModel, ConfigDict


class PrivacyExport(BaseModel):
    model_config = ConfigDict(extra="allow")

