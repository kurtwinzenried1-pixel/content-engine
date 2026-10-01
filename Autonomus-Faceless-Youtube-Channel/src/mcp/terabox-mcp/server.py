"""Terabox Archive MCP Server — exposes Terabox cloud storage as MCP tools."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# Add mcp-python-sdk to path if not installed as package
_SDK = Path(__file__).resolve().parents[3] / "mcp-python-sdk" / "src"
if _SDK.exists() and str(_SDK) not in sys.path:
    sys.path.insert(0, str(_SDK))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    EmbeddedResource,
    TextContent,
    Tool,
)

from client import TeraboxClient, TeraboxError

server = Server("terabox-archive")


def _text(content: Any) -> list[TextContent]:
    if isinstance(content, str):
        return [TextContent(type="text", text=content)]
    return [TextContent(type="text", text=json.dumps(content, indent=2, ensure_ascii=False))]


def _err(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=f"Error: {msg}")]


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="terabox_quota",
            description="Get Terabox storage quota: total, used, free GB and usage percent.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="terabox_list",
            description="List files and folders in a Terabox directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path (default: /)"},
                    "order": {"type": "string", "description": "Sort by: time | name | size (default: time)"},
                    "desc": {"type": "integer", "description": "1=descending, 0=ascending (default: 1)"},
                },
            },
        ),
        Tool(
            name="terabox_search",
            description="Search for files in Terabox by keyword.",
            inputSchema={
                "type": "object",
                "required": ["keyword"],
                "properties": {
                    "keyword": {"type": "string", "description": "Search term"},
                    "path": {"type": "string", "description": "Directory to search in (default: /)"},
                    "recursion": {"type": "integer", "description": "1=recursive, 0=top-level only"},
                },
            },
        ),
        Tool(
            name="terabox_create_folder",
            description="Create a folder in Terabox.",
            inputSchema={
                "type": "object",
                "required": ["path"],
                "properties": {
                    "path": {"type": "string", "description": "Full folder path to create, e.g. /youtube/assets"},
                },
            },
        ),
        Tool(
            name="terabox_upload",
            description="Upload a local file to Terabox. Supports chunked upload for large files.",
            inputSchema={
                "type": "object",
                "required": ["local_path", "remote_path"],
                "properties": {
                    "local_path": {"type": "string", "description": "Absolute path to local file"},
                    "remote_path": {"type": "string", "description": "Destination path on Terabox, e.g. /youtube/video.mp4"},
                },
            },
        ),
        Tool(
            name="terabox_download",
            description="Download a file from Terabox to local disk.",
            inputSchema={
                "type": "object",
                "required": ["remote_path", "local_path"],
                "properties": {
                    "remote_path": {"type": "string", "description": "File path on Terabox"},
                    "local_path": {"type": "string", "description": "Local destination path"},
                },
            },
        ),
        Tool(
            name="terabox_delete",
            description="Delete one or more files/folders from Terabox.",
            inputSchema={
                "type": "object",
                "required": ["paths"],
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of Terabox paths to delete",
                    },
                },
            },
        ),
        Tool(
            name="terabox_move",
            description="Move or rename files on Terabox.",
            inputSchema={
                "type": "object",
                "required": ["operations"],
                "properties": {
                    "operations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["path", "dest", "newname"],
                            "properties": {
                                "path": {"type": "string", "description": "Source file path"},
                                "dest": {"type": "string", "description": "Destination directory"},
                                "newname": {"type": "string", "description": "New filename"},
                            },
                        },
                        "description": "List of move operations",
                    },
                },
            },
        ),
        Tool(
            name="terabox_share",
            description="Create a shareable link for files on Terabox.",
            inputSchema={
                "type": "object",
                "required": ["fs_ids"],
                "properties": {
                    "fs_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "File system IDs (from terabox_list results)",
                    },
                    "period": {"type": "integer", "description": "Expiry days, 0=permanent (default: 0)"},
                    "password": {"type": "string", "description": "Optional 4-char access password"},
                },
            },
        ),
        Tool(
            name="terabox_archive_content",
            description=(
                "Archive YouTube channel content (video, audio, image, script) to an "
                "organised Terabox folder structure: /youtube-channel/{type}/{filename}. "
                "Creates the folder if needed, then uploads the file."
            ),
            inputSchema={
                "type": "object",
                "required": ["local_path", "content_type"],
                "properties": {
                    "local_path": {"type": "string", "description": "Absolute path to the local file"},
                    "content_type": {
                        "type": "string",
                        "enum": ["video", "audio", "image", "script", "thumbnail", "subtitle", "misc"],
                        "description": "Type of content to determine target folder",
                    },
                    "channel_name": {"type": "string", "description": "Channel name subfolder (default: default)"},
                    "custom_filename": {"type": "string", "description": "Override filename on Terabox"},
                },
            },
        ),
        Tool(
            name="terabox_get_download_link",
            description="Get a direct download link for a file stored on Terabox.",
            inputSchema={
                "type": "object",
                "required": ["remote_path"],
                "properties": {
                    "remote_path": {"type": "string", "description": "File path on Terabox"},
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    cookie = os.getenv("TERABOX_COOKIE", "")
    if not cookie and name not in ("terabox_quota",):
        return _err("TERABOX_COOKIE environment variable not set. "
                    "Export your Terabox session cookie to use this server.")

    try:
        async with TeraboxClient(cookie=cookie) as client:
            match name:
                case "terabox_quota":
                    return _text(await client.get_quota())

                case "terabox_list":
                    result = await client.list_files(
                        path=arguments.get("path", "/"),
                        order=arguments.get("order", "time"),
                        desc=arguments.get("desc", 1),
                    )
                    return _text(result)

                case "terabox_search":
                    result = await client.search(
                        keyword=arguments["keyword"],
                        path=arguments.get("path", "/"),
                        recursion=arguments.get("recursion", 1),
                    )
                    return _text(result)

                case "terabox_create_folder":
                    result = await client.create_folder(arguments["path"])
                    return _text({"status": "created", "path": arguments["path"]})

                case "terabox_upload":
                    result = await client.upload_file(
                        local_path=arguments["local_path"],
                        remote_path=arguments["remote_path"],
                    )
                    return _text(result)

                case "terabox_download":
                    result = await client.download_file(
                        remote_path=arguments["remote_path"],
                        local_path=arguments["local_path"],
                    )
                    return _text(result)

                case "terabox_delete":
                    result = await client.delete_files(arguments["paths"])
                    return _text({"status": "deleted", "paths": arguments["paths"]})

                case "terabox_move":
                    result = await client.move_files(arguments["operations"])
                    return _text({"status": "moved"})

                case "terabox_share":
                    result = await client.create_share(
                        fs_ids=arguments["fs_ids"],
                        period=arguments.get("period", 0),
                        password=arguments.get("password", ""),
                    )
                    return _text(result)

                case "terabox_get_download_link":
                    link = await client.get_download_link(arguments["remote_path"])
                    return _text({"download_link": link})

                case "terabox_archive_content":
                    local_path = Path(arguments["local_path"])
                    content_type = arguments["content_type"]
                    channel = arguments.get("channel_name", "default")
                    filename = arguments.get("custom_filename") or local_path.name
                    remote_dir = f"/youtube-channel/{channel}/{content_type}"
                    remote_path = f"{remote_dir}/{filename}"

                    # Ensure folder exists
                    try:
                        await client.create_folder(remote_dir)
                    except TeraboxError:
                        pass  # Folder may already exist

                    result = await client.upload_file(
                        local_path=str(local_path),
                        remote_path=remote_path,
                    )
                    result["remote_dir"] = remote_dir
                    result["content_type"] = content_type
                    return _text(result)

                case _:
                    return _err(f"Unknown tool: {name}")

    except TeraboxError as e:
        return _err(str(e))
    except FileNotFoundError as e:
        return _err(f"File not found: {e}")
    except Exception as e:
        return _err(f"Unexpected error: {type(e).__name__}: {e}")


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
