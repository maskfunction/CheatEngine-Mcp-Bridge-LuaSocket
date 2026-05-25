# LuaSocket CE Deployment Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/)

*One-click deploy LuaSocket into Cheat Engine — auto-detect Lua version, match pre-built DLLs, install to correct paths.*

[中文文档](README_CN.md) | [Русская документация](README_RU.md)

## What Is This?

[Cheat Engine](https://www.cheatengine.org/) ships with a Lua engine, but it lacks `socket` and `mime` (LuaSocket). This means TCP/HTTP-based remote debugging scripts won't work out of the box.

This tool **automates every step**:

- Auto-discovers your CE installation directory
- Auto-detects which Lua version CE uses (5.1 / 5.3 / 5.4)
- Auto-matches the matching pre-compiled luasocket DLL
- Auto-copies `.lua` modules and `.dll` files to the correct locations
- Validates the deployment when done

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/YOURNAME/luasocket-ce-deploy.git
cd luasocket-ce-deploy

# 2. Run the deploy script
python deploy.py

# Or specify CE path directly
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"

# Preview mode (no files are actually written)
python deploy.py --dry-run
```

**Requirements:** Python 3.6+. No third-party packages needed.

## Command-Line Flags

| Flag | Description |
|------|-------------|
| `--ce PATH` | Path to Cheat Engine root directory |
| `--force` | Skip all confirmation prompts |
| `--dry-run` | Preview what would be deployed; don't write anything |
| `--check-only` | Only run environment checks, skip deployment |
| `--list-prebuilt` | List available pre-compiled binaries and exit |

## Support Matrix

| Cheat Engine | Lua Version | DLL Name | Status |
|-------------|-------------|----------|--------|
| CE 6.x | Lua 5.1 | `lua51-64.dll` | Pre-built ✓ |
| CE 7.0 – 7.4 | Lua 5.3 | `lua53-64.dll` | Pre-built ✓ |
| CE 7.5+ | Lua 5.4 | `lua54-64.dll` | Pre-built ✓ |

All pre-built DLLs are **x86-64 (64-bit)**, compiled with Visual Studio 2026 (MSVC 19.50).

## Project Layout

```
luasocket-ce-deploy/
├── deploy.py                    # Main deployment script
├── prebuilt/                    # Pre-compiled DLLs
│   ├── lua51/
│   │   ├── socket/core.dll
│   │   └── mime/core.dll
│   ├── lua53/
│   │   ├── socket/core.dll
│   │   └── mime/core.dll
│   └── lua54/
│       ├── socket/core.dll
│       └── mime/core.dll
├── lua/                         # Pure-Lua modules
│   ├── socket.lua
│   ├── mime.lua
│   ├── ltn12.lua
│   └── socket/
│       ├── http.lua
│       ├── ftp.lua
│       ├── smtp.lua
│       ├── tp.lua
│       ├── url.lua
│       └── headers.lua
├── src/                         # LuaSocket 3.1.0 C source
├── README.md
├── README_CN.md
└── README_RU.md
```

## How It Works

1. **Find CE** — scans common paths (`C:\Program Files\Cheat Engine*`, registry entries, user-supplied path)
2. **Detect Lua version** — reads `lua*-64.dll` file names in the CE directory (e.g. `lua53-64.dll` → Lua 5.3)
3. **Match pre-built binary** — selects the matching `core.dll` from `prebuilt/`
4. **Copy files** — Lua modules go to `CE\lua\`, native DLLs go to `CE\socket\core.dll` and `CE\mime\core.dll`
5. **Verify** — checks that the deployed DLLs link against the correct Lua DLL

> **Important:** CE searches for `.lua` files in `CE\lua\`, but searches for `.dll` files directly from the CE root directory. This is why the DLLs go to `CE\socket\core.dll` and **not** `CE\lua\socket\core.dll`.

## Verifying the Installation

Open CE's Lua Engine (`Ctrl+Alt+L`) and run:

```lua
print(require("socket")._VERSION)  --> LuaSocket 3.1.0
print(require("mime")._VERSION)    --> MIME 1.0.3

-- Quick TCP smoke test
local http = require("socket.http")
local body, code = http.request("http://httpbin.org/get")
print(code, #body)
```

## Troubleshooting

### "The specified module could not be found"

The luasocket DLL was compiled against a different Lua DLL name than what CE has.

**Fix:** Run `python deploy.py --check-only` to verify the detected Lua version. Check which `lua*-64.dll` files exist in your CE directory.

### "module 'socket.core' not found"

The DLL is in the wrong directory.

**Correct layout:**
```
C:\Program Files\Cheat Engine\
├── socket\
│   └── core.dll       ← DLL goes HERE (CE root)
├── mime\
│   └── core.dll
└── lua\
    └── socket.lua     ← Lua modules go HERE (lua\ folder)
```

### Permission Denied

`C:\Program Files\` is UAC-protected. Run the script as Administrator:

```powershell
# Right-click PowerShell → Run as Administrator
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"
```

### AV False Positive

Windows Defender may flag `core.dll` because it links against `ws2_32.dll` (Windows Sockets). Add the CE directory to your AV exclusion list or create an exception for the files.

## Building from Source

If your CE uses a Lua version not covered by the pre-built binaries, or you're on 32-bit CE:

### Prerequisites

- Visual Studio 2022/2025/2026 with "Desktop development with C++" workload
- Or Visual Studio Build Tools
- Lua source code matching your CE's Lua version ([lua.org/ftp](https://www.lua.org/ftp/))

### Steps

```bash
# 1. Build Lua DLL with CE naming convention (example: Lua 5.3)
cl /MD /O2 /c /DLUA_BUILD_AS_DLL l*.c
link /DLL /OUT:lua53-64.dll /IMPLIB:lua53-64.lib *.obj

# 2. Build luasocket linked against CE's Lua DLL
cl /MD /O2 /c /DLUASOCKET_API=__declspec(dllexport) wsocket.c auxiliar.c ...
link /DLL /OUT:socket\core.dll *.obj lua53-64.lib ws2_32.lib

# 3. Build mime
cl /MD /O2 /c /DMIME_API=__declspec(dllexport) mime.c compat.c
link /DLL /OUT:mime\core.dll *.obj lua53-64.lib
```

## Why CE Renames Lua DLLs

Cheat Engine ships with a renamed Lua DLL (`lua53-64.dll` instead of `lua53.dll`) because it bundles both 32-bit and 64-bit Lua in the same directory. The `-64` suffix prevents filename collisions. Any native Lua module must be linked against this exact DLL name, which is what this tool handles automatically.

## License

MIT — see [LICENSE](LICENSE) file.

LuaSocket 3.1.0 is copyright Diego Nehab (1999–2013), used under the MIT license.
