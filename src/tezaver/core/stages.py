"""
Matrix Certification Stages
---------------------------
Core constants defining the lifecycle stages of a bundle/candidate in the Matrix system.
Decoupled from 'sniper' or 'legacy' components.
"""

# Initial stage when a bundle is first discovered/imported
STAGE_CANDIDATE = "CANDIDATE"

# Stage after passing single-asset backtest (formerly Sniper)
# Kept as SNIPER_PASSED for backwards compatibility with existing db/json records
STAGE_SNIPER_PASSED = "SNIPER_PASSED"

# Stage after passing multi-asset/live checks
STAGE_LIVE_CERTIFIED = "LIVE_CERTIFIED"

# Stage when a bundle/candidate fails validation or is manually demoted
STAGE_DEMOTED = "DEMOTED"
