"""
MX-26001: tezaver-smoke CLI

One-command system smoke test.
TR: Tek komutla sistem duman testi + rapor (PASS/FAIL)

Usage:
    tezaver-smoke --bus .tezaver_bus
    tezaver-smoke --help
"""

import argparse
import json
import os
import time
import uuid
from typing import Dict, Any, List
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


def request_with_timeout(url: str, token: str = "", timeout: float = 5.0) -> Dict:
    """HTTP GET with timeout."""
    try:
        req = Request(url)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urlopen(req, timeout=timeout) as resp:
            return {"ok": True, "data": json.loads(resp.read().decode())}
    except HTTPError as e:
        return {"ok": False, "error": f"HTTP_{e.code}"}
    except URLError as e:
        return {"ok": False, "error": str(e.reason)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def post_scan(url: str, token: str = "", timeout: float = 5.0) -> bool:
    """POST to scan inbox."""
    try:
        req = Request(f"{url}/control/scan_inbox", method="POST")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        with urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except:
        return False


def run_smoke(
    bus_root: str,
    mac_url: str,
    matrix_url: str,
    cloud_url: str,
    mac_token: str = "",
    matrix_token: str = "",
    cloud_token: str = "",
    activate: bool = False,
) -> Dict[str, Any]:
    """
    Run smoke test.
    TR: Duman testi çalıştır.
    """
    from tezaver.version import __version__, build_commit
    from tezaver.platform.bus.adapter import create_bus_adapter
    from tezaver.platform.cli.bus_backup_cli import run_backup
    
    checks = []
    artifacts = {}
    overall = "PASS"
    
    bus = create_bus_adapter(bus_root)
    
    # -------------------------------------------------------------------------
    # 1. Health Check
    # -------------------------------------------------------------------------
    health_ok = True
    health_details = []
    
    for name, url, token in [
        ("mac", mac_url, mac_token),
        ("matrix", matrix_url, matrix_token),
        ("cloud", cloud_url, cloud_token),
    ]:
        result = request_with_timeout(f"{url}/health", token)
        if result["ok"]:
            api_ver = result["data"].get("api_version", "?")
            health_details.append(f"{name}: OK (api_v{api_ver})")
        else:
            health_ok = False
            health_details.append(f"{name}: FAIL ({result.get('error', '?')})")
            
    checks.append({
        "name": "health",
        "ok": health_ok,
        "details_tr": "; ".join(health_details),
    })
    
    if not health_ok:
        overall = "FAIL"
        
    # -------------------------------------------------------------------------
    # 2. Golden Flow (headless)
    # -------------------------------------------------------------------------
    golden_ok = True
    golden_steps = []
    
    if health_ok:
        try:
            # Step 1: MAC_BUILD_CANDIDATE
            job_id = f"smoke_{uuid.uuid4().hex[:8]}"
            job = {
                "job_id": job_id,
                "job_type": "MAC_BUILD_CANDIDATE",
                "target": "mac",
                "payload": {"symbol": "BTCUSDT", "timeframe": "15m"},
                "created_at": int(time.time()),
                "priority": 50,
            }
            bus.put_json(f"jobs/mac/inbox/{job_id}.json", job)
            post_scan(mac_url, mac_token)
            time.sleep(0.5)
            
            # Check result
            result = bus.get_json(f"jobs/mac/outbox/{job_id}.json")
            if result and result.get("result", {}).get("ok"):
                candidate_path = result["result"].get("artifact_path")
                artifacts["candidate_path"] = candidate_path
                golden_steps.append("MAC_BUILD_CANDIDATE: OK")
            else:
                golden_ok = False
                golden_steps.append("MAC_BUILD_CANDIDATE: FAIL")
                
            # Step 2: MATRIX_IMPORT_CANDIDATE
            if golden_ok and candidate_path:
                job_id = f"smoke_{uuid.uuid4().hex[:8]}"
                job = {
                    "job_id": job_id,
                    "job_type": "MATRIX_IMPORT_CANDIDATE",
                    "target": "matrix",
                    "payload": {"artifact_path": candidate_path},
                    "created_at": int(time.time()),
                    "priority": 50,
                }
                bus.put_json(f"jobs/matrix/inbox/{job_id}.json", job)
                post_scan(matrix_url, matrix_token)
                time.sleep(0.5)
                
                result = bus.get_json(f"jobs/matrix/outbox/{job_id}.json")
                if result and result.get("result", {}).get("ok"):
                    candidate_id = result["result"].get("candidate_id")
                    artifacts["candidate_id"] = candidate_id
                    golden_steps.append("MATRIX_IMPORT_CANDIDATE: OK")
                else:
                    golden_ok = False
                    golden_steps.append("MATRIX_IMPORT_CANDIDATE: FAIL")
                    
            # Step 3: MATRIX_RUN_SNIPER
            if golden_ok and artifacts.get("candidate_id"):
                job_id = f"smoke_{uuid.uuid4().hex[:8]}"
                job = {
                    "job_id": job_id,
                    "job_type": "MATRIX_RUN_SNIPER",
                    "target": "matrix",
                    "payload": {"candidate_id": artifacts["candidate_id"]},
                    "created_at": int(time.time()),
                    "priority": 50,
                }
                bus.put_json(f"jobs/matrix/inbox/{job_id}.json", job)
                post_scan(matrix_url, matrix_token)
                time.sleep(0.5)
                
                result = bus.get_json(f"jobs/matrix/outbox/{job_id}.json")
                if result and result.get("result", {}).get("ok"):
                    golden_steps.append("MATRIX_RUN_SNIPER: OK")
                else:
                    golden_ok = False
                    golden_steps.append("MATRIX_RUN_SNIPER: FAIL")
                    
            # Step 4: MATRIX_APPROVE_EXPORT
            if golden_ok:
                job_id = f"smoke_{uuid.uuid4().hex[:8]}"
                job = {
                    "job_id": job_id,
                    "job_type": "MATRIX_APPROVE_EXPORT",
                    "target": "matrix",
                    "payload": {"candidate_id": artifacts.get("candidate_id", "")},
                    "created_at": int(time.time()),
                    "priority": 50,
                }
                bus.put_json(f"jobs/matrix/inbox/{job_id}.json", job)
                post_scan(matrix_url, matrix_token)
                time.sleep(0.5)
                
                result = bus.get_json(f"jobs/matrix/outbox/{job_id}.json")
                if result and result.get("result", {}).get("ok"):
                    export_path = result["result"].get("export_path")
                    artifacts["export_path"] = export_path
                    golden_steps.append("MATRIX_APPROVE_EXPORT: OK")
                else:
                    golden_ok = False
                    golden_steps.append("MATRIX_APPROVE_EXPORT: FAIL")
                    
            # Step 5: CLOUD_IMPORT_STRATEGY
            if golden_ok and artifacts.get("export_path"):
                job_id = f"smoke_{uuid.uuid4().hex[:8]}"
                job = {
                    "job_id": job_id,
                    "job_type": "CLOUD_IMPORT_STRATEGY",
                    "target": "cloud",
                    "payload": {"export_path": artifacts["export_path"]},
                    "created_at": int(time.time()),
                    "priority": 50,
                }
                bus.put_json(f"jobs/cloud/inbox/{job_id}.json", job)
                post_scan(cloud_url, cloud_token)
                time.sleep(0.5)
                
                result = bus.get_json(f"jobs/cloud/outbox/{job_id}.json")
                if result and result.get("result", {}).get("ok"):
                    strategy_id = result["result"].get("strategy_id")
                    artifacts["strategy_id"] = strategy_id
                    golden_steps.append("CLOUD_IMPORT_STRATEGY: OK")
                else:
                    golden_ok = False
                    golden_steps.append("CLOUD_IMPORT_STRATEGY: FAIL")
                    
            # Step 6: CLOUD_RUNTIME_TICK
            if golden_ok:
                job_id = f"smoke_{uuid.uuid4().hex[:8]}"
                job = {
                    "job_id": job_id,
                    "job_type": "CLOUD_RUNTIME_TICK",
                    "target": "cloud",
                    "payload": {"ticks": 2},
                    "created_at": int(time.time()),
                    "priority": 50,
                }
                bus.put_json(f"jobs/cloud/inbox/{job_id}.json", job)
                post_scan(cloud_url, cloud_token)
                time.sleep(0.5)
                
                result = bus.get_json(f"jobs/cloud/outbox/{job_id}.json")
                if result and result.get("result", {}).get("ok"):
                    golden_steps.append("CLOUD_RUNTIME_TICK: OK")
                else:
                    golden_ok = False
                    golden_steps.append("CLOUD_RUNTIME_TICK: FAIL")
                    
        except Exception as e:
            golden_ok = False
            golden_steps.append(f"EXCEPTION: {str(e)}")
            
    checks.append({
        "name": "golden",
        "ok": golden_ok,
        "details_tr": "; ".join(golden_steps) if golden_steps else "skipped",
    })
    
    if not golden_ok:
        overall = "FAIL"
        
    # -------------------------------------------------------------------------
    # 3. Backup
    # -------------------------------------------------------------------------
    ts = int(time.time())
    if bus_root.startswith("s3://"):
        backup_path = f"smoke_reports/SMOKE_{ts}.manifest.json"
    else:
        backup_path = f"smoke_reports/SMOKE_{ts}.backup.zip"
        
    backup_result = run_backup(bus_root, backup_path)
    
    checks.append({
        "name": "backup",
        "ok": backup_result["ok"],
        "details_tr": f"Yedek: {backup_result.get('output_path', 'N/A')}",
        "path": backup_result.get("output_path"),
    })
    
    # -------------------------------------------------------------------------
    # Build Report
    # -------------------------------------------------------------------------
    report = {
        "overall": overall,
        "tezaver_version": __version__,
        "commit": build_commit(),
        "smoke_ts": ts,
        "checks": checks,
        "artifacts": artifacts,
    }
    
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Tezaver Smoke Test - Tek komutla sistem duman testi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  tezaver-smoke --bus .tezaver_bus
  tezaver-smoke --bus .tezaver_bus --mac-token TOKEN --matrix-token TOKEN --cloud-token TOKEN
  
TR: Bu araç, tüm agentları ve golden flow'u test eder, sonucu JSON olarak raporlar.
"""
    )
    parser.add_argument("--bus", default=".tezaver_bus", help="Bus path (FS veya S3)")
    parser.add_argument("--mac-url", default="http://127.0.0.1:9001", help="Mac agent URL")
    parser.add_argument("--matrix-url", default="http://127.0.0.1:9002", help="Matrix agent URL")
    parser.add_argument("--cloud-url", default="http://127.0.0.1:9003", help="Cloud agent URL")
    parser.add_argument("--mac-token", default="", help="Mac agent token")
    parser.add_argument("--matrix-token", default="", help="Matrix agent token")
    parser.add_argument("--cloud-token", default="", help="Cloud agent token")
    parser.add_argument("--activate", action="store_true", help="Activate strategy after deploy")
    parser.add_argument("--out", default="", help="Output JSON path (default: smoke_reports/SMOKE_<ts>.json)")
    
    args = parser.parse_args()
    
    report = run_smoke(
        bus_root=args.bus,
        mac_url=args.mac_url,
        matrix_url=args.matrix_url,
        cloud_url=args.cloud_url,
        mac_token=args.mac_token,
        matrix_token=args.matrix_token,
        cloud_token=args.cloud_token,
        activate=args.activate,
    )
    
    # Write report
    ts = report["smoke_ts"]
    out_path = args.out or f"smoke_reports/SMOKE_{ts}.json"
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    # Print summary
    overall = report["overall"]
    icon = "✅" if overall == "PASS" else "❌"
    print(f"\n{icon} Smoke Test: {overall}")
    print(f"   Version: {report['tezaver_version']} ({report['commit']})")
    print(f"   Report: {out_path}")
    
    for check in report["checks"]:
        check_icon = "✓" if check["ok"] else "✗"
        print(f"   {check_icon} {check['name']}: {check['details_tr'][:60]}")
        
    # Exit code
    exit(0 if overall == "PASS" else 1)


if __name__ == "__main__":
    main()
