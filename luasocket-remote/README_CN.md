# Cheat Engine MCP Bridge (LuaSocket)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)](https://python.org)
[![Version](https://img.shields.io/badge/version-12.0.0--LuaSocket-blue.svg)]()

*[cheatengine-mcp-bridge](https://github.com/miscusi-peek/cheatengine-mcp-bridge) 的 TCP 传输层变体，原作者为 miscusi-peek。桥接架构、所有 MCP 工具和 Lua 命令处理程序全部归功于原作者。本 fork 仅添加了基于 LuaSocket 的 TCP 传输层，使 AI 客户端和 Cheat Engine 可以在不同机器上运行。*

[English Documentation](README.md) | [Русская документация](README_RU.md)

## 为什么会有这个 Fork

原项目非常出色且功能完备。唯一的局限是它的 Named Pipe 传输层要求 AI 客户端和 Cheat Engine 必须在**同一台 Windows 机器**上。本 fork 将传输层替换为 TCP，使你可以：

- 在任意机器（本地开发机、云服务器、容器）上运行 MCP Python 服务
- 在专用的远程 Windows 服务器上运行 Cheat Engine
- 从网络的任何位置控制游戏内存

除此之外一切保持不变：所有约 180 个 MCP 工具、JSON-RPC 通信协议、命令命名规范以及线程安全的 CE 架构，均完全沿用原项目的设计。

## 架构

```
AI 客户端 ──(MCP / JSON-RPC over stdio)──▶ mcp_cheatengine_remote.py
                                                       │
                                                       ▼ (TCP, 长度前缀 + JSON-RPC)
                                              ce_mcp_bridge_remote.lua
                                                  (在 Cheat Engine 中运行)
                                                       │
                                                       ▼ (CE Lua API / DBVM)
                                                 目标进程内存
```

| 层级 | 原项目 | 本 Fork |
|------|--------|---------|
| AI ↔ Python | stdio (同一机器) | stdio (同一机器) |
| Python ↔ CE | `\\.\pipe\CE_MCP_Bridge_v99` (仅本地) | TCP 套接字 (跨机器) |
| CE ↔ 目标 | CE Lua API | CE Lua API (不变) |

## 项目结构

```
cheatengine-mcp-bridge/
├── MCP_Server/                   # 原项目 MCP 服务端 (Named Pipe)
├── AI_Context/                   # 原项目文档
├── luasocket-remote/             # 本项目 — LuaSocket TCP 扩展
│   ├── mcp_cheatengine_remote.py # Python MCP 服务端 — 通过 TCP 连接 CE
│   ├── ce_mcp_bridge_remote.lua  # Lua TCP 桥接 — 在 Cheat Engine 中加载
│   ├── requirements.txt          # Python 依赖 (mcp>=1.0.0)
│   ├── luasocket-ce-deploy/      # 一键部署 LuaSocket 到 CE
│   │   ├── deploy.py             # 自动检测 CE、匹配 Lua 版本、安装 DLL
│   │   ├── prebuilt/             # 预编译 LuaSocket DLL (Lua 5.1/5.3/5.4, x64)
│   │   ├── lua/                  # 纯 Lua 模块
│   │   └── src/                  # LuaSocket 3.1.0 C 源码 (备选编译)
│   ├── README.md                 # 英文文档
│   ├── README_CN.md              # 本文件
│   └── README_RU.md              # 俄文文档
├── README.md                     # 原项目 README
└── LICENSE                       # MIT
```

## 快速开始

### 前置条件

- **远程 Windows 服务器**：已安装 [Cheat Engine 7.x](https://www.cheatengine.org/)
- **本地机器**：Python 3.10+（任意操作系统，Windows 最简单）
- 两台机器之间网络互通

### 第一步：将 LuaSocket 部署到 Cheat Engine

Cheat Engine **不自带** `socket` 库，而 TCP 桥接需要它。在远程 Windows 服务器上执行：

```powershell
cd luasocket-remote/luasocket-ce-deploy
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"
```

脚本会自动检测 CE 使用的 Lua 版本，匹配正确的预编译 DLL，并将所有文件复制到正确位置。可先用 `--dry-run` 预览。

### 第二步：在 Cheat Engine 中加载桥接

在远程 Windows 服务器上打开 Cheat Engine：

1. 附加到目标进程（也可以稍后由 AI 智能体完成）
2. `File` → `Execute Script` → 选择 `luasocket-remote/ce_mcp_bridge_remote.lua` → `Execute`

你应该看到：`[MCP v12.0.0] TCP Server listening on 0.0.0.0:9999`

### 第三步：启动 Python MCP 服务

在你的本地机器上：

```bash
pip install -r luasocket-remote/requirements.txt

# 连接到远程服务器上的 CE
python luasocket-remote/mcp_cheatengine_remote.py --host 192.168.1.100 --port 9999
```

命令行参数：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--host` | `127.0.0.1` | CE 服务器的 IP 或主机名 |
| `--port` | `9999` | TCP 端口（需与 Lua 端一致） |

### 第四步：配置 AI 客户端

将支持 MCP 的 AI 客户端（Claude Code、Codex 等）指向 `luasocket-remote/mcp_cheatengine_remote.py`。

**Claude Code / Claude Desktop** — 添加到 `.mcp.json`：

```json
{
  "mcpServers": {
    "cheatengine": {
      "command": "python",
      "args": [
        "C:\\path\\to\\cheatengine-mcp-bridge\\mcp_cheatengine_remote.py",
        "--host", "192.168.1.100",
        "--port", "9999"
      ]
    }
  }
}
```

**Codex (OpenAI)** — 添加到 `.codex.toml`：

```toml
[mcp_servers.cheatengine]
command = "python"
args = ['C:\\path\\to\\cheatengine-mcp-bridge\\mcp_cheatengine_remote.py', '--host', '192.168.1.100', '--port', '9999']
```

重启 AI 客户端，使用 `ping` 工具验证连接 —— 应返回桥接版本号。

## 可用 MCP 工具

桥接暴露约 180 个工具，按类别分组（全部继承自原项目）：

| 类别 | 工具示例 | 说明 |
|------|---------|------|
| 进程 | `attach_process`, `detach_process`, `get_process_info`, `get_pid`, `get_arch` | 管理目标进程 |
| 内存 | `read_memory`, `write_memory`, `read_pointer`, `read_string`, `find_bytes` | 内存读写/扫描 |
| 模块 | `enum_modules`, `get_module_info`, `find_symbol` | 模块枚举 |
| 断点 | `set_breakpoint`, `remove_breakpoint`, `list_breakpoints`, `get_breakpoint_hits` | 硬件断点 |
| DBVM | `start_dbvm_watch`, `stop_dbvm_watch`, `list_dbvm_watches`, `get_dbvm_stats` | 虚拟化层追踪 |
| 汇编 | `assemble`, `disassemble`, `get_instruction_info` | x86/x64 汇编 |
| 寄存器 | `get_registers`, `set_register`, `get_stack` | 寄存器和栈检查 |
| 代码注入 | `allocate_memory`, `inject_dll`, `create_thread`, `call_function` | 远程代码执行 |
| GUI | `get_control_list`, `click_control`, `send_key`, `get_foreground_window` | CE 界面自动化 |
| Cheat Table | `load_cheat_table`, `activate_entry`, `get_entry_list` | Cheat Table 管理 |
| Shell | `run_command`, `shell_execute` | 命令执行（默认禁用） |

完整 API 参考见原项目的 `AI_Context/MCP_Bridge_Command_Reference.md`。

## 安全注意事项

- TCP 桥接默认绑定 `0.0.0.0` —— 建议通过 Windows 防火墙限制为特定 IP
- TCP 通道没有认证或加密。请在可信网络或 VPN 中运行
- Shell 执行工具（`run_command`, `shell_execute`）默认禁用；设置 `CE_MCP_ALLOW_SHELL=1` 启用
- 为反作弊安全，优先使用硬件断点（DR0–DR3）和 DBVM watches，而非软件断点（`0xCC`）
- CE 设置 → 附加 → 禁用 "Query memory region routines"，防止 DBVM 扫描时蓝屏

## 故障排除

### "LuaSocket is not installed"

运行 `deploy.py`（见第一步）。CE 不自带 LuaSocket。

### "Connection refused" 或超时

- 确认 Lua 脚本已在 CE 中加载，并显示 `TCP Server listening on 0.0.0.0:9999`
- 检查 Windows 防火墙是否允许 TCP 9999 端口的入站连接
- 使用 `nmap -p 9999 <remote-ip>` 验证端口是否开放
- 如果 nmap 显示 `closed`，可能是 Lua 脚本绑定了 IPv6 —— 本项目的 `ce_mcp_bridge_remote.lua` 已使用 `tcp4()` 防止此问题

### 间歇性断连

TCP 工作线程使用 60 秒读取超时。如果连接断开，Python 客户端会在下一次请求时自动重连。

### 运行 deploy.py 提示权限被拒绝

`C:\Program Files\` 受 UAC 保护。右键 PowerShell → 以管理员身份运行。

## 从源码编译 LuaSocket

如果你的 CE 使用的 Lua 版本不在预编译支持范围内，或者是 32 位 CE：

详见 `luasocket-remote/luasocket-ce-deploy/README.md` → Building from Source。需要安装 Visual Studio（含 C++ 工作负载）和匹配的 Lua 源码。

## 致谢与许可证

MIT — 详见 [LICENSE](LICENSE)。

原项目：[cheatengine-mcp-bridge](https://github.com/miscusi-peek/cheatengine-mcp-bridge) v12.0.0，作者 miscusi-peek（MIT 许可证）。本 fork 深深受惠于该项目——桥接架构、全部 180 个 MCP 工具处理程序以及线程安全的 CE 集成均完全来自原项目。

LuaSocket 3.1.0 Copyright (C) 2004-2022 Diego Nehab，基于 MIT 许可证使用。
