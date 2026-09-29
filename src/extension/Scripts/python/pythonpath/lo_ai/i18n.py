"""UI localisation: Russian primary, English and Chinese as extras.

Language resolution order (see `lang()`):
  1. config.json "ui_lang" (auto|ru|en|zh)
  2. LibreOffice UI locale (ooLocale)
  3. environment LANG
  4. "ru" (the product's primary language)
"""

import os

_current = {"lang": None}

STRINGS = {
    "ru": {
        "title_panel": "AI-ассистент",
        "title_settings": "AI-ассистент — Настройки",
        "provider": "Провайдер:",
        "model": "Модель:",
        "refresh": "Обновить",
        "settings_btn": "Настройки…",
        "include_context": "Учитывать выделенный текст / контекст документа",
        "action": "Действие:",
        "send": "Отправить",
        "stop": "Стоп",
        "insert": "Вставить",
        "replace": "Заменить",
        "copy": "Копировать",
        "hint_insert": "«Вставить» дописывает в позицию курсора; «Заменить» перезаписывает выделение.",
        "ready": "Готово.",
        "type_first": "Введите сообщение.",
        "choose_model": "Выберите модель в Настройках…",
        "saved": "Настройки сохранены.",
        "saved_title": "Настройки сохранены",
        "inserted": "Вставлено в документ.",
        "cannot_insert": "Сюда вставить нельзя — используйте «Копировать».",
        "insert_failed": "Ошибка вставки: ",
        "copied": "Скопировано в буфер обмена.",
        "copy_failed": "Ошибка копирования: ",
        "done": "Готово · ",
        "chars": " симв.",
        "stopped": " [остановлено]",
        "loading_models": "Загружаю список моделей с сервера…",
        "models_loaded": "Загружено моделей: ",
        "models_empty": "Провайдер вернул пустой список моделей.",
        "models_unavailable": "Список моделей недоступен: ",
        "testing": "Проверяю подключение…",
        "connected": "✔ Подключение установлено. Ответ модели: ",
        "fail": "✘ ОШИБКА: ",
        "base_url_required": "Укажите Base URL провайдера.",
        "preset": "Пресет:",
        "api_style": "API-стиль:",
        "api_key": "API-ключ:",
        "key_hint": "Ключ хранится только локально (файл настроек). Возьмите ключ на сайте провайдера.",
        "temperature": "Температура:",
        "temp_hint": "пусто = не отправлять (нужно для reasoning-моделей o*/gpt-5)",
        "max_tokens": "Макс. токенов:",
        "max_hint": "0/пусто = по умолчанию у провайдера",
        "timeout": "Таймаут, с:",
        "stream": "Потоковый вывод (ответ печатается по мере генерации)",
        "system_prompt": "Системный промпт:",
        "test_connection": "Проверить подключение",
        "save": "Сохранить",
        "cancel": "Отмена",
        "with_context": "   (с контекстом документа)",
        "you": "Вы: ",
        "err_title": "AI-ассистент",
        # действия
        "act_chat": "Чат",
        "act_improve": "Улучшить текст",
        "act_grammar": "Грамматика и орфография",
        "act_summarize": "Сделать выжимку",
        "act_translate": "Перевести",
        "act_explain": "Объяснить",
        "act_continue": "Продолжить текст",
        "act_shorten": "Сократить",
        "act_expand": "Расширить",
        "act_formal": "Официальный стиль",
        "act_bullets": "В маркированный список",
    },
    "en": {
        "title_panel": "AI Assistant",
        "title_settings": "AI Assistant — Settings",
        "provider": "Provider:",
        "model": "Model:",
        "refresh": "Refresh",
        "settings_btn": "Settings…",
        "include_context": "Include selected text / document context",
        "action": "Action:",
        "send": "Send",
        "stop": "Stop",
        "insert": "Insert",
        "replace": "Replace",
        "copy": "Copy",
        "hint_insert": "Insert appends at the cursor; Replace overwrites the selection.",
        "ready": "Ready.",
        "type_first": "Type a message first.",
        "choose_model": "Choose a model in Settings…",
        "saved": "Settings saved.",
        "saved_title": "Settings saved",
        "inserted": "Inserted into the document.",
        "cannot_insert": "Cannot insert here — use Copy.",
        "insert_failed": "Insert failed: ",
        "copied": "Copied to clipboard.",
        "copy_failed": "Copy failed: ",
        "done": "Done · ",
        "chars": " chars",
        "stopped": " [stopped]",
        "loading_models": "Loading model list from the provider…",
        "models_loaded": "Models loaded: ",
        "models_empty": "Provider returned an empty model list.",
        "models_unavailable": "Model list unavailable: ",
        "testing": "Testing connection…",
        "connected": "✔ Connected. Model answered: ",
        "fail": "✘ ERROR: ",
        "base_url_required": "Please provide the provider Base URL.",
        "preset": "Preset:",
        "api_style": "API style:",
        "api_key": "API key:",
        "key_hint": "The key is stored locally only. Get a key at the provider's site.",
        "temperature": "Temperature:",
        "temp_hint": "blank = don't send (required for o*/gpt-5 reasoning models)",
        "max_tokens": "Max tokens:",
        "max_hint": "0/blank = provider default",
        "timeout": "Timeout, s:",
        "stream": "Stream answers (typewriter effect)",
        "system_prompt": "System prompt:",
        "test_connection": "Test connection",
        "save": "Save",
        "cancel": "Cancel",
        "with_context": "   (with document context)",
        "you": "You: ",
        "err_title": "AI Assistant",
        "act_chat": "Chat",
        "act_improve": "Improve text",
        "act_grammar": "Fix grammar & spelling",
        "act_summarize": "Summarize",
        "act_translate": "Translate",
        "act_explain": "Explain",
        "act_continue": "Continue writing",
        "act_shorten": "Make shorter",
        "act_expand": "Expand",
        "act_formal": "Make formal",
        "act_bullets": "Turn into bullet points",
    },
    "zh": {
        "title_panel": "AI 助手",
        "title_settings": "AI 助手 — 设置",
        "provider": "提供商：",
        "model": "模型：",
        "refresh": "刷新",
        "settings_btn": "设置…",
        "include_context": "包含选中文本 / 文档上下文",
        "action": "操作：",
        "send": "发送",
        "stop": "停止",
        "insert": "插入",
        "replace": "替换",
        "copy": "复制",
        "hint_insert": "“插入”在光标处追加；“替换”覆盖所选内容。",
        "ready": "就绪。",
        "type_first": "请先输入消息。",
        "choose_model": "请在设置中选择模型…",
        "saved": "设置已保存。",
        "saved_title": "设置已保存",
        "inserted": "已插入文档。",
        "cannot_insert": "此处无法插入 — 请使用“复制”。",
        "insert_failed": "插入失败：",
        "copied": "已复制到剪贴板。",
        "copy_failed": "复制失败：",
        "done": "完成 · ",
        "chars": " 字符",
        "stopped": " [已停止]",
        "loading_models": "正在从服务器获取模型列表…",
        "models_loaded": "已加载模型数：",
        "models_empty": "提供商返回空模型列表。",
        "models_unavailable": "无法获取模型列表：",
        "testing": "正在测试连接…",
        "connected": "✔ 连接成功。模型回答：",
        "fail": "✘ 错误：",
        "base_url_required": "请填写提供商的 Base URL。",
        "preset": "预设：",
        "api_style": "API 风格：",
        "api_key": "API 密钥：",
        "key_hint": "密钥仅保存在本地配置文件中。请在提供商网站获取。",
        "temperature": "温度：",
        "temp_hint": "留空 = 不发送（o*/gpt-5 推理模型需要）",
        "max_tokens": "最大 token：",
        "max_hint": "0/留空 = 提供商默认值",
        "timeout": "超时（秒）：",
        "stream": "流式输出（逐字显示回答）",
        "system_prompt": "系统提示词：",
        "test_connection": "测试连接",
        "save": "保存",
        "cancel": "取消",
        "with_context": "   （含文档上下文）",
        "you": "你：",
        "err_title": "AI 助手",
        "act_chat": "对话",
        "act_improve": "改进文本",
        "act_grammar": "修正语法拼写",
        "act_summarize": "总结",
        "act_translate": "翻译",
        "act_explain": "解释",
        "act_continue": "续写",
        "act_shorten": "缩短",
        "act_expand": "扩写",
        "act_formal": "正式语气",
        "act_bullets": "转为要点列表",
    },
}


