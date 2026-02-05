# V17 SEMA TANIMI - TEK KAYNAK (SINGLE SOURCE OF TRUTH)
# Bu dosya degistirilemez, sutun eklenemez, cikartilamaz.

V17_COLUMNS = [
    "Date",             # ISO Format (UTC)
    "Symbol",           # "AVAXUSDT"
    "Tier",             # "SILVER", "GOLD", "DIAMOND" (veya Tier-S mapping)
    "Score",            # float 0.0 - 1.0
    
    # STRUCTURAL DNA
    "ADX",              # float
    "ATR_Norm",         # float (ATR / Close)
    "Ang_Price",        # float (Price Angle)
    "Ang_EMA",          # float (EMA Angle)
    "Dist_EMA",         # float (Distance to EMA)
    "Wick_Ratio",       # float
    
    # ENERGY & MOMENTUM
    "Vrsi",             # float (Volume RSI)
    "V-Mom",            # float (Volume Momentum)
    "Vol_Ratio",        # float
    "Volt_Ratio",       # float (Volatility Ratio)
    "Energy_Gap",       # float
    
    # TRIGGER (15M)
    "Micro_Trig",       # boolean (True/False)
    "Ignition_Type",    # string ("NONE" handled as string)
    "M15_RSI",          # float
    "M15_Vol",          # float
    
    # VALIDATION / AUDIT / LABEL
    "Max_Excursion",    # float (Label)
    "Close_Excursion",  # float (Label)
    "Drawdown",         # float (Label)
    "Hit_10",           # "YES"/"NO" (Label)
    "Anti_Penalty",     # float
    "Drift_Factor",     # float
    "Audit_Verdict"     # "ONY"/"RED"
]

# ZORUNLU TIPLER
COLUMN_TYPES = {
    "Date": "object", # string
    "Symbol": "object",
    "Tier": "object",
    "Score": "float64",
    "ADX": "float64",
    "ATR_Norm": "float64",
    "Ang_Price": "float64",
    "Ang_EMA": "float64",
    "Dist_EMA": "float64",
    "Wick_Ratio": "float64",
    "Vrsi": "float64",
    "V-Mom": "float64",
    "Vol_Ratio": "float64",
    "Volt_Ratio": "float64",
    "Energy_Gap": "float64",
    "Micro_Trig": "bool",
    "Ignition_Type": "object",
    "M15_RSI": "float64",
    "M15_Vol": "float64",
    "Max_Excursion": "float64",
    "Close_Excursion": "float64",
    "Drawdown": "float64",
    "Hit_10": "object",
    "Anti_Penalty": "float64",
    "Drift_Factor": "float64",
    "Audit_Verdict": "object"
}
