from fastapi import APIRouter, Request

from ..observability import EventRecorder
from ..schemas import DebugEventRecord, DebugEventsResponse

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/events", response_model=DebugEventsResponse)
async def debug_events(request: Request) -> DebugEventsResponse:
    recorder: EventRecorder = request.app.state.event_recorder
    return DebugEventsResponse(
        events=[
            DebugEventRecord.model_validate(event.to_payload()) for event in recorder.list_events()
        ]
    )
