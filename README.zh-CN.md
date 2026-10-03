<div align="center">
  <h1>AI Assistant for LibreOffice</h1>
  <p><strong>可访问文档的 AI 智能体：读取、编辑文档，构建图表和数据透视表</strong></p>
</div>

**语言：** [Русский](README.md) · [English](README.en.md) · 中文（简体）（主）

<div align="center">

[![⚠ 模型会看到文档中的个人信息——发送前请先脱敏](https://img.shields.io/badge/⚠_模型会看到文档中的个人信息-发送前请先脱敏-c0392b?style=for-the-badge)](https://iustitia.tech/incognito/)

</div>

> **⚠️ 隐私。** 在“操作文档（智能体）”模式下以及启用文档上下文时，文档内容（文本、
> 单元格、选区）会被发送到所选的 AI 服务商——也就是说，模型**会看到文档中包含的
> 个人信息**。如果文档中含有个人数据，请提前进行脱敏处理。快捷方式：
> **[Incognito Web](https://iustitia.tech/incognito/demo/)**（浏览器中直接使用，无需
> 安装）或 **[Incognito Desktop](https://iustitia.tech/incognito/)**（适合日常使用）——
> [iustitia.tech/incognito](https://iustitia.tech/incognito/)。

<div align="center">

![版本](https://img.shields.io/badge/版本-1.13.0-2f8f8b?style=flat-square)
![许可](https://img.shields.io/badge/许可-MIT-a6784f?style=flat-square)
![Python](https://img.shields.io/badge/Python-LO内置-1d2324?style=flat-square&logo=python&logoColor=f4efe6)
![LibreOffice](https://img.shields.io/badge/LibreOffice-26.8-185abd?style=flat-square&logo=libreoffice&logoColor=ffffff)
![平台](https://img.shields.io/badge/Linux%20%7C%20Windows%20%7C%20macOS-x86__64-1d2324?style=flat-square&logo=linux&logoColor=f4efe6)

</div>

适用于 LibreOffice（Writer、Calc、Impress、Draw）的 AI 助手，以 `.oxt` 扩展形式发布。
与普通的“聊天插件”不同，该智能体**能自行查看文档内容并自行编辑文档**：读取单元格
区域和文档文本、写入公式、构建图表、生成数据透视表——只需用自然语言提出请求。

> 已在以下环境测试：**Linux (Fedora)、LibreOffice 26.8.1.1 (flatpak)**。支持在
> Windows 和 macOS 上安装（见[安装](#安装)），但尚未在这些系统上验证。

---

## 目录

- [这是什么](#这是什么)
- [功能](#功能)
- [智能体及其工具](#智能体及其工具)
- [服务商](#服务商)
- [安装](#安装)
- [快速上手](#快速上手)
- [安全](#安全)
- [开发](#开发)
- [限制](#限制)
- [许可](#许可)

## 这是什么

LibreOffice 内的浮动聊天面板。在基础模式下，它是带流式输出和文本快捷操作的普通
AI 聊天。勾选 **“操作文档（智能体）”** 后，助手变为智能体：模型通过工具自行查看
文档、做出修改并检查结果——无需手动把文本复制到聊天框。

## 功能

- **带工具的智能体**（Writer 和 Calc）：读取并编辑实时文档，每个步骤都显示在聊天中。
- **11 个快捷操作**：聊天、改进文本、语法与拼写、摘要、翻译（目标语言可设置）、
  解释、续写、精简、扩写、正式文风、项目符号列表。
- **结果写入文档**：“插入”（光标处）、“替换”（选区）、“复制”。
- **流式输出**和“停止”按钮；对话历史（8 轮，可配置）。
- **17 个服务商预设** + 任意自定义 endpoint；从服务器获取实时模型列表
  （Refresh 按钮，连接测试成功后自动加载）。
- **面板窗口**：可用鼠标拖拽边缘/角落调整大小（原生，由操作系统处理），面板停靠在
  LibreOffice 右侧栏上方，并跟随办公软件窗口。
- **界面语言**：俄语 / 英语 / 中文（按本地语言自动检测，可通过 config.json 中的
  `"ui_lang": "ru|en|zh"` 手动指定）。
- 仅使用 Python 标准库（无 pip 依赖）——运行在 LibreOffice 内置的 Python 上。

## 智能体及其工具

“操作文档”复选框启用智能体循环：模型获得一组工具并自行决定调用什么；每次调用的
结果都会返回给模型，直到任务完成（最多 12 步，可通过 `agent_max_steps` 配置）。

**Calc** 中的工具：

| 工具 | 作用 |
|---|---|
| `calc_info` | 工作簿的工作表及其已用区域 |
| `read_range` | 读取单元格值（可选公式） |
| `write_range` | 将值数组写入区域 |
| `set_formula` | 向单元格/区域写入公式 |
| `sort_range` | 按一个或多个键排序 |
| `format_range` | 加粗/斜体、背景与字体颜色、数字格式 |
| `create_chart` | 图表：柱形、条形、折线、饼图、面积、散点 |
| `create_pivot` | 数据透视（合并分析）表：行/列/数据字段，sum、count、average、min、max 聚合 |
| `find_replace` | 在工作表或整个工作簿中查找替换 |

**Writer** 中的工具：文档统计、读取全文和选区、替换选区、在光标处插入、全文查找替换。

每次编辑都是普通的 LibreOffice 操作，可通过 **Ctrl+Z** 撤销。如果模型参数出错，会
收到错误文本并自行修正。

## 服务商

| 服务商 | API 风格 | 获取密钥 |
|---|---|---|
| **Z.ai Coding Plan (GLM)** — 已在实战中验证 | OpenAI | [z.ai/manage-apikey](https://z.ai/manage-apikey/apikey-list) |
| Z.ai Open Platform | OpenAI | 同上 |
| **Anthropic Claude** | Messages | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| **OpenAI (GPT)** | OpenAI | [platform.openai.com](https://platform.openai.com/api-keys) |
| **OpenAI Codex** | Responses | 同上 |
| Google Gemini | OpenAI 层 | [aistudio.google.com](https://aistudio.google.com/apikey) |
| OpenRouter、DeepSeek、Mistral、Groq、xAI、Together、Fireworks、Perplexity | OpenAI | 各服务商控制台 |
| Ollama、LM Studio（本地，无需密钥） | OpenAI | — |
| Custom | OpenAI | 任意兼容 endpoint |

全部 17 个预设均通过连接测试（各自使用对应的 API 风格，针对本地 API 模拟服务：
`tests/test_providers.py`）。对于 OpenAI 推理模型（`o1/o3/o4`、`gpt-5*`），扩展会
自动去掉 `temperature` 并改用 `max_completion_tokens`。

智能体模式需要支持 function calling 的服务商——即所有 OpenAI 兼容风格（17 个预设
中的 14 个，包括 Z.ai GLM）。Claude 和 Codex 目前以普通聊天模式运行（这些风格的
工具支持在计划中）。

## 安装

三种系统上的安装方式相同——通过扩展管理器：

1. 下载 `dist/sphaera-lo-ai-assistant.oxt`（或自行构建：`./build.sh`）。
2. LibreOffice → **工具 ▸ 扩展管理器… ▸ 添加** → 选择文件。
3. 完全重启 LibreOffice——出现 **AI 助手** 菜单和工具栏按钮。

Linux 上还有辅助脚本：`./install.sh`（支持 flatpak 安装；安装期间 LibreOffice 必须
关闭）。

要求：LibreOffice 已安装 Python 脚本支持（Windows、macOS 和 Linux 的标准安装程序
默认启用）。

## 快速上手

1. **AI 助手 ▸ 设置…**：选择预设——地址和模型自动填入 → 粘贴 API 密钥 →
   **Test connection** → **Save**。
2. **AI 助手 ▸ 打开面板…** —— 面板停靠在办公窗口右侧栏位置（也可拖动边缘放到
   方便的地方）。
3. 提问或选择操作。勾选“操作文档”后，智能体会自行读取和编辑文档：“根据 B:D 列
   构建图表”、“按经理汇总销售数据透视表”、“改进第二段”。

## 安全

API 密钥**仅保存在本地**，存于权限为 `0600` 的 JSON 配置中（LibreOffice 配置文件
内的 `…/user/config/lo-ai-assistant/config.json`；办公软件之外——
`$APPDATA/lo-ai-assistant` 或 `$XDG_CONFIG_HOME/lo-ai-assistant`）。密钥只会发送到
您选择的 API 服务商。切勿将配置提交到 git。

**关于个人信息** —— 见页面顶部的警告：在智能体模式下以及启用文档上下文时，文档
内容会发送到您选择的 AI 服务商。处理包含个人数据的文档前请先脱敏——例如使用
[Incognito Web](https://iustitia.tech/incognito/demo/) 或
[Incognito Desktop](https://iustitia.tech/incognito/)。

## 开发

```bash
python3 tests/test_providers.py   # 适配器、配置、提示词 + 全部预设的连接测试
python3 tests/test_agent.py       # 智能体循环（主机 python，无需 LO）
python3 tests/test_static.py      # 静态检查
./build.sh && ./install.sh        # 构建 .oxt + 安装 (Linux)
```

```
src/extension/
├── Addons.xcu                     # 菜单和工具栏按钮（service: 分发）
├── Scripts/python/ai_assistant_entry.py   # python 组件 (XJobExecutor) + 宏
├── Scripts/python/pythonpath/lo_ai/
│   ├── agent.py                   # 智能体循环（模型 + 工具）
│   ├── document_tools.py          # 15 个操作实时文档的工具 (UNO)
│   ├── document_bridge.py         # Writer/Calc/Impress/Draw 的文档上下文
│   ├── assistant.py               # 提示词、操作、历史
│   ├── config.py, i18n.py, http_client.py, uno_env.py
│   ├── providers/                 # 17 个预设；openai_compat / anthropic / responses
│   └── ui/                        # 面板、设置、主线程泵
└── Dialogs/, icons/
tests/  test_providers.py · test_agent.py · test_static.py · mock_server.py · wait_and_install.sh
tools/  build.py · gen_icons.py
```

## 限制

- 智能体模式（工具）已面向 OpenAI 兼容服务商实现；Anthropic/Codex 以无工具的普通
  聊天运行。
- LibreOffice **flatpak** 中远程 URP 桥接不稳定——这是构建版本的特性；扩展在进程内
  运行，不受影响。
- Impress/Draw 支持基础场景（形状文本的读取/插入）；Calc 级别的工具正在计划中。
- Windows 和 macOS：支持安装，但尚未在真实机器上验证（欢迎提交问题反馈）。

## 许可

MIT —— 见 [LICENSE](LICENSE)。
