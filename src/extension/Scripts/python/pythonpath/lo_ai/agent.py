"""Agent loop: the model inspects and edits the live document via tools.

run_agent() runs on a worker thread; every UNO call goes through
run_on_main (panel passes pump.call) so document access stays on the
LibreOffice main thread. Host tests inject a fake tools module and an
inline run_on_main, keeping the whole loop testable without UNO.
"""

MAX_STEPS = 12

_SYSTEM_TEMPLATE = """You are an expert assistant working INSIDE the user's LibreOffice %(app)s document. You can inspect and modify the live document through tools.

Rules:
- Inspect before you modify: call %(probe)s first to learn the real layout (sheet names, used ranges, headings).
- Make minimal, targeted edits. For calculations prefer writing spreadsheet formulas over hardcoding computed numbers.
- After an important write, verify by reading the range back.
- Charts: create_chart with types column, bar, line, pie, area, scatter. Pivot (summary) tables: create_pivot with row/col/data fields.
- Every edit is applied immediately; the user can undo with Ctrl+Z. Do not ask for permission — just do what was asked.
- If a tool returns ERROR, fix the arguments and retry (max 2 retries per problem).
- When the task is done, stop calling tools and write a short final answer in the user's language summarizing what you changed.
- Never invent document content: what you have not read with tools, you do not know."""

_PROBE = {"calc": "calc_info and read_range", "writer": "writer_info and read_document"}


def agent_system_prompt(app):
    app_name = {"calc": "Calc (spreadsheet)", "writer": "Writer (text)"}.get(
        app, app)
    return _SYSTEM_TEMPLATE % {"app": app_name,
                               "probe": _PROBE.get(app, "list/read tools")}


def _tool_call_message(turn):
    """Assistant message echoing the requested tool calls (OpenAI shape)."""
    return {"role": "assistant",
            "content": turn.content or "",
            "tool_calls": [{"id": c["id"], "type": "function",
                            "function": {"name": c["name"],
                                         "arguments": c["args"]}}
                           for c in turn.tool_calls]}


def _short_args(args, limit=80):
    s = " ".join(str(args).split())
    return s if len(s) <= limit else s[:limit - 1] + "…"


def run_agent(model, provider, user_message, history, on_step,
              cancel=None, max_steps=MAX_STEPS, app="other",
              tools=None, run_on_main=None):
    """Run the tool loop; returns the final assistant text.

    tools    — module with specs_for_app/execute (default document_tools);
    run_on_main(fn) -> (ok, value) — dispatch for UNO calls; None = inline.
    """
    if tools is None:
        from . import document_tools as tools
    if not getattr(provider, "supports_tools", False):
        raise RuntimeError("provider %s does not support tool calling"
                           % provider.name)
    specs = tools.specs_for_app(app)
    if not specs:
        raise RuntimeError("no tools for document type %r" % app)

    messages = [{"role": "system", "content": agent_system_prompt(app)}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": user_message})

    for _step in range(max(1, int(max_steps))):
        turn = provider.chat_with_tools(messages, specs, cancel=cancel)
        if not turn.has_tool_calls:
            return (turn.content or "").strip()
        messages.append(_tool_call_message(turn))
        for call in turn.tool_calls:
            if on_step:
                on_step("%s(%s)" % (call["name"],
                                    _short_args(call["args"])))
            if run_on_main is not None:
                ok, result = run_on_main(
                    lambda c=call: tools.execute(model, app, c["name"],
                                                 c["args"]))
            else:
                try:
                    ok, result = True, tools.execute(model, app,
                                                     call["name"],
                                                     call["args"])
                except Exception as exc:
                    ok, result = False, exc
            if not ok:
                result = "ERROR: tool crashed: %r" % (result,)
            messages.append({"role": "tool", "tool_call_id": call["id"],
                             "content": str(result)})

    # Step budget exhausted: force a text answer without tools.
    messages.append({"role": "user",
                     "content": "Stop using tools. Summarize briefly in the "
                                "user's language what has been done so far."})
    turn = provider.chat_with_tools(messages, None, cancel=cancel)
    return (turn.content or "").strip()
