# Cheat Engine MCP Bridge (LuaSocket)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*A fork of [cheatengine-mcp-bridge](https://github.com/miscusi-peek/cheatengine-mcp-bridge) that adds TCP remote connectivity — let AI agents drive Cheat Engine on a remote Windows server over the network.*

[中文文档](README_CN.md) | [Русская документация](README_RU.md)

## What's New vs. the Original

The original bridge communicates over a Windows Named Pipe, which only works when the AI client and Cheat Engine are on the **same machine**. This fork replaces the transport with TCP, so you can:

- Run the MCP Python server on any machine (local dev box, cloud VM, container)
- Keep Cheat Engine running on a dedicated remote Windows server
- Control game memory inspection/manipulation from anywhere on the network

Everything else is preserved: all ~180 MCP tools, the JSON-RPC wire protocol, the handler naming conventions, and the multi-threaded CE-safe architecture.

## Architecture

```
AI client ──(MCP / JSON-RPC over stdio)──▶ mcp_cheatengine_remote.py
                                                       │
                                                       ▼ (TCP, length-prefixed JSON-RPC)
                                              ce_mcp_bridge_remote.lua
                                                  (inside Cheat Engine)
                                                       │
                                                       ▼ (CE Lua API / DBVM)
                                                 Target process memory
```

Compared to the original:

| Layer | Original | LuaSocket Edition |
|-------|----------|----------------|
| AI ↔ Python | stdio (same machine) | stdio (same machine) |
| Python ↔ CE | `\\.\pipe\CE_MCP_Bridge_v99` (local only) | TCP socket (cross-machine) |
| CE ↔ Target | CE Lua API | CE Lua API (unchanged) |

## Project Structure

```
cheatengine-mcp-bridge-luasocket/
├── mcp_cheatengine_remote.py    # Python MCP server — connects to remote CE via TCP
├── ce_mcp_bridge_remote.lua     # Lua TCP bridge — load this in Cheat Engine
├── requirements.txt             # Python dependencies (mcp>=1.0.0)
├── luasocket-ce-deploy/         # One-click LuaSocket deployment for CE
│   ├── deploy.py                # Auto-detect CE, match Lua version, install DLLs
│   ├── prebuilt/                # Pre-compiled LuaSocket DLLs (Lua 5.1/5.3/5.4, x64)
│   ├── lua/                     # Pure-Lua socket modules
│   └── src/                     # LuaSocket 3.1.0 C source (fallback compilation)
├── README.md                    # This file
├── README_CN.md                 # Chinese documentation
├── README_RU.md                 # Russian documentation
└── LICENSE                      # MIT
```

## Quick Start

### Prerequisites

