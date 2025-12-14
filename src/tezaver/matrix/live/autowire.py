# Matrix Live Autowire
"""
CLI for auto-building Live cluster from Strategy Board.
"""

from tezaver.matrix.live.live_cluster import build_live_cluster_from_profile_board
from tezaver.matrix.profile_board import build_profile_board, print_profile_board


def main() -> None:
    """CLI entry point for Live autowire."""
    # Build profile board
    rows = build_profile_board()
    
    # Build cluster from LIVE eligible profiles
    cluster = build_live_cluster_from_profile_board(
        initial_capital=100.0,
        risk_mode="contract",
    )
    
    # Print header
    print("=" * 100)
    print("Matrix Live Autowire v1 – From Strategy Board")
    print("=" * 100)
    print()
    
    # Print strategy board table
    print_profile_board(rows)
    
    # Print live cell count
    print()
    live_count = sum(1 for r in rows if r.live_eligible)
    print(f"Live Cluster: {live_count} cells ready for LIVE trading")
    
    # List cells in cluster
    cells = cluster.list_cells()
    for cell in cells:
        print(f"  ✓ {cell.symbol} {cell.timeframe} {cell.profile_id}")


if __name__ == "__main__":
    main()
