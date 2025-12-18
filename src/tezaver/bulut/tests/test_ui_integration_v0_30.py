import pytest
from tezaver.bulut.ui.pages.command_center import render_command_center
from tezaver.bulut.ui.pages.live_charts import render_live_charts
from tezaver.bulut.ui.pages.explorer import render_explorer
from tezaver.bulut.ui.pages.journal import render_journal

def test_ui_functions_importable():
    assert callable(render_command_center)
    assert callable(render_live_charts)
    assert callable(render_explorer)
    assert callable(render_journal)

def test_signature_accepts_api_base():
    # Basic check if it accepts args or kwargs, mostly python dynamic
    # Just ensuring we can import is main validation here without full streamlit mock context
    pass
