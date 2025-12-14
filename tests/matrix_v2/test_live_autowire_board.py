# Matrix Live Autowire Tests
"""
Tests for Live Autowire functionality.
"""

import pytest


class TestLiveAutowire:
    """Tests for build_live_cluster_from_profile_board."""
    
    def test_build_live_cluster_from_profile_board_creates_cells(self):
        """build_live_cluster_from_profile_board should create cells for LIVE profiles."""
        from tezaver.matrix.live.live_cluster import build_live_cluster_from_profile_board
        from tezaver.matrix.profile_board import build_profile_board
        
        # Get LIVE eligible rows
        rows = build_profile_board()
        live_rows = [r for r in rows if r.live_eligible]
        
        # Should have at least BTC and ETH
        assert len(live_rows) >= 2
        
        # Build cluster
        cluster = build_live_cluster_from_profile_board(
            initial_capital=100.0,
            risk_mode="contract",
        )
        
        # Get cluster cells
        cells = cluster.list_cells()
        cell_keys = {(c.symbol, c.timeframe, c.profile_id) for c in cells}
        
        # All LIVE eligible profiles should be in cluster
        for row in live_rows:
            assert (row.symbol, row.timeframe, row.profile_id) in cell_keys
    
    def test_cluster_has_btc_and_eth_cells(self):
        """Cluster should include BTC and ETH Silver 15m profiles."""
        from tezaver.matrix.live.live_cluster import build_live_cluster_from_profile_board
        
        cluster = build_live_cluster_from_profile_board()
        cells = cluster.list_cells()
        cell_keys = {(c.symbol, c.timeframe, c.profile_id) for c in cells}
        
        assert ("BTCUSDT", "15m", "BTC_SILVER_15M_CORE_V1") in cell_keys
        assert ("ETHUSDT", "15m", "ETH_SILVER_15M_CORE_V1") in cell_keys
    
    def test_cluster_excludes_experimental_profiles(self):
        """Cluster should NOT include EXPERIMENTAL profiles like SOL."""
        from tezaver.matrix.live.live_cluster import build_live_cluster_from_profile_board
        
        cluster = build_live_cluster_from_profile_board()
        cells = cluster.list_cells()
        cell_keys = {(c.symbol, c.timeframe, c.profile_id) for c in cells}
        
        # SOL is EXPERIMENTAL, should NOT be in LIVE cluster
        assert ("SOLUSDT", "15m", "SOL_SILVER_15M_CORE_V1") not in cell_keys
