import csv
import io
from datetime import date
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix="/v1/public", tags=["public"])


def get_analytics_service(request: Request) -> AnalyticsService:
    return request.app.state.analytics_service


@router.get("/metrics")
def public_metrics(
    request: Request,
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    category: str | None = None,
    agency_id: str | None = None,
    format: Literal["json", "csv"] = "json",
):
    service = get_analytics_service(request)
    try:
        metrics = service.get_public_metrics(
            from_date,
            to_date,
            category,
            agency_id,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "agency_id",
                "agency_name",
                "reports",
                "avg_response_hours",
                "resolution_rate",
            ]
        )
        for row in metrics["by_agency"]:
            writer.writerow(
                [
                    row["agency"]["id"],
                    row["agency"]["name"],
                    row["reports"],
                    row["avg_response_hours"] or "",
                    row["resolution_rate"] or "",
                ]
            )
        return PlainTextResponse(
            buffer.getvalue(),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="public-metrics.csv"',
            },
        )
    return metrics