def _detect_lang():
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        v = os.environ.get(var, "")
        if v:
            v = v.split(".")[0].lower()
            if v.startswith("ru"):
                return "ru"
            if v.startswith("zh"):
                return "zh"
            if v.startswith("en"):
                return "en"
    return "ru"


def set_lang(lang, ctx=None, smgr=None):
    """Explicit override: 'ru' | 'en' | 'zh' | 'auto'."""
    if lang in ("ru", "en", "zh"):
        _current["lang"] = lang
        return lang
    # auto: LibreOffice UI locale, then environment
    if ctx is not None and smgr is not None:
        try:
            cp = smgr.createInstanceWithArgumentsAndContext(
                "com.sun.star.configuration.ConfigurationProvider", (), ctx)
            node = cp.createInstanceWithArguments(
                "com.sun.star.configuration.ConfigurationAccess",
                (_mkprop("nodepath", "/org.openoffice.Setup/L10N"),))
            loc = str(node.getPropertyValue("ooLocale")).lower()
            if loc.startswith("ru"):
                _current["lang"] = "ru"
                return "ru"
            if loc.startswith("zh"):
                _current["lang"] = "zh"
                return "zh"
            if loc.startswith("en"):
                _current["lang"] = "en"
                return "en"
        except Exception:
            pass
    _current["lang"] = _detect_lang()
    return _current["lang"]


def _mkprop(name, value):
    import uno
    prop = uno.createUnoStruct("com.sun.star.beans.PropertyValue")
    prop.Name = name
    prop.Value = value
    return prop


def lang():
    return _current.get("lang") or "ru"


def tr(key):
    table = STRINGS.get(lang()) or STRINGS["ru"]
    return table.get(key) or STRINGS["en"].get(key) or key
