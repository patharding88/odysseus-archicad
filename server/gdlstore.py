"""Working library store. GSM files are unpacked with ArchiCAD's LP_XMLConverter."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "workspace"
CONVERTER = Path(
    os.environ.get(
        "GDL_CONVERTER",
        r"C:\Program Files\Graphisoft\Archicad 28\LP_XMLConverter.exe",
    )
)
GUIDES = Path(
    os.environ.get(
        "GDL_GUIDES",
        r"C:\Users\PatHarding\Homes By CMA\DraftSP - ArchiCAD\TUTORIALS\GDL SCRIPTING",
    )
)

SCRIPT_SLOTS = [
    ("1d.gdl", "Master"),
    ("2d.gdl", "2D"),
    ("3d.gdl", "3D"),
    ("pr.gdl", "Properties"),
    ("vl.gdl", "Parameter"),
    ("ui.gdl", "Interface"),
    ("fm.gdl", "Forward migration"),
    ("bw.gdl", "Backward migration"),
]

EXAMPLES = [
    {
        "name": "Tankworks",
        "path": r"C:\Users\PatHarding\Desktop\Tankworks_ArchiCAD_LibraryAC20\Tankworks_ArchiCAD_Lib",
    },
    {
        "name": "Roof downpipe",
        "path": r"C:\Users\PatHarding\Desktop\roof_downpipe.gsm",
    },
]

JOBS = [
    {
        "id": "tank-sizes",
        "title": "Tank sizes are short of the range we need",
        "library": "tankworks",
        "part": "Tankworks_WaterTanks",
        "script": "vl.gdl",
        "summary": (
            "Slimline, round, square, modline and stockman sizes are written as VALUES lists "
            "in the parameter script. The litre figure is not calculated. The master script "
            "picks a row, and the parameter script reads that row from the matching "
            "Tankworks_Capacity text file. A new size has to land in the VALUES list, "
            "in the master-script row lookup, and as a tab-separated row in the capacity file."
        ),
    },
    {
        "id": "downpipe-steps",
        "title": "Downpipe needs steps and a spreader",
        "library": "roof-downpipe",
        "part": "roof_downpipe",
        "script": "3d.gdl",
        "summary": (
            "The 3D script builds one tube. It leaves the gutter, makes a single neck back "
            "to the wall, drops straight to the ground, then adds an optional toe. Extra steps "
            "are more path points down that tube. A spreader is a second ending at the bottom, "
            "beside the existing toe, so the outlet can fan out instead of kicking out on an angle."
        ),
    },
]


def slug(name: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return cleaned or "library"


def ensure_workspace() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    jobs_path = WORK / "jobs.json"
    if not jobs_path.exists():
        jobs_path.write_text(json.dumps(JOBS, indent=2), encoding="utf-8")


def seed_examples() -> list[str]:
    """Unpack the desktop examples once, when their source is still there."""
    ensure_workspace()
    notes: list[str] = []
    for example in EXAMPLES:
        source = Path(example["path"])
        lib_id = slug(example["name"])
        if (WORK / lib_id / "manifest.json").exists():
            continue
        if not source.exists():
            notes.append(f"Skipped {example['name']}: {source} is not on this machine.")
            continue
        import_path(source, example["name"])
        notes.append(f"Imported {example['name']}.")
    return notes


def _run_converter(args: list[str]) -> None:
    if not CONVERTER.exists():
        raise FileNotFoundError(f"LP_XMLConverter was not found at {CONVERTER}")
    completed = subprocess.run(
        [str(CONVERTER), *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(detail or f"LP_XMLConverter failed ({completed.returncode})")


def import_path(source: Path, name: str | None = None) -> dict:
    ensure_workspace()
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(str(source))
    library_name = name or (source.stem if source.is_file() else source.name)
    lib_id = slug(library_name)
    lib_dir = WORK / lib_id
    if lib_dir.exists():
        shutil.rmtree(lib_dir)
    parts_dir = lib_dir / "parts"
    files_dir = lib_dir / "files"
    parts_dir.mkdir(parents=True)
    files_dir.mkdir(parents=True)

    if source.is_file():
        if source.suffix.lower() != ".gsm":
            raise ValueError("Import a .gsm file or a library folder.")
        _convert_gsm(source, parts_dir / source.stem)
    else:
        gsm_files = [p for p in source.rglob("*") if p.is_file() and p.suffix.lower() == ".gsm"]
        if not gsm_files:
            raise ValueError("That folder has no .gsm library parts.")
        for gsm in gsm_files:
            _convert_gsm(gsm, parts_dir / gsm.stem)
        for item in source.rglob("*"):
            if not item.is_file() or item.suffix.lower() == ".gsm":
                continue
            relative = item.relative_to(source)
            target = files_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)

    manifest = {
        "id": lib_id,
        "name": library_name,
        "source": str(source),
    }
    (lib_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return library_detail(lib_id)


def _convert_gsm(gsm: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run_converter(["libpart2hsf", "-l", "UTF8", str(gsm), str(dest)])
    if not (dest / "libpartdata.xml").exists():
        raise RuntimeError(f"Converter did not write a library part for {gsm.name}")


def list_libraries() -> list[dict]:
    ensure_workspace()
    libraries = []
    for lib_dir in sorted(p for p in WORK.iterdir() if (p / "manifest.json").exists()):
        manifest = json.loads((lib_dir / "manifest.json").read_text(encoding="utf-8"))
        parts = []
        parts_root = lib_dir / "parts"
        if parts_root.exists():
            for part_dir in sorted(p for p in parts_root.iterdir() if (p / "libpartdata.xml").exists()):
                parts.append(_part_summary(lib_dir.name, part_dir))
        libraries.append(
            {
                "id": manifest["id"],
                "name": manifest["name"],
                "source": manifest.get("source", ""),
                "parts": parts,
            }
        )
    return libraries


def library_detail(lib_id: str) -> dict:
    match = next((lib for lib in list_libraries() if lib["id"] == lib_id), None)
    if match is None:
        raise FileNotFoundError(lib_id)
    return match


def _part_dir(lib_id: str, part_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]+", lib_id):
        raise FileNotFoundError(lib_id)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", part_id):
        raise FileNotFoundError(part_id)
    lib_root = (WORK / lib_id).resolve()
    part = (lib_root / "parts" / part_id).resolve()
    try:
        part.relative_to(lib_root)
    except ValueError as exc:
        raise FileNotFoundError(f"{lib_id}/{part_id}") from exc
    if not (part / "libpartdata.xml").exists():
        raise FileNotFoundError(f"{lib_id}/{part_id}")
    return part


def _part_summary(lib_id: str, part_dir: Path) -> dict:
    data = ET.parse(part_dir / "libpartdata.xml").getroot()
    ident = data.find("Identification")
    docs = _docs(part_dir)
    return {
        "id": part_dir.name,
        "library": lib_id,
        "name": part_dir.name.replace("_", " "),
        "guid": _text(ident, "MainGUID") if ident is not None else "",
        "placeable": _text(ident, "IsPlaceable") == "true" if ident is not None else False,
        "author": docs["author"],
        "license": docs["license"],
        "preview": (part_dir / "images" / "Picture_0.png").exists(),
    }


def part_detail(lib_id: str, part_id: str) -> dict:
    part_dir = _part_dir(lib_id, part_id)
    summary = _part_summary(lib_id, part_dir)
    docs = _docs(part_dir)
    parameters = _parameters(part_dir / "paramlist.xml")
    if not summary["author"]:
        for row in parameters:
            if row["name"].lower() == "copyright" and row["description"]:
                summary["author"] = row["description"]
                break
    scripts = []
    for filename, label in SCRIPT_SLOTS:
        path = part_dir / "scripts" / filename
        scripts.append(
            {
                "file": f"scripts/{filename}",
                "label": label,
                "exists": path.exists() and path.stat().st_size > 0,
                "bytes": path.stat().st_size if path.exists() else 0,
            }
        )
    ancestry = []
    ancestry_path = part_dir / "ancestry.xml"
    if ancestry_path.exists():
        root = ET.parse(ancestry_path).getroot()
        ancestry = [node.text or "" for node in root.findall("MainGUID")]
    return {
        **summary,
        "comment": docs["comment"],
        "scripts": scripts,
        "parameters": parameters,
        "ancestry": ancestry,
        "files": _library_files(lib_id),
    }


def _docs(part_dir: Path) -> dict:
    path = part_dir / "libpartdocs.xml"
    author = ""
    license_name = ""
    comment = ""
    if path.exists():
        root = ET.parse(path).getroot()
        author = _text(root.find("Copyright"), "Author")
        license_node = root.find("./Copyright/License")
        if license_node is not None:
            kind = _text(license_node, "Type")
            version = _text(license_node, "Version")
            license_name = " ".join(bit for bit in (kind, version) if bit)
        comment_node = root.find("CommentSection")
        if comment_node is not None and comment_node.text:
            lines = [line.strip() for line in comment_node.text.splitlines() if line.strip()]
            comment = "\n".join(lines)
    return {"author": author, "license": license_name, "comment": comment}


def _text(node: ET.Element | None, tag: str) -> str:
    if node is None:
        return ""
    child = node.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parameters(path: Path) -> list[dict]:
    if not path.exists():
        return []
    root = ET.parse(path).getroot()
    rows = []
    container = root.find("Parameters")
    if container is None:
        return rows
    for child in list(container):
        if child.tag == "ParamSectHeader":
            continue
        flags = [flag.tag for flag in child.findall("./Flags/*")]
        flags += [flag.tag for flag in child if flag.tag in {"Fix", "BoldName"}]
        description = _text(child, "Description").strip('"')
        raw = _text(child, "Value")
        display = raw[1:-1] if len(raw) >= 2 and raw[0] == '"' and raw[-1] == '"' else raw
        rows.append(
            {
                "name": child.attrib.get("Name", child.tag),
                "type": child.tag,
                "value": display,
                "description": description,
                "hidden": "ParFlg_Hidden" in flags,
                "bold": "ParFlg_BoldName" in flags or child.tag == "Title",
            }
        )
    return rows


def _library_files(lib_id: str) -> list[dict]:
    files_root = WORK / lib_id / "files"
    if not files_root.exists():
        return []
    rows = []
    for path in sorted(p for p in files_root.rglob("*") if p.is_file()):
        relative = path.relative_to(files_root).as_posix()
        rows.append({"file": f"files/{relative}", "name": path.name, "bytes": path.stat().st_size})
    return rows


def read_text_file(lib_id: str, part_id: str, relative: str) -> str:
    path = _resolve_text(lib_id, part_id, relative, write=False)
    return path.read_text(encoding="utf-8-sig")


def write_text_file(lib_id: str, part_id: str, relative: str, text: str) -> None:
    path = _resolve_text(lib_id, part_id, relative, write=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def _resolve_text(lib_id: str, part_id: str, relative: str, write: bool) -> Path:
    relative = relative.replace("\\", "/").lstrip("/")
    parts = Path(relative).parts
    if any(part in {"..", ""} for part in parts):
        raise ValueError("That file path is not allowed.")
    lib_root = (WORK / lib_id).resolve()
    part_root = _part_dir(lib_id, part_id)
    if relative.startswith("scripts/"):
        allowed = {f"scripts/{name}" for name, _label in SCRIPT_SLOTS}
        if relative not in allowed:
            raise ValueError("That script is not a GDL slot.")
        return part_root / relative
    if relative.startswith("files/") and relative.lower().endswith(".txt"):
        path = (lib_root / relative).resolve()
        if lib_root not in path.parents:
            raise ValueError("That file sits outside the library.")
        if write and not path.exists():
            raise FileNotFoundError(relative)
        return path
    raise ValueError("Only GDL scripts and library text files can be opened here.")


def preview_path(lib_id: str, part_id: str) -> Path:
    path = _part_dir(lib_id, part_id) / "images" / "Picture_0.png"
    if not path.exists():
        raise FileNotFoundError("No preview picture.")
    return path


def export_part(lib_id: str, part_id: str) -> dict:
    part_dir = _part_dir(lib_id, part_id)
    export_dir = WORK / lib_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    gsm_path = export_dir / f"{part_id}.gsm"
    if gsm_path.exists():
        gsm_path.unlink()
    _run_converter(["hsf2libpart", "-l", "UTF8", str(part_dir), str(gsm_path)])
    files_root = WORK / lib_id / "files"
    copied = 0
    if files_root.exists():
        for item in files_root.rglob("*"):
            if not item.is_file():
                continue
            target = export_dir / item.relative_to(files_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)
            copied += 1
    return {"gsm": str(gsm_path), "folder": str(export_dir), "copiedFiles": copied}


def list_jobs() -> list[dict]:
    ensure_workspace()
    return json.loads((WORK / "jobs.json").read_text(encoding="utf-8"))


def list_guides() -> list[dict]:
    if not GUIDES.exists():
        return []
    guides = []
    for path in sorted(GUIDES.glob("CB4_*.pdf")):
        guides.append({"name": path.name, "path": str(path)})
    return guides