- **Remote Windows server** with [Cheat Engine 7.x](https://www.cheatengine.org/) installed
- **Local machine** with Python 3.10+ (any OS, but Windows is simplest)
- Network connectivity between the two machines

### Step 1: Deploy LuaSocket to Cheat Engine

Cheat Engine does **not** include the `socket` library. The TCP bridge needs it. On the remote Windows server:

```powershell
cd luasocket-ce-deploy
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"
```

This auto-detects your CE's Lua version, matches the correct pre-built DLL, and copies all files to the right locations. Use `--dry-run` to preview first.

### Step 2: Load the Bridge in Cheat Engine

On the remote Windows server, open Cheat Engine and:

1. Attach to the target process (or let the AI agent do it later)
2. `File` → `Execute Script` → select `ce_mcp_bridge_remote.lua` → `Execute`

You should see: `[MCP v12.0.0] TCP Server listening on 0.0.0.0:9999`

### Step 3: Start the Python MCP Server

On your local machine:

```bash
pip install -r requirements.txt

# Connect to CE on the remote server
python mcp_cheatengine_remote.py --host 192.168.1.100 --port 9999
```

Command-line options:

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Remote CE server IP or hostname |
| `--port` | `9999` | TCP port (must match the Lua side) |

### Step 4: Configure Your AI Client

Point your MCP-compatible AI client (Claude Code, Codex, etc.) at `mcp_cheatengine_remote.py`.

**Claude Code / Claude Desktop** — add to `.mcp.json`:

```json
{
  "mcpServers": {
    "cheatengine": {
      "command": "python",
      "args": [
        "C:\\path\\to\\MCP_Server_Remote\\mcp_cheatengine_remote.py",
        "--host", "192.168.1.100",
        "--port", "9999"
      ]
    }
  }
}
```

**Codex (OpenAI)** — add to `.codex.toml`:

```toml
[mcp_servers.cheatengine]
command = "python"
args = ['C:\path\to\MCP_Server_Remote\mcp_cheatengine_remote.py', '--host', '192.168.1.100', '--port', '9999']
```

Restart the AI client, then verify with the `ping` tool — it should return the bridge version.

## Available MCP Tools

The bridge exposes ~180 tools grouped by category:

| Category | Tools | Description |
|----------|-------|-------------|
| Process | `attach_process`, `detach_process`, `get_process_info`, `get_pid`, `get_arch` | Manage target process |
| Memory | `read_memory`, `write_memory`, `read_pointer`, `read_string`, `find_bytes` | Memory read/write/scan |
| Modules | `enum_modules`, `get_module_info`, `find_symbol` | Module enumeration |
| Breakpoints | `set_breakpoint`, `remove_breakpoint`, `list_breakpoints`, `get_breakpoint_hits` | Hardware breakpoints |
| DBVM | `start_dbvm_watch`, `stop_dbvm_watch`, `list_dbvm_watches`, `get_dbvm_stats` | Hypervisor-level tracing |
| Assembly | `assemble`, `disassemble`, `get_instruction_info` | x86/x64 assembly |
| Registers | `get_registers`, `set_register`, `get_stack` | Register and stack inspection |
| Code Injection | `allocate_memory`, `inject_dll`, `create_thread`, `call_function` | Remote code execution |
| GUI | `get_control_list`, `click_control`, `send_key`, `get_foreground_window` | CE GUI automation |
| Cheat Table | `load_cheat_table`, `activate_entry`, `get_entry_list` | Cheat table management |
| Shell | `run_command`, `shell_execute` | Command execution (disabled by default) |

For the full API reference, see the original project's `AI_Context/MCP_Bridge_Command_Reference.md`.

## Security Considerations

- The TCP bridge binds to `0.0.0.0` by default — consider restricting with Windows Firewall to your specific IP
- There is no authentication or encryption on the TCP channel. Run it on a trusted network or VPN
- Shell execution tools (`run_command`, `shell_execute`) are disabled by default; enable with `CE_MCP_ALLOW_SHELL=1`
- Prefer hardware breakpoints (DR0–DR3) and DBVM watches over software (`0xCC`) breakpoints for anti-cheat safety
- CE Settings → Extra → disable "Query memory region routines" to prevent BSODs during DBVM scans

## Troubleshooting

### "LuaSocket is not installed"

Run `deploy.py` (see Step 1). CE does not ship with LuaSocket.

### "Connection refused" or timeout

- Verify the Lua script is loaded in CE and shows `TCP Server listening on 0.0.0.0:9999`
- Check Windows Firewall allows inbound TCP on port 9999
- Use `nmap -p 9999 <remote-ip>` to verify port is open
- If nmap shows `closed`, the Lua script may have bound IPv6-only — `ce_mcp_bridge_remote.lua` uses `tcp4()` to prevent this

### Intermittent disconnections

The TCP worker thread uses a 60-second read timeout. If your AI client sends requests less frequently than every 60 seconds, the connection stays alive. If the connection drops, the Python client auto-reconnects on the next request.

### Permission Denied when running deploy.py

`C:\Program Files\` is UAC-protected. Right-click PowerShell → Run as Administrator.

## Building LuaSocket from Source

If your CE uses a Lua version not covered by the pre-built binaries (prebuilt folder), or you're on 32-bit CE:

See `luasocket-ce-deploy/README.md` → Building from Source for detailed instructions. Requires Visual Studio with C++ workload and matching Lua source code.

## License

MIT — see [LICENSE](LICENSE).

Based on [cheatengine-mcp-bridge](https://github.com/miscusi-peek/cheatengine-mcp-bridge) v12.0.0 by miscusi-peek (MIT License).

LuaSocket 3.1.0 is copyright Diego Nehab (1999–2013), used under the MIT license.
