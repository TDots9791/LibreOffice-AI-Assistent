# AI Assistant for LibreOffice

Мультипровайдерный AI-ассистент для LibreOffice (Writer, Calc, Impress, Draw) в виде расширения `.oxt`. Работает по API с **Z.ai (GLM Coding Plan)**, **Anthropic Claude**, **OpenAI / Codex**, **Gemini**, **OpenRouter**, **DeepSeek**, **Mistral**, **Groq**, **xAI**, **Together**, **Fireworks**, **Perplexity**, **Ollama / LM Studio (локально)** — и с любым OpenAI-совместимым endpoint (vLLM, LiteLLM, шлюзы).

![version](https://img.shields.io/badge/version-1.0.0-blue) ![platform](https://img.shields.io/badge/platform-Linux%20%7C%20Windows%20%7C%20macOS-lightgrey)

---

## Возможности

- **Панель-чат** (немодальное окно) с потоковым выводом ответа и кнопкой «Стоп».
- **Осведомлённость о документе**: автоматически подхватывает выделенный текст / активную ячейку / текст фигуры или слайда и передаёт модели как контекст.
- **Вставка результата в документ**:
  - Writer — вставка на позицию курсора или замена выделения;
  - Calc — запись в активную ячейку или в выделенный диапазон;
  - Impress / Draw — в выделенную текстовую фигуру (дозапись или замена), иначе — новая текстовая рамка на текущем слайде/странице;
  - остальные модули — кнопка «Копировать» в буфер обмена.
- **Быстрые действия**: Improve, Fix grammar, Summarize, Translate (с выбором языка), Explain, Continue writing, Make shorter, Expand, Make formal, Bullets.
- **16 пресетов провайдеров** + произвольный endpoint; у каждой модели настраиваются base URL, API-стиль, ключ, температура, max tokens, таймаут, системный промпт.
- **Тест подключения** прямо из настроек.
- Только стандартная библиотека Python (никаких pip-зависимостей) — работает со встроенным Python LibreOffice.

## Установка

### Linux (нативный LibreOffice)

```bash
./build.sh     # собирает dist/sphaera-lo-ai-assistant.oxt
./install.sh   # unopkg add (пользовательская установка)
```

### Linux (LibreOffice из Flatpak — как здесь)

```bash
./install.sh   # сам определит flatpak и вызовет unopkg внутри песочницы
```

Удалить: `./install.sh --remove`, либо Менеджер расширений (Tools ▸ Extension Manager).

> **Важно:** во время установки LibreOffice должен быть закрыт — `install.sh` сам проверяет это и откажется работать при запущенном офисе (установка «поверх» работающего экземпляра повреждает реестр расширений). После установки перезапустите LibreOffice.

### Если расширение в списке, но меню не появилось

1. Полностью закройте **все** окна LibreOffice и откройте заново (меню строится при старте).
2. Если не помогло — реестр расширений мог быть повреждён установкой «поверх» запущенного офиса. Лечение (закройте LibreOffice):
   ```bash
   # flatpak:
   rm -rf ~/.var/app/org.libreoffice.LibreOffice/config/libreoffice/4/user/uno_packages/cache
   # нативная установка:
   rm -rf ~/.config/libreoffice/4/user/uno_packages/cache
   ./install.sh   # и снова запустите LibreOffice
   ```
   (Кэш содержит только установленные пользователем расширения — проверьте в Extension Manager, что кроме нашего там нет ваших.)

### Windows / macOS

Соберите пакет (`python3 tools/build.py`) и откройте `dist/sphaera-lo-ai-assistant.oxt` двойным кликом — LibreOffice предложит установить. Скрипты `build.sh`/`install.sh` рассчитаны на bash, но сам `.oxt` платформонезависим.

## Быстрый старт

1. Запустите LibreOffice → **Tools ▸ AI Assistant…** (или кнопка на панели инструментов).
2. При первом запуске откройте **Tools ▸ AI Assistant Settings…** (или «Settings…» в панели):
   - выберите пресет провайдера — base URL и модель подставятся автоматически;
   - вставьте API-ключ;
   - нажмите **Test connection** → **Save**.
3. Пишите в нижнее поле и жмите **Send**. Ответ можно **Insert** (в курсор), **Replace** (заменить выделение) или **Copy**.

### Настройка провайдеров

| Провайдер | Где взять ключ | Endpoint по умолчанию |
|---|---|---|
| **Z.ai Coding Plan (GLM)** | [z.ai/manage-apikey](https://z.ai/manage-apikey/apikey-list) | `https://api.z.ai/api/coding/paas/v4` |
| Z.ai Open Platform | там же | `https://api.z.ai/api/paas/v4` |
| **Anthropic Claude** | [console.anthropic.com](https://console.anthropic.com/settings/keys) | `https://api.anthropic.com/v1` |
| **OpenAI (GPT)** | [platform.openai.com](https://platform.openai.com/api-keys) | `https://api.openai.com/v1` |
| **OpenAI (Codex)** | там же | тот же, но через **Responses API** (`/responses`) — переключается пресетом |
| Google Gemini | [aistudio.google.com](https://aistudio.google.com/apikey) | OpenAI-совместимый слой `…/v1beta/openai` |
| OpenRouter | [openrouter.ai](https://openrouter.ai/keys) | 400+ моделей одним ключом |
| DeepSeek / Mistral / Groq / xAI / Together / Fireworks / Perplexity | консоли провайдеров | см. пресеты |
| Ollama (локально) | ключ не нужен | `http://localhost:11434/v1` |
| LM Studio (локально) | ключ не нужен | `http://localhost:1234/v1` |

**Z.ai Coding Plan**: подписочный ключ (от ~$3/мес) работает именно на `/api/coding/paas/v4`; для pay-per-token используйте пресет «Open Platform» (`/api/paas/v4`). Модели: `glm-4.7`, `glm-4.6`, `glm-4.5-air`, `glm-4.5-flash`.

**Codex**: модели `gpt-5.1-codex-max`, `gpt-5.1-codex`, `gpt-5-codex`, `codex-mini-latest` обслуживаются только через Responses API — пресет «OpenAI (Codex)» включает нужный API-стиль автоматически.

**Заметки по моделям**: имена моделей — редактируемые поля, а не жёсткий список (списки в пресетах актуальны на дату релиза). Для reasoning-моделей OpenAI (`o1/o3/o4`, `gpt-5*`) расширение само убирает `temperature` и шлёт `max_completion_tokens` вместо `max_tokens`.

## Безопасность

API-ключи хранятся **локально** в JSON-конфиге с правами `0600`:

- Flatpak: `~/.var/app/org.libreoffice.LibreOffice/config/libreoffice/4/user/config/lo-ai-assistant/config.json`
- Нативная установка (Linux): `~/.config/libreoffice/4/user/config/lo-ai-assistant/config.json`

Ключи никуда не передаются, кроме выбранного вами API-провайдера. Не коммитьте конфиг в git.

## Архитектура

```
src/extension/
├── ai_assistant_entry.py        # entry-точки Scripting Framework (open_panel, open_settings, тесты)
├── Addons.xcu                   # пункты меню Tools + кнопка тулбара
├── description.xml, META-INF/   # манифест .oxt
└── pythonpath/lo_ai/
    ├── config.py                # JSON-конфиг (без UNO — тестируется вне LO)
    ├── http_client.py           # urllib + SSE-стриминг + отмена (threading.Event)
    ├── uno_env.py               # путь конфига через PathSettings (работает и в flatpak)
    ├── document_bridge.py       # контекст/вставка для Writer/Calc/Impress/Draw
    ├── assistant.py             # промпты, история, быстрые действия
    ├── providers/
    │   ├── presets.py           # 16 пресетов
    │   ├── openai_compat.py     # OpenAI-совместимые (z.ai, Gemini, Groq, …)
    │   ├── anthropic.py         # Claude Messages API
    │   └── openai_responses.py  # Codex через Responses API
    └── ui/                      # UnoControlDialog-панель и настройки, main-thread pump
tests/
├── test_providers.py            # 16 юнит-тестов: адаптеры, отмена, конфиг, промпты
├── mock_server.py               # локальный SSE-мок всех трёх API
├── integration_client.py        # интеграционный тест по URP (для штатных установок)
└── check_port.py, urp_sanity.py
tools/build.py, tools/gen_icons.py   # сборка .oxt и генерация иконок (без PIL)
```

Поток ответов рендерится безопасно: сетевой поток читает фоновый поток, обновления UI уходят через `com.sun.star.awt.AsyncCallback` (фолбэки: `awt.Timer`, затем прямой вызов).

## Разработка

```bash
python3 tests/test_providers.py   # юнит-тесты (хостовый python, без LO)
./build.sh && ./install.sh        # пересборка + переустановка
```

Известные ограничения:

- В LibreOffice 26.8 **flatpak** удалённый URP-мост (`--accept=socket`) нестабилен — это особенность сборки, не расширения: ассистент работает in-process и её не касается. Из-за неё `tests/integration_client.py` в этой среде может не пройти; на нативных установках тест работает.
- Имена скриптов в `Addons.xcu` используют схему `vnd.sun.star.script:sphaera-lo-ai-assistant.oxt|ai_assistant_entry.py$<func>?language=Python&location=user:uno_packages` — имя пакета в имени скрипта, разделитель `|`, location без суффикса. Это рабочая форма современных LibreOffice (проверено по `pythonscript.py` 26.8); старые примеры с `location=user:uno_packages/<имя>.oxt` не работают. Не переименовывайте oxt при пересборке.
- В LO 24.2 была регрессия регистрации python-пакетов в `.oxt` (исправлена в последующих релизах).

## Лицензия

MIT — см. [LICENSE](LICENSE).
