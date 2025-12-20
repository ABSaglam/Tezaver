"""
MX-22002: Panel CLI

Console entrypoint for running Tezaver Panel (Streamlit).
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="tezaver-panel",
        description="Run Tezaver Panel UI (Streamlit)"
    )
    parser.add_argument("--port", type=int, default=8501, help="Port to run (default: 8501)")
    parser.add_argument("--host", default="localhost", help="Host (default: localhost)")
    
    args = parser.parse_args()
    
    # Run streamlit programmatically
    try:
        from streamlit.web.cli import main as streamlit_main
        
        # Build streamlit command args
        sys.argv = [
            "streamlit", "run",
            "src/tezaver/ui/main_panel.py",
            "--server.port", str(args.port),
            "--server.address", args.host,
        ]
        
        print(f"Starting Tezaver Panel on {args.host}:{args.port}")
        streamlit_main()
    except ImportError:
        print("Error: streamlit not installed. Run: pip install streamlit")
        sys.exit(1)


if __name__ == "__main__":
    main()
