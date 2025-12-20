"""
MX-22001: Matrix Agent CLI

Console entrypoint for running Matrix Agent.
"""

import argparse
from tezaver.platform.agents.matrix_agent import MatrixAgent, MatrixAgentConfig
from tezaver.platform.agents.base import run_agent_server


def main():
    parser = argparse.ArgumentParser(
        prog="tezaver-matrix-agent",
        description="Run Matrix Agent for V4 import/sniper/war/approve workflows"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9002, help="Port to listen (default: 9002)")
    parser.add_argument("--token", default="", help="Auth token for API")
    parser.add_argument("--bus", default=".tezaver_bus", help="Bus root path (default: .tezaver_bus)")
    parser.add_argument("--home", default=".tezaver_matrix", help="Matrix home path (default: .tezaver_matrix)")
    parser.add_argument("--allow-stubs", action="store_true", help="Allow stub fallbacks (default: False)")
    
    args = parser.parse_args()
    
    config = MatrixAgentConfig(
        agent_name="matrix",
        bus_root=args.bus,
        token=args.token,
        host=args.host,
        port=args.port,
        matrix_home=args.home,
        allow_stubs=args.allow_stubs,
    )
    
    agent = MatrixAgent(config)
    print(f"Starting Matrix Agent on {args.host}:{args.port}")
    print(f"Bus root: {args.bus}")
    print(f"Matrix home: {args.home}")
    print(f"Allow stubs: {args.allow_stubs}")
    run_agent_server(agent)


if __name__ == "__main__":
    main()
