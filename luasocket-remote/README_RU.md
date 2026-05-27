# Cheat Engine MCP Bridge (LuaSocket)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-green.svg)](https://python.org)
[![Version](https://img.shields.io/badge/version-12.0.0--LuaSocket-blue.svg)]()

*TCP-вариант проекта [cheatengine-mcp-bridge](https://github.com/miscusi-peek/cheatengine-mcp-bridge) от miscusi-peek. Архитектура моста, все MCP-инструменты и Lua-обработчики — полностью заслуга оригинального автора. Этот форк добавляет TCP-транспорт на основе LuaSocket, чтобы AI-клиент и Cheat Engine могли работать на разных машинах.*

[English Documentation](README.md) | [中文文档](README_CN.md)

## Зачем нужен этот форк

Оригинальный проект превосходен и полностью функционален. Единственное ограничение — его транспорт через Named Pipe требует, чтобы AI-клиент и Cheat Engine находились на **одной Windows-машине**. Этот форк заменяет транспорт на TCP, позволяя:

- Запускать MCP Python-сервер на любой машине (локальный ПК, облачный сервер, контейнер)
- Держать Cheat Engine на выделенном удалённом Windows-сервере
- Управлять памятью игрового процесса из любой точки сети

Всё остальное без изменений: ~180 MCP-инструментов, JSON-RPC протокол, соглашения об именовании обработчиков и потокобезопасная архитектура CE полностью соответствуют оригиналу.

## Архитектура

```
AI клиент ──(MCP / JSON-RPC через stdio)──▶ mcp_cheatengine_remote.py
                                                       │
                                                       ▼ (TCP, префикс длины + JSON-RPC)
                                              ce_mcp_bridge_remote.lua
                                                  (внутри Cheat Engine)
                                                       │
                                                       ▼ (CE Lua API / DBVM)
                                                 Память целевого процесса
```

| Уровень | Оригинал | Этот форк |
|---------|----------|-----------|
| AI ↔ Python | stdio (одна машина) | stdio (одна машина) |
| Python ↔ CE | `\\.\pipe\CE_MCP_Bridge_v99` (только локально) | TCP-сокет (по сети) |
| CE ↔ Цель | CE Lua API | CE Lua API (без изменений) |

## Структура проекта

```
cheatengine-mcp-bridge/
├── MCP_Server/                   # Оригинальный MCP-сервер (Named Pipe)
├── AI_Context/                   # Оригинальная документация
├── luasocket-remote/             # ЭТОТ ПРОЕКТ — LuaSocket TCP расширение
│   ├── mcp_cheatengine_remote.py # Python MCP-сервер — подключается к CE по TCP
│   ├── ce_mcp_bridge_remote.lua  # Lua TCP-мост — загружается в Cheat Engine
│   ├── requirements.txt          # Зависимости Python (mcp>=1.0.0)
│   ├── luasocket-ce-deploy/      # Установка LuaSocket в CE в один клик
│   │   ├── deploy.py             # Автоопределение CE, версии Lua, установка DLL
│   │   ├── prebuilt/             # Готовые DLL LuaSocket (Lua 5.1/5.3/5.4, x64)
│   │   ├── lua/                  # Чистые Lua-модули
│   │   └── src/                  # Исходный код LuaSocket 3.1.0
│   ├── README.md                 # Документация на английском
│   ├── README_CN.md              # Документация на китайском
│   └── README_RU.md              # Этот файл
├── README.md                     # Оригинальный README
└── LICENSE                       # MIT
```

## Быстрый старт

### Требования

- **Удалённый Windows-сервер** с установленным [Cheat Engine 7.x](https://www.cheatengine.org/)
- **Локальная машина** с Python 3.10+ (любая ОС, Windows — проще всего)
- Сетевая связь между машинами

### Шаг 1: Установка LuaSocket в Cheat Engine

В составе Cheat Engine **нет** библиотеки `socket`. Она необходима для TCP-моста. На удалённом Windows-сервере:

```powershell
cd luasocket-remote/luasocket-ce-deploy
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"
```

Скрипт автоматически определит версию Lua, подберёт подходящую готовую DLL и скопирует все файлы в правильные папки. Используйте `--dry-run` для предпросмотра.

### Шаг 2: Загрузка моста в Cheat Engine

На удалённом Windows-сервере откройте Cheat Engine:

1. Присоединитесь к целевому процессу (или пусть это сделает AI-агент позже)
2. `File` → `Execute Script` → выберите `luasocket-remote/ce_mcp_bridge_remote.lua` → `Execute`

Вы должны увидеть: `[MCP v12.0.0] TCP Server listening on 0.0.0.0:9999`

### Шаг 3: Запуск Python MCP-сервера

На локальной машине:

```bash
pip install -r luasocket-remote/requirements.txt

# Подключение к удалённому серверу CE
python luasocket-remote/mcp_cheatengine_remote.py --host 192.168.1.100 --port 9999
```

Аргументы командной строки:

| Аргумент | По умолчанию | Описание |
|----------|-------------|----------|
| `--host` | `127.0.0.1` | IP или имя хоста CE-сервера |
| `--port` | `9999` | TCP-порт (должен совпадать с Lua-стороной) |

### Шаг 4: Настройка AI-клиента

Направьте ваш MCP-совместимый AI-клиент (Claude Code, Codex и др.) на `luasocket-remote/mcp_cheatengine_remote.py`.

**Claude Code / Claude Desktop** — добавьте в `.mcp.json`:

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

**Codex (OpenAI)** — добавьте в `.codex.toml`:

```toml
[mcp_servers.cheatengine]
command = "python"
args = ['C:\\path\\to\\cheatengine-mcp-bridge\\mcp_cheatengine_remote.py', '--host', '192.168.1.100', '--port', '9999']
```

Перезапустите AI-клиент и проверьте соединение инструментом `ping` — он должен вернуть версию моста.

## Доступные MCP-инструменты

Мост предоставляет ~180 инструментов, сгруппированных по категориям (все унаследованы от оригинального проекта):

| Категория | Примеры инструментов | Описание |
|-----------|---------------------|----------|
| Процесс | `attach_process`, `detach_process`, `get_process_info`, `get_pid`, `get_arch` | Управление целевым процессом |
| Память | `read_memory`, `write_memory`, `read_pointer`, `read_string`, `find_bytes` | Чтение/запись/сканирование памяти |
| Модули | `enum_modules`, `get_module_info`, `find_symbol` | Перечисление модулей |
| Точки останова | `set_breakpoint`, `remove_breakpoint`, `list_breakpoints`, `get_breakpoint_hits` | Аппаратные точки останова |
| DBVM | `start_dbvm_watch`, `stop_dbvm_watch`, `list_dbvm_watches`, `get_dbvm_stats` | Трассировка на уровне гипервизора |
| Ассемблер | `assemble`, `disassemble`, `get_instruction_info` | x86/x64 ассемблер |
| Регистры | `get_registers`, `set_register`, `get_stack` | Проверка регистров и стека |
| Внедрение кода | `allocate_memory`, `inject_dll`, `create_thread`, `call_function` | Удалённое выполнение кода |
| GUI | `get_control_list`, `click_control`, `send_key`, `get_foreground_window` | Автоматизация интерфейса CE |
| Cheat Table | `load_cheat_table`, `activate_entry`, `get_entry_list` | Управление Cheat Table |
| Shell | `run_command`, `shell_execute` | Выполнение команд (по умолчанию отключено) |

Полный справочник API см. в `AI_Context/MCP_Bridge_Command_Reference.md` оригинального проекта.

## Безопасность

- TCP-мост по умолчанию слушает `0.0.0.0` — рекомендуется ограничить доступ через брандмауэр Windows до конкретного IP
- Канал TCP не имеет аутентификации или шифрования. Используйте в доверенной сети или VPN
- Инструменты выполнения команд (`run_command`, `shell_execute`) отключены по умолчанию; включите через `CE_MCP_ALLOW_SHELL=1`
- Для защиты от античитов используйте аппаратные точки останова (DR0–DR3) и DBVM-наблюдение вместо программных (`0xCC`)
- Настройки CE → Extra → отключите «Query memory region routines» во избежание BSOD при DBVM-сканировании

## Устранение неполадок

### "LuaSocket is not installed"

Запустите `deploy.py` (см. Шаг 1). CE не поставляется с LuaSocket.

### "Connection refused" или таймаут

- Убедитесь, что Lua-скрипт загружен в CE и выводит `TCP Server listening on 0.0.0.0:9999`
- Проверьте, что брандмауэр Windows разрешает входящие соединения на TCP-порт 9999
- Используйте `nmap -p 9999 <удалённый-ip>` для проверки доступности порта
- Если nmap показывает `closed`, возможно Lua-скрипт привязался только к IPv6 — `ce_mcp_bridge_remote.lua` использует `tcp4()` для предотвращения этой проблемы

### Периодические разрывы соединения

TCP-поток использует 60-секундный таймаут чтения. При разрыве Python-клиент автоматически переподключается при следующем запросе.

### Ошибка доступа при запуске deploy.py

Папка `C:\Program Files\` защищена UAC. Правый клик по PowerShell → Запуск от имени администратора.

## Сборка из исходников

Если ваш CE использует версию Lua, отсутствующую среди готовых сборок, или у вас 32-разрядный CE:

См. `luasocket-remote/luasocket-ce-deploy/README.md` → Building from Source. Требуется Visual Studio с рабочей нагрузкой C++ и исходный код Lua соответствующей версии.

## Благодарности и лицензия

MIT — см. файл [LICENSE](LICENSE).

Оригинальный проект: [cheatengine-mcp-bridge](https://github.com/miscusi-peek/cheatengine-mcp-bridge) v12.0.0, автор miscusi-peek (лицензия MIT). Этот форк глубоко обязан этому проекту — архитектура моста, все 180 обработчиков MCP-инструментов и потокобезопасная интеграция с CE полностью взяты из оригинала.

Библиотека LuaSocket 3.1.0 — Copyright (C) 2004-2022 Diego Nehab, используется по лицензии MIT.
