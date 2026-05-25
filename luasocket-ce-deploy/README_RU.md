# LuaSocket CE — Инструмент развёртывания

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.6+](https://img.shields.io/badge/python-3.6+-blue.svg)](https://www.python.org/)

*Установка LuaSocket в Cheat Engine в один клик — автоопределение версии Lua, подбор готовых DLL, копирование в правильные папки.*

[English Documentation](README.md) | [中文文档](README_CN.md)

## Что это такое?

В состав [Cheat Engine](https://www.cheatengine.org/) входит движок Lua, но в нём отсутствуют библиотеки `socket` и `mime` (LuaSocket). Из-за этого скрипты удалённой отладки по TCP/HTTP не работают «из коробки».

Данный инструмент **автоматизирует все шаги**:

- Автоматически находит установленную копию CE
- Определяет, какую версию Lua использует CE (5.1 / 5.3 / 5.4)
- Подбирает соответствующую предкомпилированную DLL LuaSocket
- Копирует `.lua`-модули и `.dll`-файлы в правильные каталоги
- Проверяет корректность после установки

## Быстрый старт

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/YOURNAME/luasocket-ce-deploy.git
cd luasocket-ce-deploy

# 2. Запустите скрипт развёртывания
python deploy.py

# Или сразу укажите путь к CE
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"

# Режим предпросмотра (файлы не записываются)
python deploy.py --dry-run
```

**Требования:** Python 3.6+. Сторонние пакеты не нужны.

## Аргументы командной строки

| Аргумент | Описание |
|----------|----------|
| `--ce PATH` | Путь к корневой папке Cheat Engine |
| `--force` | Пропустить все запросы подтверждения |
| `--dry-run` | Показать, что будет сделано; файлы не менять |
| `--check-only` | Только проверка окружения, без установки |
| `--list-prebuilt` | Вывести список готовых сборок и выйти |

## Таблица совместимости

| Cheat Engine | Версия Lua | Имя DLL | Статус |
|-------------|------------|---------|--------|
| CE 6.x | Lua 5.1 | `lua51-64.dll` | Готовая сборка ✓ |
| CE 7.0 – 7.4 | Lua 5.3 | `lua53-64.dll` | Готовая сборка ✓ |
| CE 7.5+ | Lua 5.4 | `lua54-64.dll` | Готовая сборка ✓ |

Все готовые DLL — **x86-64 (64-разрядные)**, собраны в Visual Studio 2026 (MSVC 19.50).

## Структура проекта

```
luasocket-ce-deploy/
├── deploy.py                    # Главный скрипт развёртывания
├── prebuilt/                    # Готовые DLL
│   ├── lua51/
│   │   ├── socket/core.dll
│   │   └── mime/core.dll
│   ├── lua53/
│   │   ├── socket/core.dll
│   │   └── mime/core.dll
│   └── lua54/
│       ├── socket/core.dll
│       └── mime/core.dll
├── lua/                         # Lua-модули (чистый Lua)
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
├── src/                         # Исходный код LuaSocket 3.1.0 (C)
├── README.md
├── README_CN.md
└── README_RU.md
```

## Как это работает

1. **Поиск CE** — сканирует типичные пути (`C:\Program Files\Cheat Engine*`, реестр, путь, указанный пользователем)
2. **Определение версии Lua** — читает имена файлов `lua*-64.dll` в папке CE (например, `lua53-64.dll` → Lua 5.3)
3. **Подбор готовой сборки** — выбирает нужный `core.dll` из каталога `prebuilt/`
4. **Копирование** — Lua-модули помещаются в `CE\lua\`, нативные DLL — в `CE\socket\core.dll` и `CE\mime\core.dll`
5. **Проверка** — убеждается, что развёрнутые DLL ссылаются на правильную Lua DLL

> **Важно:** CE ищет `.lua`-файлы в папке `CE\lua\`, но `.dll`-файлы ищет прямо в корне CE. Поэтому DLL кладутся в `CE\socket\core.dll`, а **не** в `CE\lua\socket\core.dll`.

## Проверка установки

Откройте Lua Engine в CE (`Ctrl+Alt+L`) и выполните:

```lua
print(require("socket")._VERSION)  --> LuaSocket 3.1.0
print(require("mime")._VERSION)    --> MIME 1.0.3

-- Быстрая проверка TCP
local http = require("socket.http")
local body, code = http.request("http://httpbin.org/get")
print(code, #body)
```

## Устранение неполадок

### "Не найден указанный модуль" (The specified module could not be found)

DLL LuaSocket была собрана под другое имя Lua DLL, чем то, что используется в CE.

**Решение:** выполните `python deploy.py --check-only` для проверки определённой версии Lua. Проверьте, какие файлы `lua*-64.dll` есть в папке CE.

### "module 'socket.core' not found"

DLL находится в неправильной папке.

**Правильная структура:**
```
C:\Program Files\Cheat Engine\
├── lua\
│   └── socket.lua     ← .lua-файлы ЗДЕСЬ
├── socket\
│   └── core.dll       ← .dll-файлы ЗДЕСЬ (в корне CE)
└── mime\
    └── core.dll
```

### Доступ запрещён (Permission Denied)

Папка `C:\Program Files\` защищена UAC. Запустите скрипт от имени администратора:

```powershell
# Правый клик по PowerShell → Запуск от имени администратора
python deploy.py --ce "C:\Program Files\Cheat Engine 7.5"
```

### Ложное срабатывание антивируса

Защитник Windows может пометить `core.dll` из-за ссылки на `ws2_32.dll` (сокеты Windows). Добавьте папку CE в исключения антивируса.

## Сборка из исходников

Если ваш CE использует версию Lua, которой нет среди готовых сборок, или у вас 32-разрядный CE:

### Необходимые компоненты

- Visual Studio 2022/2025/2026 с рабочей нагрузкой «Разработка классических приложений на C++»
- Или Visual Studio Build Tools
- Исходный код Lua, соответствующий версии в вашем CE ([lua.org/ftp](https://www.lua.org/ftp/))

### Шаги

```bash
# 1. Сборка Lua DLL с именем, принятым в CE (пример: Lua 5.3)
cl /MD /O2 /c /DLUA_BUILD_AS_DLL l*.c
link /DLL /OUT:lua53-64.dll /IMPLIB:lua53-64.lib *.obj

# 2. Сборка luasocket с линковкой на Lua DLL от CE
cl /MD /O2 /c /DLUASOCKET_API=__declspec(dllexport) wsocket.c auxiliar.c ...
link /DLL /OUT:socket\core.dll *.obj lua53-64.lib ws2_32.lib

# 3. Сборка mime
cl /MD /O2 /c /DMIME_API=__declspec(dllexport) mime.c compat.c
link /DLL /OUT:mime\core.dll *.obj lua53-64.lib
```

## Почему CE переименовывает Lua DLL

Cheat Engine поставляется с переименованной Lua DLL (`lua53-64.dll` вместо `lua53.dll`), потому что в одной папке лежат одновременно 32- и 64-битные версии Lua. Суффикс `-64` предотвращает конфликт имён. Любой нативный Lua-модуль должен быть прилинкован именно к этому имени DLL — данный инструмент делает это автоматически.

## Лицензия

MIT — см. файл [LICENSE](LICENSE).

Библиотека LuaSocket 3.1.0 — Copyright (C) 2004-2022 Diego Nehab, используется по лицензии MIT.
