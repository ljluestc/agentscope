import sys
import types
import importlib.util
from pathlib import Path
import pytest

# Provide a lightweight stub for shortuuid used by the library in tests
if "shortuuid" not in sys.modules:
    sys.modules["shortuuid"] = types.SimpleNamespace(uuid=lambda: "test-id")

# Manually wire only the modules needed to avoid importing the whole package
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
PKG = SRC / "agentscope"

# Create minimal package stubs
if "agentscope" not in sys.modules:
    pkg = types.ModuleType("agentscope")
    pkg.__path__ = [str(PKG)]
    sys.modules["agentscope"] = pkg
for sub in ["agent", "message", "module", "types"]:
    name = f"agentscope.{sub}"
    if name not in sys.modules:
        mod = types.ModuleType(name)
        mod.__path__ = [str(PKG / sub)]
        sys.modules[name] = mod

def _load_module(mod_name: str, file_path: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(mod_name, str(file_path))
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module

# Load lightweight dependencies
_load_module("agentscope.types", PKG / "types" / "__init__.py")
_load_module("agentscope._logging", PKG / "_logging.py")
_load_module("agentscope.module", PKG / "module" / "__init__.py")
_load_module("agentscope.message", PKG / "message" / "__init__.py")

# Finally load the target module
agent_base_mod = _load_module(
    "agentscope.agent._agent_base",
    PKG / "agent" / "_agent_base.py",
)

from agentscope.message import Msg, ThinkingBlock, TextBlock  # type: ignore
AgentBase = agent_base_mod.AgentBase  # type: ignore


@pytest.mark.asyncio
async def test_stream_print_mixed_thinking_and_text(capsys) -> None:
    agent = AgentBase()
    agent.set_console_output_enabled(True)

    name = "Bot"
    fixed_id = "fixed-msg-id"

    # Chunk 1: thinking only
    msg1 = Msg(
        name=name,
        content=[ThinkingBlock(type="thinking", thinking="A")],
        role="assistant",
    )
    msg1.id = fixed_id
    await agent.print(msg1, last=False)

    # Chunk 2: thinking grows and text starts
    msg2 = Msg(
        name=name,
        content=[
            ThinkingBlock(type="thinking", thinking="AB"),
            TextBlock(type="text", text="x"),
        ],
        role="assistant",
    )
    msg2.id = fixed_id
    await agent.print(msg2, last=False)

    # Chunk 3: text grows; thinking stable
    msg3 = Msg(
        name=name,
        content=[
            ThinkingBlock(type="thinking", thinking="AB"),
            TextBlock(type="text", text="xy"),
        ],
        role="assistant",
    )
    msg3.id = fixed_id
    await agent.print(msg3, last=True)

    out = capsys.readouterr().out
    assert out == "Bot(thinking): AB\nBot: xy\n"

