# Исправления MCP DipTrace (по мотивам 0.4.0)

Источник: тег `v0.4.0` (codeload). Патч: `../mcp-diptrace-fixes.patch`
(5 файлов, ~10 КБ). Готовые файлы лежат прямо в `src/` и `tests/`.

## 1. `place_builtin_component` падал в Windows-бандле

**Симптом**

```
diptrace_mcp_server.exe: error: unrecognized arguments: _library_export_worker ...
HeadlessGuiError: library export worker exited with code 2 without a result
```

**Причина.** `headless_gui._entry_argv()` в замороженной сборке запускает
`[sys.executable, subcommand, ...]`, то есть сам сервер. Но бандл разделён на два
exe: `diptrace_mcp_server.exe` (только MCP-сервер) и
`tools/diptrace_mcp_headless_gui/diptrace_mcp_headless_gui.exe` (воркер с
подкомандами `_worker`, `_library_export_worker`, `_probe`). Сервер не понимает
скрытые подкоманды, падает с кодом 2, результат воркера не появляется.

**Исправление** (`src/diptrace_mcp/headless_gui.py`)

* новая функция `_frozen_worker_executable()`: переменная окружения
  `DIPTRACE_MCP_HEADLESS_GUI` → соседний `tools/diptrace_mcp_headless_gui/
  diptrace_mcp_headless_gui.exe` → `diptrace_mcp_headless_gui.exe` рядом →
  `sys.executable` (сборки «всё в одном exe»);
* `_entry_argv()` использует найденный воркер;
* сообщения об ошибке воркера теперь содержат команду, которой он запускался.

Путь соответствует тому, что создаёт `scripts/build_windows_server.ps1`
(`dist/windows-server/diptrace_mcp_server/tools/diptrace_mcp_headless_gui/…`).

## 2. Сервер умирал на символах вне cp1251

**Симптом**

```
File "diptrace_mcp\server_runtime.py", line 2934, in forward_output
File "encodings\cp1251.py", line 19, in encode
UnicodeEncodeError: 'charmap' codec can't encode character '\u03a9'
```

Любой ответ с `Ω` (значения каталога вида `10kΩ`) убивал процесс: `rc=3221225477`.

**Причина.** MCP stdio — это UTF-8, но `sys.stdout` в замороженном консольном
приложении кодирует текст кодовой страницей ANSI (cp1251 на русской Windows).
`PYTHONUTF8`/`PYTHONIOENCODING` не помогают: PyInstaller инициализирует
интерпретатор изолированно и переменные игнорирует.

**Исправление**

* новый модуль `src/diptrace_mcp/stdio_transport.py` с `write_payload()`:
  пишет уже закодированные UTF-8 байты в `stream.buffer` (текстовый поток —
  только как запасной путь);
* `server_runtime.forward_output()` использует `write_payload()`;
* `server_runtime.main()` вызывает `_force_utf8_stdio()` (reconfigure stdout и
  stderr в UTF-8), чтобы и логи не падали на непечатаемых для cp1251 символах.

## Тесты

* `tests/test_stdio_transport.py` — UTF-8 поверх cp1251-потока, ровно один
  перевод строки, запрет `\n` в payload, текстовый fallback;
* `tests/test_headless_gui.py` — три новых случая: воркер из бандла, переопределение
  через переменную окружения, откат на `sys.executable`.

Локальная проверка (без pytest, тем же кодом, что в тестах):

```
PASS frozen uses bundled worker
PASS env override wins
PASS fallback to running binary
PASS python mode keeps -m
PASS cp1251 stream carries UTF-8 bytes
PASS text-only fallback
PASS trailing newline rejected
```

## Второй коммит: устойчивость и диагностика

3. **`services/builtin_library.py`: выбор компонента по имени, а не по индексу.**
   `library_index` из SQLite-каталога использовался как позиция в XML-экспорте
   библиотеки. После обновления `.eli` позиции могут съехать, и тогда либо
   `catalog index is outside the exported library`, либо — хуже — в схему
   попадёт чужой символ (проверка имени это ловила, но падала). Теперь имя из
   каталога ищется по всем компонентам экспорта, индекс остаётся подсказкой,
   а расхождение даёт сообщение с ожидаемым и фактическим именем.

4. **`error_boundary.py`: `OSError` больше не теряет причину.**
   Раньше ответ был просто `A filesystem or external-tool operation failed`
   с пустыми `details` — по нему нельзя было отличить «нет доступа» от «нет
   файла». Теперь в `details` попадают `errno` и `strerror`. Имя файла
   намеренно **не** добавляется: контракт запрещает утечку путей
   (`/tmp/fixture-secret/` проверяется тестом).

5. **`headless_gui._write_json`: ошибки записи воркерного JSON оборачиваются
   в `HeadlessGuiError` с путём.** Именно этот путь давал `PermissionError`
   при недоступном `TEMP`, а наружу выходило `INTERNAL_ERROR` без деталей.

## Сознательно не менял

* **`place_part` с несуществующим `ComponentStyle`.** Проверка «стиль есть в
  документе» ломает собственные тесты проекта (`test_schematic_authoring`
  ставит `CompType0`/`CompType9` в документ без библиотеки, а
  `test_semantic_compiler` — в синтетическую схему). То есть текущая
  терпимость — часть контракта, а не недосмотр. Если её ужесточать, это
  отдельное решение мейнтейнера (например, предупреждение в `warnings`
  вместо ошибки, с обновлением ожиданий в тестах).
* **Описание поля `pin` (0-based индекс).** Схемы инструментов зафиксированы в
  `reference/mcp-tools-list.snapshot.json`, и добавление `description`
  меняет публичный контракт; без перегенерации снапшота тесты парности
  упадут. Это правка контракта, а не бага.

## Что осталось

* Установленный бандл (`%LOCALAPPDATA%\Programs\DipTraceMCP`) — это готовые exe;
  правки в исходниках на него не влияют, нужна пересборка:
  `scripts/build_windows_server.ps1` (нужны Python 3.10+, PyInstaller 6.14.2 и
  зависимости из `pyproject.toml`).
* Наблюдение, которое я **не** менял: `place_part` принимает
  `component_style`, которого нет в документе, и создаёт деталь со «висячей»
  ссылкой. DipTrace потом ругается `component type … is not in the file`.
  Это осознанная свобода инструмента (стиль может появиться в том же
  транзакционном пакете), но проверку на существование `ComponentStyle`
  в библиотеке документа стоит обсудить отдельно.
