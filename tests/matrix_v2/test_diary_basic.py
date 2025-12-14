# Matrix Diary Tests
"""
Tests for Matrix Diary v1 functionality.
"""

import pytest


class TestDiaryBasic:
    """Basic diary formatting tests."""
    
    def test_format_event_line_tick_start(self):
        """format_event_line should handle TICK_START events."""
        from tezaver.matrix.wargame.diary import format_event_line
        
        evt = {
            "event_type": "TICK_START",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "tick_index": 0,
            "details": {"note": "tick start"},
        }
        
        line = format_event_line(evt)
        assert isinstance(line, str)
        assert len(line) > 0
        assert "TICK_START" in line
        assert "BTCUSDT" in line
    
    def test_format_event_line_signal(self):
        """format_event_line should handle SIGNAL events."""
        from tezaver.matrix.wargame.diary import format_event_line
        
        evt = {
            "event_type": "SIGNAL",
            "symbol": "ETHUSDT",
            "timeframe": "15m",
            "tick_index": 1,
            "details": {
                "signal_count": 2,
                "signals": [{"type": "LONG", "confidence": 0.8}],
            },
        }
        
        line = format_event_line(evt)
        assert "SIGNAL" in line
        assert "count=2" in line
    
    def test_format_event_line_decision_no_trade(self):
        """format_event_line should handle DECISION with no trade."""
        from tezaver.matrix.wargame.diary import format_event_line
        
        evt = {
            "event_type": "DECISION",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "tick_index": 2,
            "details": {"decision": None, "reason": "no_trade"},
        }
        
        line = format_event_line(evt)
        assert "DECISION" in line
        assert "no_trade" in line
    
    def test_format_event_line_execution(self):
        """format_event_line should handle EXECUTION events."""
        from tezaver.matrix.wargame.diary import format_event_line
        
        evt = {
            "event_type": "EXECUTION",
            "symbol": "BTCUSDT",
            "timeframe": "15m",
            "tick_index": 3,
            "details": {"pnl": 1.5, "equity_after": 101.5},
        }
        
        line = format_event_line(evt)
        assert "EXECUTION" in line
        assert "pnl=" in line
        assert "equity_after=" in line
    
    def test_format_event_line_does_not_crash(self):
        """format_event_line should not crash on various event types."""
        from tezaver.matrix.wargame.diary import format_event_line
        
        event_types = [
            "TICK_START", "TICK_END", "SIGNAL", "DECISION",
            "GUARDRAIL_V1", "GUARDRAIL_V2", "EXECUTION", "INFO"
        ]
        
        for etype in event_types:
            evt = {
                "event_type": etype,
                "symbol": "TESTUSDT",
                "timeframe": "1h",
                "tick_index": 0,
                "details": {},
            }
            line = format_event_line(evt)
            assert isinstance(line, str)
            assert len(line) > 0


class TestPrintWargameDiary:
    """Tests for print_wargame_diary function."""
    
    def test_print_wargame_diary_runs(self, capsys):
        """print_wargame_diary should print header and events."""
        from tezaver.matrix.wargame.diary import print_wargame_diary
        from tezaver.matrix.wargame.reports import WargameReport
        
        # Create minimal report with events
        report = WargameReport(
            scenario_id="TEST_SCENARIO",
            profile_id="TEST_PROFILE",
            capital_start=100.0,
            capital_end=105.0,
            trade_count=1,
            win_rate=1.0,
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            events=[
                {
                    "event_type": "TICK_START",
                    "symbol": "BTCUSDT",
                    "timeframe": "15m",
                    "tick_index": 0,
                    "details": {"note": "tick start"},
                },
                {
                    "event_type": "TICK_END",
                    "symbol": "BTCUSDT",
                    "timeframe": "15m",
                    "tick_index": 0,
                    "details": {"note": "tick end"},
                },
            ],
        )
        
        print_wargame_diary(report)
        
        captured = capsys.readouterr()
        assert "Matrix Diary v1" in captured.out
        assert "TEST_PROFILE" in captured.out
        assert "100.00" in captured.out
        assert "105.00" in captured.out
    
    def test_print_wargame_diary_empty_events(self, capsys):
        """print_wargame_diary should handle empty events."""
        from tezaver.matrix.wargame.diary import print_wargame_diary
        from tezaver.matrix.wargame.reports import WargameReport
        
        report = WargameReport(
            scenario_id="TEST",
            profile_id="TEST",
            capital_start=100.0,
            capital_end=100.0,
            trade_count=0,
            win_rate=0.0,
            events=[],
        )
        
        print_wargame_diary(report)
        
        captured = capsys.readouterr()
        assert "Matrix Diary v1" in captured.out
        assert "telemetry event bulunamadı" in captured.out
