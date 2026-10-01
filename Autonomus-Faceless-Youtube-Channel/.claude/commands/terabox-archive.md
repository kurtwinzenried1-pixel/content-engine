# Terabox Archive Skill

Archive, manage and retrieve content from Terabox cloud storage (1 TB free) as part of the autonomous YouTube channel pipeline.

## Setup

### 1. Get your session cookie

Log into [terabox.com](https://www.terabox.com), open DevTools → Application → Cookies → `www.terabox.com` and copy the full cookie string.

### 2. Export the cookie

```bash
export TERABOX_COOKIE="ndut=...; BAIDUID=...; BDUSS=...; ..."
```

Add to your shell profile or `.env` file (never commit to git).

### 3. Register the MCP server

```bash
claude mcp add terabox-archive python /path/to/src/mcp/terabox-mcp/server.py
```

Or add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "terabox-archive": {
      "command": "python",
      "args": ["src/mcp/terabox-mcp/server.py"],
      "env": {
        "TERABOX_COOKIE": "<your-cookie-here>"
      }
    }
  }
}
```

---

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `terabox_quota` | Show storage usage (total / used / free GB) |
| `terabox_list` | List files in a folder |
| `terabox_search` | Search files by keyword |
| `terabox_create_folder` | Create a folder |
| `terabox_upload` | Upload a local file |
| `terabox_download` | Download a file to local disk |
| `terabox_delete` | Delete files/folders |
| `terabox_move` | Move or rename files |
| `terabox_share` | Generate a shareable link |
| `terabox_get_download_link` | Get direct download URL |
| `terabox_archive_content` | Auto-archive to organised channel folder |

---

## YouTube Channel Workflow

### Archive a finished video
```
terabox_archive_content(
  local_path="/output/episode_42.mp4",
  content_type="video",
  channel_name="my-channel"
)
→ uploads to /youtube-channel/my-channel/video/episode_42.mp4
```

### Archive TTS audio
```
terabox_archive_content(
  local_path="/tts/narration_ep42.wav",
  content_type="audio",
  channel_name="my-channel"
)
```

### Archive AI-generated thumbnail
```
terabox_archive_content(
  local_path="/assets/thumbnail_ep42.jpg",
  content_type="thumbnail",
  channel_name="my-channel"
)
```

### Archive video script
```
terabox_archive_content(
  local_path="/scripts/ep42_script.txt",
  content_type="script",
  channel_name="my-channel"
)
```

### List archived videos
```
terabox_list(path="/youtube-channel/my-channel/video")
```

### Check storage
```
terabox_quota()
→ { "total_gb": 1024, "used_gb": 12.4, "free_gb": 1011.6, "used_pct": 1.2 }
```

### Share a file
```
# Step 1: Get fs_id from list
files = terabox_list(path="/youtube-channel/my-channel/video")
# Step 2: Create share link
terabox_share(fs_ids=[files[0]["fs_id"]], period=0)
→ { "link": "https://terabox.com/s/...", "password": "" }
```

---

## Folder Structure

The `terabox_archive_content` tool organises content automatically:

```
/youtube-channel/
  {channel-name}/
    video/          ← rendered .mp4 files
    audio/          ← TTS narration, background music
    image/          ← AI-generated scene images
    thumbnail/      ← YouTube thumbnails
    script/         ← episode scripts / prompts
    subtitle/       ← .srt / .vtt subtitle files
    misc/           ← everything else
```

---

## Content Types

| Type | Examples |
|------|---------|
| `video` | `.mp4`, `.mkv`, `.webm` |
| `audio` | `.wav`, `.mp3`, `.flac` |
| `image` | `.jpg`, `.png`, `.webp` |
| `thumbnail` | YouTube thumbnail JPEGs |
| `script` | `.txt`, `.md` episode scripts |
| `subtitle` | `.srt`, `.vtt` caption files |
| `misc` | Any other assets |

---

## Integration with Pipeline

This skill integrates with other tools in the repository:

- **faster-whisper** → transcribe audio → archive subtitle with `content_type="subtitle"`
- **moviepy / ffmpeg** → render video → archive with `content_type="video"`
- **diffusers / pillow** → generate images → archive with `content_type="image"`
- **openvoice** → clone voice TTS → archive audio with `content_type="audio"`
- **open-interpreter** → generate scripts → archive with `content_type="script"`

---

## Security Notes

- **Never commit your cookie** to git — it grants full account access
- The cookie expires after ~30 days; refresh it by re-logging in
- For CI/CD use, inject `TERABOX_COOKIE` as a GitHub Actions secret
- Terabox sessions are region-locked; use a stable IP/VPN if needed
