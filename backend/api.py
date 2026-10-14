import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path
from threading import RLock

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .advisor import recommend
from .cards import DATA_DIR, Catalog
from .demo import demo_snapshot
from .logs import LogSession, LogTail, discover_log, fingerprint
from .store import Store


class Settings(BaseModel):
    mode: str = "live"
    log_path: str = ""
    player_id: int | None = Field(default=None, ge=1, le=16)
    preference: str = "balanced"


class ImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000_000)
    player_id: int | None = Field(default=None, ge=1, le=16)


class Service:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.lock = RLock()
        self.data_dir = data_dir
        self.catalog = Catalog(data_dir / "cards.json")
        self.store = Store(data_dir / "advisor.sqlite3")
        self.config_file = data_dir / "settings.json"
        self.settings = Settings()
        if self.config_file.exists():
            self.settings = Settings.model_validate_json(self.config_file.read_text(encoding="utf-8"))
        self.tail = LogTail(self.catalog, self.settings.player_id)
        self.snapshot = None
        self.status = "waiting"
        self.error = None
        self.active_log = None
        self.last_fingerprint = None
        self.stage = 0
        if self.settings.mode == "demo":
            self.publish(demo_snapshot(self.catalog))

    def publish(self, snapshot):
        signature = fingerprint(snapshot)
        if signature == self.last_fingerprint:
            return
        self.snapshot = snapshot
        self.last_fingerprint = signature
        self.store.save(snapshot)

    def poll(self):
        with self.lock:
            if self.settings.mode != "live":
                return
            try:
                path = discover_log(self.settings.log_path) if self.settings.log_path else None
                if path is None:
                    self.status = "waiting"
                    self.active_log = None
                    self.snapshot = None
                    self.last_fingerprint = None
                    self.tail = LogTail(self.catalog, self.settings.player_id)
                    return
                self.active_log = str(path)
                previous_session = self.tail.session
                if path != self.tail.path or path.stat().st_size < self.tail.offset:
                    self.snapshot = None
                    self.last_fingerprint = None
                snapshot = self.tail.poll(path)
                if self.tail.session is not previous_session:
                    self.snapshot = None
                    self.last_fingerprint = None
                if snapshot:
                    self.publish(snapshot)
                self.status = "connected" if self.snapshot else "waiting_game"
                if self.snapshot and time.time() - path.stat().st_mtime > 120:
                    self.status = "stale"
                self.error = None
            except Exception as error:
                self.status = "error"
                self.error = str(error)
                self.snapshot = None
                self.last_fingerprint = None

    def update(self, settings: Settings):
        if settings.mode not in ("live", "demo") or settings.preference not in ("balanced", "survival"):
            raise ValueError("无效的模式或偏好。")
        if settings.log_path:
            path = Path(settings.log_path)
            if not path.exists() or not (path.is_dir() or path.name.lower() == "power.log"):
                raise ValueError("日志路径不存在，或文件不是 Power.log。")
        with self.lock:
            reset = (settings.mode, settings.log_path, settings.player_id) != (
                self.settings.mode, self.settings.log_path, self.settings.player_id)
            self.settings = settings
            self.config_file.write_text(settings.model_dump_json(indent=2), encoding="utf-8")
            if reset:
                self.tail = LogTail(self.catalog, settings.player_id)
                self.snapshot = None
                self.last_fingerprint = None
                self.error = None
                self.active_log = None
                self.status = "waiting"
                if settings.mode == "demo":
                    self.stage = 0
                    self.publish(demo_snapshot(self.catalog))

    def payload(self):
        with self.lock:
            snapshot = self.snapshot.model_dump() if self.snapshot else None
            stale = self.settings.mode == "live" and self.status == "stale"
            if stale and snapshot:
                snapshot["warnings"].append("日志超过 120 秒未更新，暂停实时建议。")
            return {"settings": self.settings.model_dump(), "status": self.status, "error": self.error,
                    "active_log": self.active_log, "catalog": self.catalog.metadata,
                    "snapshot": snapshot,
                    "advice": [a.model_dump() for a in recommend(self.snapshot, self.settings.preference)] if self.snapshot and not stale else []}

    def reconnect(self):
        with self.lock:
            self.tail = LogTail(self.catalog, self.settings.player_id)
            self.snapshot = None
            self.last_fingerprint = None
            self.error = None
            self.status = "waiting"
            if self.settings.mode == "demo":
                self.publish(demo_snapshot(self.catalog, self.stage))


service = Service()


@asynccontextmanager
async def lifespan(app):
    async def watch():
        while True:
            await asyncio.to_thread(service.poll)
            await asyncio.sleep(1)
    task = asyncio.create_task(watch())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="Tavern Advisor", lifespan=lifespan)


@app.get("/api/state")
def state():
    return service.payload()


@app.put("/api/settings")
def settings(settings: Settings):
    try:
        service.update(settings)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    return service.payload()


@app.post("/api/demo/next")
def next_demo():
    with service.lock:
        if service.settings.mode != "demo":
            raise HTTPException(409, "请先切换到演练。")
        service.stage += 1
        service.publish(demo_snapshot(service.catalog, service.stage))
        return service.payload()


@app.post("/api/reconnect")
def reconnect():
    service.reconnect()
    return service.payload()


@app.post("/api/import")
def import_log(request: ImportRequest):
    session = LogSession(service.catalog, source="import", player_id=request.player_id)
    try:
        session.feed(request.text)
        snapshot = session.snapshot()
        if snapshot is None:
            raise ValueError("日志中未找到 CREATE_GAME，请选择完整 Power.log。")
    except Exception as error:
        raise HTTPException(400, str(error)) from error
    service.store.save(snapshot)
    return {"snapshot": snapshot.model_dump(), "advice": [a.model_dump() for a in recommend(snapshot, service.settings.preference)]}


@app.get("/api/history")
def history():
    return service.store.recent()


@app.get("/api/history/{snapshot_id}")
def history_detail(snapshot_id: str):
    snapshot = service.store.get(snapshot_id)
    if snapshot is None:
        raise HTTPException(404, "未找到快照。")
    return {"snapshot": snapshot.model_dump(), "advice": [a.model_dump() for a in recommend(snapshot, service.settings.preference)]}


@app.get("/api/export")
def export_history():
    return {"schema_version": 1, "snapshots": service.store.recent(1000)}
