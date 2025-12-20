"""
MX-22001: Mac Agent CLI

Console entrypoint for running Mac Agent.
"""

import argparse
from tezaver.platform.agents.mac_agent import MacAgent
from tezaver.platform.agents.base import AgentConfig, run_agent_server


def main():
    parser = argparse.ArgumentParser(
        prog="tezaver-mac-agent",
        description="Run Mac Agent for publishing candidates to bus"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9001, help="Port to listen (default: 9001)")
    parser.add_argument("--token", default="", help="Auth token for API")
    parser.add_argument("--bus", default=".tezaver_bus", help="Bus root path (default: .tezaver_bus)")
    
    args = parser.parse_args()
    
    config = AgentConfig(
        agent_name="mac",
        bus_root=args.bus,
        token=args.token,
        host=args.host,
        port=args.port,
    )
    
    agent = MacAgent(config)
    print(f"Starting Mac Agent on {args.host}:{args.port}")
    print(f"Bus root: {args.bus}")
    run_agent_server(agent)


if __name__ == "__main__":
    main()
