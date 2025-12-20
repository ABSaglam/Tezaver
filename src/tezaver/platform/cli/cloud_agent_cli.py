"""
MX-22001: Cloud Agent CLI

Console entrypoint for running Cloud Agent.
"""

import argparse
from tezaver.platform.agents.cloud_agent import CloudAgent, CloudAgentConfig
from tezaver.platform.agents.base import run_agent_server


def main():
    parser = argparse.ArgumentParser(
        prog="tezaver-cloud-agent",
        description="Run Cloud Agent for strategy import/tick/pause/resume"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9003, help="Port to listen (default: 9003)")
    parser.add_argument("--token", default="", help="Auth token for API")
    parser.add_argument("--bus", default=".tezaver_bus", help="Bus root path (default: .tezaver_bus)")
    parser.add_argument("--home", default=".tezaver_matrix", help="Cloud home path (default: .tezaver_matrix)")
    
    args = parser.parse_args()
    
    config = CloudAgentConfig(
        agent_name="cloud",
        bus_root=args.bus,
        token=args.token,
        host=args.host,
        port=args.port,
        cloud_home=args.home,
    )
    
    agent = CloudAgent(config)
    print(f"Starting Cloud Agent on {args.host}:{args.port}")
    print(f"Bus root: {args.bus}")
    print(f"Cloud home: {args.home}")
    run_agent_server(agent)


if __name__ == "__main__":
    main()
