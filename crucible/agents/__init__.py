"""Agent registry. `make_agent("claude:sonnet")` is how the CLI names one."""

from .baselines import EagerAgent, NoopAgent, OracleAgent


def make_agent(spec: str):
    spec = spec.strip()
    if spec == "oracle":
        return OracleAgent()
    if spec == "noop":
        return NoopAgent()
    if spec == "eager":
        return EagerAgent()
    if spec.startswith("claude"):
        from .claude_agent import ClaudeAgent

        parts = spec.split(":")
        model = parts[1] if len(parts) > 1 and parts[1] else "sonnet"
        effort = parts[2] if len(parts) > 2 else None
        return ClaudeAgent(model=model, effort=effort)
    raise ValueError(
        f"unknown agent {spec!r}. Try: oracle, noop, eager, claude:sonnet, claude:opus, claude:haiku"
    )


BASELINES = ["oracle", "noop", "eager"]
