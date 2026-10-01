"""Terabox API client using cookie-based authentication."""

import asyncio
import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx


class TeraboxError(Exception):
    pass


class TeraboxClient:
    """Async Terabox client using session cookies."""

    BASE = "https://www.terabox.com"
    PAN_API = "https://pan.terabox.com/api"
    UPLOAD_BASE = "https://c-jp.terabox.com"

    def __init__(self, cookie: str | None = None, token: str | None = None):
        self.cookie = cookie or os.getenv("TERABOX_COOKIE", "")
        self.token = token or os.getenv("TERABOX_TOKEN", "")
        self._client: httpx.AsyncClient | None = None

    @property
    def headers(self) -> dict:
        return {
            "Cookie": self.cookie,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.terabox.com/",
        }

    async def __aenter__(self):
        self._client = httpx.AsyncClient(headers=self.headers, timeout=60.0)
        return self

    async def __aexit__(self, *_):
        if self._client:
            await self._client.aclose()

    def _check(self, data: dict, op: str = "operation") -> dict:
        errno = data.get("errno", 0)
        if errno != 0:
            raise TeraboxError(f"{op} failed (errno={errno}): {data}")
        return data

    async def get_quota(self) -> dict:
        r = await self._client.get(
            f"{self.PAN_API}/quota",
            params={"checkexpire": 1, "checkfree": 1},
        )
        data = r.json()
        total = data.get("total", 0)
        used = data.get("used", 0)
        return {
            "total_gb": round(total / 1024**3, 2),
            "used_gb": round(used / 1024**3, 2),
            "free_gb": round((total - used) / 1024**3, 2),
            "used_pct": round(used / total * 100, 1) if total else 0,
        }

    async def list_files(self, path: str = "/", order: str = "time", desc: int = 1) -> list[dict]:
        params = {
            "dir": path,
            "order": order,
            "desc": desc,
            "showempty": 1,
            "web": 1,
            "page": 1,
            "num": 100,
            "channel": "dubox",
            "clienttype": 0,
        }
        r = await self._client.get(f"{self.PAN_API}/list", params=params)
        data = self._check(r.json(), "list_files")
        return [
            {
                "name": f["server_filename"],
                "path": f["path"],
                "size": f.get("size", 0),
                "is_dir": bool(f.get("isdir", 0)),
                "modified": f.get("server_mtime", 0),
                "md5": f.get("md5", ""),
                "fs_id": f.get("fs_id", 0),
            }
            for f in data.get("list", [])
        ]

    async def create_folder(self, path: str) -> dict:
        r = await self._client.post(
            f"{self.PAN_API}/create",
            data={
                "path": path,
                "isdir": 1,
                "block_list": "[]",
                "channel": "dubox",
                "web": 1,
                "clienttype": 0,
            },
        )
        return self._check(r.json(), "create_folder")

    async def search(self, keyword: str, path: str = "/", recursion: int = 1) -> list[dict]:
        params = {
            "key": keyword,
            "dir": path,
            "recursion": recursion,
            "web": 1,
            "page": 1,
            "num": 50,
            "channel": "dubox",
            "clienttype": 0,
        }
        r = await self._client.get(f"{self.PAN_API}/search", params=params)
        data = self._check(r.json(), "search")
        return [
            {
                "name": f["server_filename"],
                "path": f["path"],
                "size": f.get("size", 0),
                "is_dir": bool(f.get("isdir", 0)),
                "fs_id": f.get("fs_id", 0),
            }
            for f in data.get("list", [])
        ]

    async def delete_files(self, paths: list[str]) -> dict:
        filelist = json.dumps(paths)
        r = await self._client.post(
            f"{self.PAN_API}/filemanager",
            params={"opera": "delete", "web": 1, "clienttype": 0},
            data={"filelist": filelist, "async": 1},
        )
        return self._check(r.json(), "delete_files")

    async def move_files(self, file_list: list[dict]) -> dict:
        """file_list: [{"path": "/src", "dest": "/dst", "newname": "name"}]"""
        r = await self._client.post(
            f"{self.PAN_API}/filemanager",
            params={"opera": "move", "web": 1, "clienttype": 0},
            data={"filelist": json.dumps(file_list), "async": 1},
        )
        return self._check(r.json(), "move_files")

    async def copy_files(self, file_list: list[dict]) -> dict:
        r = await self._client.post(
            f"{self.PAN_API}/filemanager",
            params={"opera": "copy", "web": 1, "clienttype": 0},
            data={"filelist": json.dumps(file_list), "async": 1},
        )
        return self._check(r.json(), "copy_files")

    async def get_download_link(self, path: str) -> str:
        """Get direct download link for a file."""
        r = await self._client.get(
            f"{self.PAN_API}/download",
            params={"path": path, "web": 1, "clienttype": 0},
        )
        data = r.json()
        dlink = data.get("dlink", "")
        if not dlink:
            raise TeraboxError(f"No download link returned for {path}")
        return dlink

    async def create_share(self, fs_ids: list[int], period: int = 0,
                           password: str = "") -> dict:
        """Create a share link. period=0 means permanent."""
        data: dict[str, Any] = {
            "fid_list": json.dumps(fs_ids),
            "schannel": 0,
            "channel_list": "[]",
            "period": period,
        }
        if password:
            data["pwd"] = password
        r = await self._client.post(
            f"{self.PAN_API}/share/set",
            params={"web": 1, "clienttype": 0},
            data=data,
        )
        result = self._check(r.json(), "create_share")
        return {
            "link": result.get("link", ""),
            "shareid": result.get("shareid", ""),
            "password": password,
        }

    async def precreate_upload(self, remote_path: str, size: int,
                               block_md5_list: list[str], content_md5: str) -> dict:
        r = await self._client.post(
            f"{self.PAN_API}/precreate",
            params={"web": 1, "clienttype": 0},
            data={
                "path": remote_path,
                "size": size,
                "isdir": 0,
                "autoinit": 1,
                "block_list": json.dumps(block_md5_list),
                "content-md5": content_md5,
                "slice-md5": block_md5_list[0] if block_md5_list else "",
            },
        )
        return self._check(r.json(), "precreate_upload")

    async def upload_chunk(self, remote_path: str, partseq: int,
                           chunk: bytes, uploadid: str) -> dict:
        files = {"file": ("blob", chunk, "application/octet-stream")}
        r = await self._client.post(
            f"{self.UPLOAD_BASE}/rest/2.0/pcs/superfile2",
            params={
                "method": "upload",
                "type": "tmpfile",
                "path": remote_path,
                "partseq": partseq,
                "uploadid": uploadid,
            },
            files=files,
        )
        return r.json()

    async def create_upload(self, remote_path: str, size: int,
                            uploadid: str, block_md5_list: list[str],
                            content_md5: str) -> dict:
        r = await self._client.post(
            f"{self.PAN_API}/create",
            params={"web": 1, "clienttype": 0},
            data={
                "path": remote_path,
                "size": size,
                "isdir": 0,
                "uploadid": uploadid,
                "block_list": json.dumps(block_md5_list),
                "content-md5": content_md5,
            },
        )
        return self._check(r.json(), "create_upload")

    async def upload_file(self, local_path: str | Path,
                          remote_path: str,
                          chunk_size: int = 4 * 1024 * 1024) -> dict:
        """Upload a local file to Terabox with chunked upload."""
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(str(local_path))

        data = local_path.read_bytes()
        size = len(data)
        content_md5 = hashlib.md5(data).hexdigest()

        chunks = [data[i:i + chunk_size] for i in range(0, size, chunk_size)] or [b""]
        block_md5_list = [hashlib.md5(c).hexdigest() for c in chunks]

        pre = await self.precreate_upload(remote_path, size, block_md5_list, content_md5)

        if pre.get("return_type") == 2:
            return {"status": "rapid_upload", "path": remote_path, "fs_id": pre.get("fs_id")}

        uploadid = pre["uploadid"]
        for i, chunk in enumerate(chunks):
            await self.upload_chunk(remote_path, i, chunk, uploadid)

        result = await self.create_upload(remote_path, size, uploadid, block_md5_list, content_md5)
        return {"status": "uploaded", "path": remote_path, "fs_id": result.get("fs_id"), "size": size}

    async def download_file(self, remote_path: str, local_path: str | Path) -> dict:
        """Download a file from Terabox to local disk."""
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        dlink = await self.get_download_link(remote_path)
        async with httpx.AsyncClient(headers=self.headers, timeout=300.0,
                                     follow_redirects=True) as dl:
            r = await dl.get(dlink)
            r.raise_for_status()
            local_path.write_bytes(r.content)
        return {"status": "downloaded", "path": str(local_path), "size": len(r.content)}

    async def get_file_info(self, paths: list[str]) -> list[dict]:
        params = {
            "web": 1,
            "clienttype": 0,
            "fsids": json.dumps([]),
            "dlink": 1,
        }
        r = await self._client.post(
            f"{self.PAN_API}/filemetas",
            params=params,
            data={"target": json.dumps(paths)},
        )
        data = self._check(r.json(), "get_file_info")
        return data.get("info", [])
