"""FastAPI app for the live demo dashboard (`smartcampus demo`).

All session calls run on one worker thread: the in-memory SQLite event store may only be used from
the thread that opened it, and one call at a time also keeps a slow solve from racing an apply.
"""

import asyncio
from collections.abc import AsyncIterator, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, TypeVar

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from smartcampus.api.demo import DemoError, DemoSession
from smartcampus.coordinator.run import Method

STATIC = Path(__file__).parent / "static"
T = TypeVar("T")


class ResetRequest(BaseModel):
    scenario: str


class FaultRequest(BaseModel):
    room_id: str
    kind: str
    start_min: int
    end_min: int
    reported_min: int | None = None


class OverrunRequest(BaseModel):
    fault_id: str
    new_end_min: int
    reported_min: int | None = None


def create_app(scenario: str = "ac-failure") -> FastAPI:
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="demo-session")
    session = worker.submit(DemoSession, scenario).result()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        worker.submit(session.close).result()
        worker.shutdown()

    app = FastAPI(title="Smart campus live demo", lifespan=lifespan)

    async def call(fn: Callable[[], T]) -> T:
        try:
            return await asyncio.get_running_loop().run_in_executor(worker, fn)
        except DemoError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error

    def with_state(fn: Callable[[], Any]) -> Callable[[], dict[str, Any]]:
        def run() -> dict[str, Any]:
            steps = fn()
            return {
                "steps": [s.as_dict() for s in steps or []],
                "state": session.snapshot(),
            }

        return run

    def method_of(name: str) -> Method:
        try:
            return Method(name)
        except ValueError as error:
            raise HTTPException(status_code=404, detail=f"unknown method {name!r}") from error

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC / "index.html")

    @app.get("/api/state")
    async def state() -> dict[str, Any]:
        return await call(session.snapshot)

    @app.post("/api/reset")
    async def reset(body: ResetRequest) -> dict[str, Any]:
        return await call(with_state(lambda: session.reset(body.scenario)))

    @app.post("/api/incident")
    async def incident(body: FaultRequest) -> dict[str, Any]:
        return await call(
            with_state(
                lambda: session.report_fault(
                    body.room_id, body.kind, body.start_min, body.end_min, body.reported_min
                )
            )
        )

    @app.post("/api/overrun")
    async def overrun(body: OverrunRequest) -> dict[str, Any]:
        return await call(
            with_state(
                lambda: session.report_overrun(body.fault_id, body.new_end_min, body.reported_min)
            )
        )

    @app.post("/api/plan/{method}")
    async def plan(method: str) -> dict[str, Any]:
        chosen = method_of(method)
        return await call(with_state(lambda: session.propose(chosen)))

    @app.post("/api/apply/{method}")
    async def apply(method: str) -> dict[str, Any]:
        chosen = method_of(method)
        return await call(with_state(lambda: session.apply(chosen)))

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    return app
