# LuaSocket CE 部署工具

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/)

*一键将 LuaSocket 部署到 Cheat Engine — 自动检测 Lua 版本、匹配预编译 DLL、安装到正确路径。*

[English Documentation](README.md) | [Русская документация](README_RU.md)

## 这是什么？

[Cheat Engine](https://www.cheatengine.org/) 自带的 Lua 引擎缺少 `socket` 和 `mime` 库（LuaSocket）。这意味着基于 TCP/HTTP 的远程调试脚本无法直接使用。

此工具**自动化所有繁琐步骤**：

- 自动发现 CE 安装目录
- 自动检测 CE 使用的 Lua 版本（5.1 / 5.3 / 5.4）
- 自动匹配对应版本的预编译 luasocket DLL
- 自动复制 `.lua` 模块和 `.dll` 文件到正确位置
- 部署后自动验证

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/YOURNAME/luasocket-ce-deploy.git
cd luasocket-ce-deploy

# 2. 运行部署脚本
python deploy.py

# 或直接指定 CE 路径
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"

# 预览模式（不实际写入文件）
python deploy.py --dry-run
```

**运行要求：** Python 3.6+。不需要任何第三方包。

## 命令行参数

| 参数 | 说明 |
|------|------|
| `--ce PATH` | 指定 Cheat Engine 根目录路径 |
| `--force` | 跳过所有确认提示 |
| `--dry-run` | 预览部署内容，不写入任何文件 |
| `--check-only` | 仅运行环境检查，不执行部署 |
| `--list-prebuilt` | 列出可用的预编译二进制文件并退出 |

## 支持矩阵

| Cheat Engine | Lua 版本 | DLL 名称 | 状态 |
|-------------|----------|----------|------|
| CE 6.x | Lua 5.1 | `lua51-64.dll` | 预编译 ✓ |
| CE 7.0 – 7.4 | Lua 5.3 | `lua53-64.dll` | 预编译 ✓ |
| CE 7.5+ | Lua 5.4 | `lua54-64.dll` | 预编译 ✓ |

所有预编译 DLL 均为 **x86-64 (64-bit)**，使用 Visual Studio 2026 (MSVC 19.50) 编译。

## 项目结构

```
luasocket-ce-deploy/
├── deploy.py                    # 主部署脚本
├── prebuilt/                    # 预编译 DLL
│   ├── lua51/
│   │   ├── socket/core.dll      # Lua 5.1 用
│   │   └── mime/core.dll
│   ├── lua53/
│   │   ├── socket/core.dll      # Lua 5.3 用
│   │   └── mime/core.dll
│   └── lua54/
│       ├── socket/core.dll      # Lua 5.4 用
│       └── mime/core.dll
├── lua/                         # 纯 Lua 模块
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
├── src/                         # LuaSocket 3.1.0 C 源码
├── README.md
├── README_CN.md
└── README_RU.md
```

## 工作原理

1. **查找 CE** — 扫描常见路径（`C:\Program Files\Cheat Engine*`、注册表、用户指定路径）
2. **检测 Lua 版本** — 读取 CE 目录下 `lua*-64.dll` 文件名（如 `lua53-64.dll` → Lua 5.3）
3. **匹配预编译二进制** — 从 `prebuilt/` 选择对应版本的 `core.dll`
4. **复制文件** — Lua 模块复制到 `CE\lua\`，原生 DLL 复制到 `CE\socket\core.dll` 和 `CE\mime\core.dll`
5. **验证** — 检查部署的 DLL 是否正确链接到对应的 Lua DLL

> **关键：** CE 搜索 `.lua` 文件走 `CE\lua\` 目录，但搜索 `.dll` 文件直接从 CE 根目录搜索。这就是为什么 DLL 放在 `CE\socket\core.dll` 而**不是** `CE\lua\socket\core.dll`。

## 验证安装

在 CE 的 Lua 引擎中（`Ctrl+Alt+L`）执行：

```lua
print(require("socket")._VERSION)  --> LuaSocket 3.1.0
print(require("mime")._VERSION)    --> MIME 1.0.3

-- TCP 功能快速测试
local http = require("socket.http")
local body, code = http.request("http://httpbin.org/get")
print(code, #body)
```

## 故障排除

### "找不到指定的模块"

luasocket DLL 编译时链接的 Lua DLL 名称与 CE 实际使用的名称不一致。

**解决：** 运行 `python deploy.py --check-only` 确认检测到的 Lua 版本。手动检查 CE 目录下的 `lua*-64.dll` 文件。

### "module 'socket.core' not found"

DLL 放在了错误的目录。

**正确布局：**
```
C:\Program Files\Cheat Engine\
├── lua\
│   └── socket.lua     ← .lua 文件放这里
├── socket\
│   └── core.dll       ← .dll 文件放这里（CE 根目录下）
└── mime\
    └── core.dll
```

### 权限被拒绝

`C:\Program Files\` 受 UAC 保护。以管理员身份运行脚本：

```powershell
# 右键 PowerShell → 以管理员身份运行
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"
```

### 杀软误报

Windows Defender 可能会标记 `core.dll`，因为它链接了 `ws2_32.dll`（Windows 套接字）。将 CE 目录添加到杀软的排除列表或为对应文件创建例外。

## 从源码编译

如果 CE 使用的 Lua 版本不在预编译支持范围内，或者是 32 位 CE：

### 前置条件

- Visual Studio 2022/2025/2026，含"使用 C++ 的桌面开发"工作负载
- 或 Visual Studio Build Tools
- 与 CE Lua 版本匹配的 Lua 源码（[lua.org/ftp](https://www.lua.org/ftp/)）

### 步骤

```bash
# 1. 编译 Lua DLL，使用 CE 命名规范（示例：Lua 5.3）
cl /MD /O2 /c /DLUA_BUILD_AS_DLL l*.c
link /DLL /OUT:lua53-64.dll /IMPLIB:lua53-64.lib *.obj

# 2. 编译 luasocket，链接到 CE 的 Lua DLL
cl /MD /O2 /c /DLUASOCKET_API=__declspec(dllexport) wsocket.c auxiliar.c ...
link /DLL /OUT:socket\core.dll *.obj lua53-64.lib ws2_32.lib

# 3. 编译 mime
cl /MD /O2 /c /DMIME_API=__declspec(dllexport) mime.c compat.c
link /DLL /OUT:mime\core.dll *.obj lua53-64.lib
```

## 为什么 CE 改名了 Lua DLL

Cheat Engine 将 Lua DLL 改名（如 `lua53-64.dll` 而非 `lua53.dll`），因为它在同一目录中同时打包了 32 位和 64 位 Lua。`-64` 后缀避免了文件名冲突。任何原生 Lua 模块都必须链接到这个确切的 DLL 名称，这正是本工具自动处理的事情。

## 许可证

MIT — 详见 [LICENSE](LICENSE) 文件。

LuaSocket 3.1.0 Copyright (C) 2004-2022 Diego Nehab，基于 MIT 许可证使用。
