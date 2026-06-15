from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile

from autodata_agent.api.dependencies import (
    get_analysis_service,
    get_dataset_store,
    get_session_store,
    settings_dependency,
)
from autodata_agent.core.config import Settings
from autodata_agent.core.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    DatasetInfo,
    DatasetProfile,
    HealthStatus,
    SessionRecord,
    SQLIngestRequest,
)
from autodata_agent.services.analysis import AnalysisService
from autodata_agent.services.datasets import DatasetStore
from autodata_agent.storage.session_store import SessionStore

router = APIRouter()

SettingsDep = Annotated[Settings, Depends(settings_dependency)]
DatasetStoreDep = Annotated[DatasetStore, Depends(get_dataset_store)]
SessionStoreDep = Annotated[SessionStore, Depends(get_session_store)]
AnalysisServiceDep = Annotated[AnalysisService, Depends(get_analysis_service)]
UploadFileDep = Annotated[UploadFile, File(...)]


@router.get("/health", response_model=HealthStatus)
def health(settings: SettingsDep) -> HealthStatus:
    return HealthStatus(status="ok", environment=settings.env, model=settings.ollama_model)


@router.post("/datasets/upload", response_model=DatasetInfo)
async def upload_dataset(
    file: UploadFileDep,
    datasets: DatasetStoreDep,
) -> DatasetInfo:
    content = await file.read()
    return datasets.put_file(file.filename or "uploaded_dataset", content)


@router.post("/datasets/sql", response_model=DatasetInfo)
def ingest_sql(
    request: SQLIngestRequest,
    datasets: DatasetStoreDep,
) -> DatasetInfo:
    return datasets.put_sql(request)


@router.get("/datasets/{dataset_id}/profile", response_model=DatasetProfile)
def get_profile(
    dataset_id: str,
    datasets: DatasetStoreDep,
) -> DatasetProfile:
    return datasets.get(dataset_id).profile


@router.post("/analysis", response_model=AnalysisResponse)
def analyze(
    request: AnalysisRequest,
    service: AnalysisServiceDep,
) -> AnalysisResponse:
    return service.analyze(request)


@router.get("/sessions/{session_id}/history", response_model=list[SessionRecord])
def session_history(
    session_id: str,
    sessions: SessionStoreDep,
) -> list[SessionRecord]:
    return sessions.history(session_id)
