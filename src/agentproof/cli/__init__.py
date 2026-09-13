"""CLI package for AgentProof."""

__all__ = ["main"]


def main():
    from agentproof.cli.main import main as _main
    return _main()
