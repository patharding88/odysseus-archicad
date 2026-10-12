from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from server import gdlstore

STATIC = Path(__file__).resolve().parents[1] / "static"

app = FastAPI(title="GDL Builder")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


class ImportBody(BaseModel):
    path: str = Field(min_length=1)
    name: str | None = None


class FileBody(BaseModel):
    file: str = Field(min_length=1)
    text: str


@app.on_event("startup")
def startup() -> None:
    gdlstore.seed_examples()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/libraries")
def libraries() -> dict:
    return {"libraries": gdlstore.list_libraries()}


@app.post("/api/import")
def import_library(body: ImportBody) -> dict:
    try:
        library = gdlstore.import_path(Path(body.path), body.name)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return library


@app.get("/api/libraries/{lib_id}/parts/{part_id}")
def part(lib_id: str, part_id: str) -> dict:
    try:
        return gdlstore.part_detail(lib_id, part_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/libraries/{lib_id}/parts/{part_id}/text")
def read_text(lib_id: str, part_id: str, file: str) -> dict:
    try:
        text = gdlstore.read_text_file(lib_id, part_id, file)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"file": file, "text": text}


@app.put("/api/libraries/{lib_id}/parts/{part_id}/text")
def write_text(lib_id: str, part_id: str, body: FileBody) -> dict:
    try:
        gdlstore.write_text_file(lib_id, part_id, body.file, body.text)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "file": body.file}


@app.post("/api/libraries/{lib_id}/parts/{part_id}/export")
def export_part(lib_id: str, part_id: str) -> dict:
    try:
        return gdlstore.export_part(lib_id, part_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/libraries/{lib_id}/parts/{part_id}/preview")
def preview(lib_id: str, part_id: str) -> FileResponse:
    try:
        return FileResponse(gdlstore.preview_path(lib_id, part_id))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/jobs")
def jobs() -> dict:
    return {"jobs": gdlstore.list_jobs()}


@app.get("/api/guides")
def guides() -> dict:
    return {"folder": str(gdlstore.GUIDES), "guides": gdlstore.list_guides()}
