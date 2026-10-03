"""Agent loop test on a plain host python (no UNO, no LibreOffice).

Fake provider returns scripted turns (tool calls, then final text); fake
tools module records execution. Covers: the happy 2-step loop, argument
passing (raw JSON), tool error feedback into the next request, the step
budget (forced summary), and non-tools provider rejection.
Run: python3 tests/test_agent.py  ->  "agent OK"
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "src", "extension", "Scripts",
                                "python", "pythonpath"))

from lo_ai import agent as agent_mod  # noqa: E402


class Turn(object):
    def __init__(self, content=None, calls=()):
        self.content = content
        self.tool_calls = list(calls)

    has_tool_calls = property(lambda self: bool(self.tool_calls))


class FakeProvider(object):
    name = "fake (scripted)"
    supports_tools = True

    def __init__(self, turns):
        self.turns = list(turns)
        self.requests = []

    def chat_with_tools(self, messages, tools, cancel=None):
        self.requests.append({"messages": [dict(m) for m in messages],
                              "tools": [dict(t) for t in (tools or [])]})
        return self.turns.pop(0)


class FakeTools(object):
    """execute() records calls and returns canned results."""

    def __init__(self, results):
        self.results = dict(results)
        self.ran = []

    def specs_for_app(self, app):
        return [{"name": n, "description": "d", "parameters":
                 {"type": "object", "properties": {}}}
                for n in self.results]

    def execute(self, model, app, name, args):
        self.ran.append((name, args))
        raw = self.results[name]
        if isinstance(raw, Exception):
            raise raw
        return raw


def call(name, args, cid="c1"):
    return {"id": cid, "name": name, "args": json.dumps(args)}


def test_happy_loop():
    tools = FakeTools({"read_range": "A1:B2 | 1 | 2",
                       "write_range": "Wrote 1 rows x 2 cols"})
    provider = FakeProvider([
        Turn(calls=[call("read_range", {"range": "A1:B2"}, "c1")]),
        Turn(calls=[call("write_range",
                         {"range": "D1:E1", "values": [["x", 5]]}, "c2")]),
        Turn(content="Done: wrote the row."),
    ])
    steps = []
    answer = agent_mod.run_agent(
        model=object(), provider=provider, user_message="do it",
        history=[{"role": "user", "content": "earlier"},
                 {"role": "assistant", "content": "ok"}],
        on_step=steps.append, max_steps=5, app="calc",
        tools=tools, run_on_main=lambda fn: (True, fn()))
    assert answer == "Done: wrote the row.", answer
    # args reach execute() as the RAW json string — parsing is execute()'s job
    assert tools.ran == [("read_range", json.dumps({"range": "A1:B2"})),
                         ("write_range", json.dumps(
                             {"range": "D1:E1", "values": [["x", 5]]}))], \
        tools.ran
    assert len(steps) == 2 and steps[0].startswith("read_range("), steps
    # messages: system + 2 history + user + assistant(tool) + tool + ...
    first = provider.requests[0]
    assert first["messages"][0]["role"] == "system"
    assert "Calc" in first["messages"][0]["content"]
    last = provider.requests[-1]
    tool_msgs = [m for m in last["messages"] if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2"]
    assert "A1:B2 | 1 | 2" in tool_msgs[0]["content"]
    echoed = [m for m in last["messages"] if m["role"] == "assistant"
              and "tool_calls" in m]
    assert echoed and echoed[0]["tool_calls"][0]["function"]["name"] == "read_range"
    # specs passed to the provider
    assert {t["name"] for t in provider.requests[0]["tools"]} >= \
        {"read_range", "write_range"}


def test_tool_error_fed_back():
    # real document_tools.execute never raises — it returns "ERROR: ..." text
    tools = FakeTools({"read_range": "ERROR: no sheet named 'X'; available: "
                                     "Data, Report"})
    provider = FakeProvider([
        Turn(calls=[call("read_range", {"sheet": "X", "range": "A1:A2"})]),
        Turn(content="Fixed."),
    ])
    answer = agent_mod.run_agent(
        model=object(), provider=provider, user_message="go",
        history=[], on_step=None, max_steps=4, app="calc",
        tools=tools, run_on_main=lambda fn: (True, fn()))
    assert answer == "Fixed."
    last = provider.requests[-1]
    tool_msg = [m for m in last["messages"] if m["role"] == "tool"][0]
    assert "no sheet named" in tool_msg["content"], tool_msg


def test_step_budget_forces_summary():
    # exactly max_steps tool turns, then the forced no-tools summary call
    provider = FakeProvider(
        [Turn(calls=[call("read_range", {"range": "A1:B1"}, "c%d" % i)])
         for i in range(3)] + [Turn(content="summary")])
    tools = FakeTools({"read_range": "data"})
    answer = agent_mod.run_agent(
        model=object(), provider=provider, user_message="go",
        history=[], on_step=None, max_steps=3, app="calc",
        tools=tools, run_on_main=lambda fn: (True, fn()))
    assert answer == "summary"
    # after the budget: a no-tools request with the "Stop using tools" note
    assert provider.requests[-1]["tools"] == []
    assert any("Stop using tools" in m.get("content", "")
               for m in provider.requests[-1]["messages"])


def test_unsupported_provider_rejected():
    class P(object):
        name = "plain"
        supports_tools = False

        def chat_with_tools(self, *a, **k):
            raise AssertionError("must not be called")

    try:
        agent_mod.run_agent(model=object(), provider=P(), user_message="x",
                            history=[], on_step=None, max_steps=3,
                            app="calc", tools=FakeTools({"t": "r"}),
                            run_on_main=None)
    except RuntimeError as exc:
        assert "does not support" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_crashing_tool_reported():
    tools = FakeTools({"read_range": "ok"})
    provider = FakeProvider([Turn(calls=[call("read_range", {})]),
                             Turn(content="done")])
    answer = agent_mod.run_agent(
        model=object(), provider=provider, user_message="go",
        history=[], on_step=None, max_steps=3, app="calc",
        tools=tools, run_on_main=lambda fn: (False, ZeroDivisionError("boom")))
    assert answer == "done"
    tool_msg = [m for m in provider.requests[-1]["messages"]
                if m["role"] == "tool"][0]
    assert "tool crashed" in tool_msg["content"] and "boom" in tool_msg["content"]


if __name__ == "__main__":
    test_happy_loop()
    test_tool_error_fed_back()
    test_step_budget_forces_summary()
    test_unsupported_provider_rejected()
    test_crashing_tool_reported()
    print("agent OK")
