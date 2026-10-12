"""MCP endpoint so Odysseus can read and edit the unpacked GDL library."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from server import gdlstore

mcp = FastMCP(
    "GDL Builder",
    instructions=(
        "Edit Archicad GDL library parts that have been unpacked on this machine. "
        "Before a rename or an edit, read the scripts the change depends on with read_gdl_file "
        "or read_gdl_files. Use only the text those tools return. An edit is refused until that "
        "file has been read. Do not invent commands and do not reply with a suggested script. "
        "Lengths in the parameter list are metres. The name shown in the editor is objName in "
        "scripts/1d.gdl. Do not expect a live Archicad connection from this server."
    ),
    host="127.0.0.1",
    port=8766,
    streamable_http_path="/mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            "127.0.0.1:*",
            "localhost:*",
            "host.docker.internal:*",
        ],
        allowed_origins=[],
    ),
)


def _dump(payload: object) -> str:
    return json.dumps(payload, indent=2)


@mcp.tool()
def list_gdl_parts() -> str:
    """List the Archicad GDL objects currently loaded in the GDL editor.

    Call this when the user asks which library parts or objects are loaded.
    Do not browse the editor page. This tool returns the library and part ids.
    """
    libraries = []
    for library in gdlstore.list_libraries():
        libraries.append(
            {
                "id": library["id"],
                "name": library["name"],
                "parts": [{"id": part["id"], "name": part["name"], "author": part["author"]} for part in library["parts"]],
            }
        )
    return _dump({"libraries": libraries, "jobs": gdlstore.list_jobs()})


@mcp.tool()
def read_gdl_part(library: str, part: str) -> str:
    """List one object's scripts and parameters.

    This is the map of the object, not the source. Call read_gdl_file on each script
    you will change before rename_gdl_part or edit_gdl_file.
    """
    detail = gdlstore.part_detail(library, part)
    detail.pop("comment", None)
    for script in detail["scripts"]:
        filename = script["file"].rsplit("/", 1)[-1]
        script["about"] = gdlstore.SCRIPT_NOTES.get(filename, "")
    detail["edit_rule"] = "Read a script with read_gdl_file before editing it. Quote the existing lines."
    return _dump(detail)


@mcp.tool()
def read_gdl_file(library: str, part: str, file: str) -> str:
    """Read one GDL script or library text file before editing it.

    file is like scripts/ui.gdl, scripts/3d.gdl, scripts/vl.gdl, or scripts/1d.gdl.
    Call this, then edit_gdl_file using lines copied from the returned text.
    """
    text = gdlstore.read_for_edit(library, part, file)
    limit = 100000
    clipped = text[:limit]
    complete = clipped == text
    if not complete:
        gdlstore.forget_seen(library, part, file)
    return _dump(
        {
            "file": file,
            "truncated": not complete,
            "text": clipped,
            "edit_with": "edit_gdl_file" if complete else "read the rest before editing",
        }
    )


@mcp.tool()
def read_gdl_files(library: str, part: str, files: str) -> str:
    """Read several scripts in one call before changing an object.

    files is a comma-separated list, for example scripts/ui.gdl, scripts/vl.gdl, scripts/3d.gdl.
    A checkbox or dialog change needs the interface, parameter, and 3D scripts.
    A rename needs scripts/1d.gdl.
    """
    names = [item.strip() for item in files.split(",") if item.strip()]
    if not names:
        raise ValueError("Name the scripts to read, separated by commas.")
    payload = []
    for name in names:
        text = gdlstore.read_for_edit(library, part, name)
        payload.append({"file": name, "text": text})
    return _dump({"files": payload})


@mcp.tool()
def edit_gdl_file(library: str, part: str, file: str, find: str, replace: str) -> str:
    """Change lines in a script that read_gdl_file has already returned.

    find must be copied from that text. Call this for the user's change. Do not paste a suggested script in the chat.
    """
    gdlstore.edit_text_file(library, part, file, find, replace)
    return _dump({"ok": True, "file": file})


@mcp.tool()
def rename_gdl_part(library: str, part: str, name: str) -> str:
    """Rename the object shown in the GDL editor.

    Read scripts/1d.gdl first. This updates objName in the master script.
    """
    return _dump(gdlstore.rename_part(library, part, name))


@mcp.tool()
def write_gdl_file(library: str, part: str, file: str, text: str) -> str:
    """Replace a whole GDL script. Send the complete file.

    For a small change, call edit_gdl_file instead. A short replacement of a long script is refused.
    """
    gdlstore.write_text_file(library, part, file, text)
    return _dump({"ok": True, "file": file, "bytes": len(text.encode("utf-8"))})


@mcp.tool()
def export_gdl_part(library: str, part: str) -> str:
    """Pack the working copy back to a GSM with Archicad's LP_XMLConverter."""
    return _dump(gdlstore.export_part(library, part))


def main() -> None:
    gdlstore.ensure_workspace()
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
