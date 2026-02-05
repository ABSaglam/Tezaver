---
description: List recent signals in the Standard Format
---

# 📋 Universal Standard Lister

This workflow runs the `universal_lister_standard.py` script to generate a report of recent market signals using the official Standard Format.

## Steps

1. Run the standard lister for the last 3 days (default):
// turbo
```bash
python3 scripts/universal_lister_standard.py --days 3
```

## Options

To list a specific date range, you can run the script manually:
```bash
python3 scripts/universal_lister_standard.py --start 2026-01-20 --end 2026-01-25
```
