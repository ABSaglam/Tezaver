from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

PORT = 8085

import os
import json
from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore

ROUTES = {
    "/": "UI-A: Home",
    "/candidates": "UI-B: Candidates",
    "/runs": "UI-C: Runs",
    "/engine": "UI-D: Engine",
    "/gates": "UI-E: Gates",
    "/reports": "UI-F: Reports",
    "/evidence": "UI-G: Evidence",
    "/data": "UI-H: Data",
    "/story": "UI-I: Story",
    "/lessons": "UI-J: Lessons",
    "/ai": "UI-K: AI",
    "/ops": "UI-L: Ops",
    "/tests": "UI-M: Tests",
    "/maintenance": "UI-N: Maintenance",
    "/registry": "UI-O: Registry",
    "/alerts": "UI-P: Alerts",
}

class PanelHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.rstrip("/")
        if path == "": path = "/"
        
        # UI-B: Candidates List
        if path == "/candidates":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            store = FileCandidateStore()
            ids = store.list_ids()
            
            list_html = "".join([f'<li><a href="/candidates/{i}">{i}</a></li>' for i in ids])
            if not ids: list_html = "<li>No candidates found. Use 'candidate_importer' to add some.</li>"
            
            html = f"""
            <html>
                <head><title>UI-B: Candidates</title></head>
                <body>
                    <h1>Candidates List</h1>
                    <p><a href="/">Back to Home</a></p>
                    <hr/>
                    <ul>{list_html}</ul>
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-B/I: Candidate Detail / Story
        if path.startswith("/candidates/"):
            cid = path.split("/")[-1]
            store = FileCandidateStore()
            try:
                data = store.load(cid)
                story = data.get('story', {})
                html = f"""
                <html>
                    <head><title>{cid}</title></head>
                    <body>
                        <h1>Candidate: {data.get('symbol')}</h1>
                        <p><a href="/candidates">Back to Candidates</a></p>
                        <pre>ID: {cid}\nTimeframe: {data.get('timeframe')}\nBuild: {data.get('build_ts')}</pre>
                        <hr/>
                        <h2>Story (UI-I)</h2>
                        <h3>Phases</h3>
                        <table border="1">
                            <tr><th>Name</th><th>Start</th><th>End</th></tr>
                            {"".join([f"<tr><td>{p['name']}</td><td>{p['start_bar']}</td><td>{p['end_bar']}</td></tr>" for p in story.get('phases', [])])}
                        </table>
                        <h3>Anchors</h3>
                        <ul>
                            <li>Entry Bar: {story.get('anchors', {}).get('entry_bar')}</li>
                            <li>Invalidation Bar: {story.get('anchors', {}).get('invalidation_bar')}</li>
                        </ul>
                        <hr/>
                        <pre>{json.dumps(data, indent=2)}</pre>
                    </body>
                </html>
                """
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(html.encode("utf-8"))
            except Exception as e:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(f"Error: {e}".encode("utf-8"))
            return

        # UI-H: Data Diagnostics
        if path == "/data":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            home = os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
            latest_path = os.path.join(home, "data_reports", "latest.json")
            
            content = "<h3>No diagnostics yet. Run 'data_doctor' CLI.</h3>"
            
            if os.path.exists(latest_path):
                try:
                    with open(latest_path, "r", encoding="utf-8") as f:
                        rep = json.load(f)
                    
                    status_color = "green" if rep.get("ok") else "red"
                    issues_html = "".join([f"<li>{i}</li>" for i in rep.get("issues", [])]) or "<li>None</li>"
                    
                    content = f"""
                    <h2>Data Quality Report: <span style="color:{status_color}">{ "OK" if rep.get("ok") else "FAIL" }</span></h2>
                    <p>Report ID: {rep.get("report_id")}</p>
                    <table border="1">
                        <tr><td>Timeframe</td><td>{rep.get("timeframe")}</td></tr>
                        <tr><td>Count</td><td>{rep.get("count")}</td></tr>
                        <tr><td>Range</td><td>{rep.get("first_ts")} - {rep.get("last_ts")}</td></tr>
                        <tr><td>Fingerprint</td><td><small>{rep.get("fingerprint")}</small></td></tr>
                    </table>
                    <h3>Stats</h3>
                    <pre>{json.dumps(rep.get("stats"), indent=2)}</pre>
                    <h3>Issues</h3>
                    <ul>{issues_html}</ul>
                    """
                except Exception as e:
                    content = f"<h3>Error loading report: {e}</h3>"
            
            html = f"""
            <html>
                <head><title>UI-H: Data</title></head>
                <body>
                    <h1>Data Diagnostics (UI-H)</h1>
                    <p><a href="/">Back to Home</a></p>
                    <hr/>
                    {content}
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-H: Data Diagnostics
        if path == "/data":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            home = os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
            latest_path = os.path.join(home, "data_reports", "latest.json")
            
            content = "<h3>No diagnostics yet. Run 'data_doctor' CLI.</h3>"
            
            if os.path.exists(latest_path):
                try:
                    with open(latest_path, "r", encoding="utf-8") as f:
                        rep = json.load(f)
                    
                    status_color = "green" if rep.get("ok") else "red"
                    issues_html = "".join([f"<li>{i}</li>" for i in rep.get("issues", [])]) or "<li>None</li>"
                    
                    content = f"""
                    <h2>Data Quality Report: <span style="color:{status_color}">{ "OK" if rep.get("ok") else "FAIL" }</span></h2>
                    <p>Report ID: {rep.get("report_id")}</p>
                    <table border="1">
                        <tr><td>Timeframe</td><td>{rep.get("timeframe")}</td></tr>
                        <tr><td>Count</td><td>{rep.get("count")}</td></tr>
                        <tr><td>Range</td><td>{rep.get("first_ts")} - {rep.get("last_ts")}</td></tr>
                        <tr><td>Fingerprint</td><td><small>{rep.get("fingerprint")}</small></td></tr>
                    </table>
                    <h3>Stats</h3>
                    <pre>{json.dumps(rep.get("stats"), indent=2)}</pre>
                    <h3>Issues</h3>
                    <ul>{issues_html}</ul>
                    """
                except Exception as e:
                    content = f"<h3>Error loading report: {e}</h3>"
            
            html = f"""
            <html>
                <head><title>UI-H: Data</title></head>
                <body>
                    <h1>Data Diagnostics (UI-H)</h1>
                    <p><a href="/">Back to Home</a></p>
                    <hr/>
                    {content}
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-C: Runs List & Demo
        if path == "/runs":
            from tezaver.matrix.adapters.run_store_fs import RunStoreFS
            store = RunStoreFS()
            runs = store.list_runs()
            
            list_html = "".join([f'<li><a href="/runs/{r}">{r}</a></li>' for r in runs])
            
            html = f"""
            <html>
                <head><title>UI-C: Runs</title></head>
                <body>
                    <h1>Runs (UI-C)</h1>
                    <p><a href="/">Back to Home</a> | <b style="color:blue"><a href="/runs/demo">▶ RUN DEMO</a></b></p>
                    <hr/>
                    <ul>{list_html}</ul>
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # Run Demo Logic
        if path == "/runs/demo":
            from tezaver.matrix.core.cycle_engine import run_cycle
            from tezaver.matrix.core.trace import TraceIds
            from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig
            from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
            
            # Adapters
            from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
            from tezaver.matrix.adapters.broker_sim import SimBroker
            from tezaver.matrix.adapters.store_run_fs import FileRunStore
            
            # 1. Load a candidate
            c_store = FileCandidateStore()
            c_ids = c_store.list_ids()
            if not c_ids:
                self.wfile.write(b"No candidates found. Import one first.")
                return
            
            cid = c_ids[0]
            c_data = c_store.load(cid)
            symbol = c_data.get('symbol', 'UNKNOWN')
            timeframe = c_data.get('timeframe', '1h')
            build_ts = c_data.get('build_ts', '')
            
            # 2. Setup Ports
            home = os.environ.get("TEZAVER_MATRIX_HOME", ".tezaver_matrix")
            
            # Data: Check sample_bars.json or fallback
            sample_bars_path = "sample_bars.json"
            if not os.path.exists(sample_bars_path):
                 # Create minimal sample if missing
                 with open(sample_bars_path, "w") as f:
                     # Create sample 5 bars
                     json.dump([
                        {"ts": i*900, "open": 100, "high": 105, "low": 95, "close": 102, "is_closed": True} 
                        for i in range(5)
                     ], f)
            
            data_port = JsonFileDataPort(sample_bars_path)
            broker_port = SimBroker()
            store_port = FileRunStore(home)
            
            # 3. Run Cycle
            trace = TraceIds("v4-demo-ports", "demo-data", "demo-cfg")
            risk_cfg = RiskGateConfig(max_notional=10000)
            gov_cfg = GovernanceConfig(allowlist=[symbol])
            
            meta = run_cycle(
                symbol=symbol,
                timeframe=timeframe,
                candidate_build_ts=str(int(time.time())),
                trace_ids=trace,
                data=data_port,
                broker=broker_port,
                store=store,
                risk_cfg=risk_cfg,
                gov_cfg=gov_cfg,
                home=self.home,
                run_profile="SNIPER"
            )
            
            # Redirect
            self.wfile.write(b"HTTP/1.1 302 Found\r\n")
            self.wfile.write(f"Location: /runs/{meta['run_id']}\r\n".encode("utf-8"))
            self.wfile.write(b"\r\n")
            return
            
        # UI-C: Sniper Runner
        if path.startswith("/runs/sniper/"):
            cid = path.split("/")[-1]
            # Execute Run Sniper logic
            # For simplicity in panel, we can reuse logic, but let's call CLI via subprocess to ensure full environment separation?
            # Or embedded: Call run_sniper module's main logic but adapted?
            # We already have run_cycle logic embedded above in /runs/demo.
            # Let's clone /runs/demo logic but force SNIPER and real candidate load.
            
            from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
            c_store = FileCandidateStore()
            candidate = c_store.load(cid)
            if not candidate:
                self.wfile.write(b"Candidate not found")
                return
                
            # Need Bars
            # Use sample_bars.json from home or root if exists, else create dummy?
            bars_path = os.path.join(self.home, "sample_bars.json")
            if not os.path.exists(bars_path):
                # Create dummy
                 with open(bars_path, "w") as f:
                     json.dump([
                         {"ts": 1000, "open":10, "high":12, "low":9, "close":11, "volume":100, "closed": True},
                         {"ts": 2000, "open":11, "high":13, "low":10, "close":12, "volume":100, "closed": True}
                     ], f)
            
            # Setup Ports
            from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
            from tezaver.matrix.adapters.broker_sim import SimBroker
            from tezaver.matrix.adapters.store_run_fs import FileRunStore
            from tezaver.matrix.core.trace import TraceIds
            from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig
            from tezaver.matrix.core.cycle_engine import run_cycle
            
            store = FileRunStore(self.home)
            trace = TraceIds("panel", "sample_bars", "sniper-mode")
            
             # Run
            meta = run_cycle(
                symbol=candidate["symbol"],
                timeframe=candidate["timeframe"],
                candidate_build_ts=candidate["build_ts"],
                trace_ids=trace,
                data=JsonFileDataPort(bars_path),
                broker=SimBroker(),
                store=store,
                risk_cfg=RiskGateConfig(),
                gov_cfg=GovernanceConfig(allowlist=[candidate["symbol"]], max_age_seconds=99999999),
                home=self.home,
                run_profile="SNIPER"
            )
            
            # Redirect to Report
            rid = meta["run_id"]
            self.wfile.write(b"HTTP/1.1 302 Found\r\n")
            self.wfile.write(f"Location: /reports/{rid}\r\n".encode("utf-8"))
            self.wfile.write(b"\r\n")
            return

        # UI-C: Run Detail
        if path.startswith("/runs/") and not path.endswith("demo"):
            rid = path.split("/")[-1]
            from tezaver.matrix.adapters.run_store_fs import RunStoreFS
            store = RunStoreFS()
            meta = store.load_meta(rid)
            
            html = f"""
            <html>
                <h1>Run: {rid}</h1>
                <p><a href="/runs">Back to Runs</a></p>
                <ul>
                  <li><a href="/gates/{rid}">Gates Result (UI-E)</a></li>
                  <li><a href="/evidence/{rid}">Evidence & Audit (UI-G)</a></li>
                </ul>
                <pre>{json.dumps(meta, indent=2)}</pre>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-E: Gates
        if path.startswith("/gates/"):
            rid = path.split("/")[-1]
            from tezaver.matrix.adapters.run_store_fs import RunStoreFS
            store = RunStoreFS()
            gates = store.read_gates(rid)
            
            html = f"""
            <html>
                <h1>Gates: {rid}</h1>
                <p><a href="/runs/{rid}">Back to Run</a></p>
                <pre>{json.dumps(gates, indent=2)}</pre>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-G: Evidence
        if path.startswith("/evidence/"):
            rid = path.split("/")[-1]
            from tezaver.matrix.adapters.run_store_fs import RunStoreFS
            store = RunStoreFS()
            txt = store.read_events_head_tail(rid)
            
            # Read audit if available
            audit = {}
            a_path = os.path.join(store._run_dir(rid), "audit.json")
            if os.path.exists(a_path):
                with open(a_path, "r") as f:
                    audit = json.load(f)
            
            # Check for incidents
            incidents = store.list_incidents()
            related_incidents = []
            for iid in incidents:
                if rid in iid: # heuristic: INC_runid_ts
                    related_incidents.append(iid)
            
            inc_links = "".join([f'<li><a href="/incidents/{i}">{i}</a></li>' for i in related_incidents])
            
            html = f"""
            <html>
                <h1>Evidence: {rid}</h1>
                <p><a href="/runs/{rid}">Back to Run</a></p>
                
                <h2>Trade Audit (MX-5002)</h2>
                <pre>{json.dumps(audit, indent=2)}</pre>
                
                <h2>Incidents (MX-5003)</h2>
                <ul>{inc_links or "<li>None</li>"}</ul>

                <h2>Telemetry Events (MX-5001)</h2>
                <pre>{txt}</pre>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return
            
        # UI-G: Incidents List
        if path == "/incidents":
            from tezaver.matrix.adapters.run_store_fs import RunStoreFS
            store = RunStoreFS()
            incidents = store.list_incidents()
            list_html = "".join([f'<li><a href="/incidents/{i}">{i}</a></li>' for i in incidents])
            
            html = f"""
            <html>
                <head><title>UI-G: Incidents</title></head>
                <body>
                    <h1>Incidents (UI-G)</h1>
                    <p><a href="/">Back to Home</a></p>
                    <hr/>
                    <ul>{list_html}</ul>
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-G: Incident Detail
        if path.startswith("/incidents/"):
            iid = path.split("/")[-1]
            from tezaver.matrix.adapters.run_store_fs import RunStoreFS
            store = RunStoreFS()
            manifest = store.read_incident_manifest(iid)
            
            html = f"""
            <html>
                <h1>Incident: {iid}</h1>
                <p><a href="/incidents">Back to Incidents</a></p>
                <div style="background:#ffcccc; padding:10px; border:1px solid red">
                  <b>Reason:</b> {manifest.get('reason')}
                </div>
                <h3>Manifest</h3>
                <pre>{json.dumps(manifest, indent=2)}</pre>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-C: War War Runner (Demo)
        if path == "/runs/war":
            # Just run a demo session with embedded logic or subprocess?
            # Let's use subprocess to `run_war.py` for full fidelity (and args handling).
            # We'll use local candidates dir and sample bars.
            
            # Setup Inputs
            # 1. Candidates: use home/candidates
            c_dir = os.path.join(self.home, "candidates")
            if not os.path.exists(c_dir):
                self.wfile.write(b"No candidates found")
                return
                
            # 2. Bars: use sample_bars.json for all by copying to temp structure?
            # Or run_war logic allows mapping. "f{sym}.json".
            # Let's verify we have bars.
            # For DEMO: create a "bars" dir in home and populate it with sample data for found candidates.
            b_dir = os.path.join(self.home, "bars_demo")
            os.makedirs(b_dir, exist_ok=True)
            
            # Create sample data
            sample_data = [
                {"ts": 1000, "open":10, "high":12, "low":9, "close":11, "volume":100, "closed": True},
                {"ts": 2000, "open":11, "high":13, "low":10, "close":12, "volume":100, "closed": True},
                {"ts": 3000, "open":12, "high":14, "low":11, "close":13, "volume":100, "closed": True}
            ]
            
            import shutil
            candidates = [f for f in os.listdir(c_dir) if f.endswith(".json")]
            for c in candidates:
                sym = c.split("_")[0] # approximate symbol extraction
                # Write sym.json
                with open(os.path.join(b_dir, f"{sym}.json"), "w") as f:
                    json.dump(sample_data, f)
            
            # Run Subprocess
            import subprocess
            import sys
            
            cmd = [
                sys.executable, "-m", "tezaver.matrix.apps.run_war",
                "--candidates-dir", c_dir,
                "--bars-dir", b_dir,
                "--home", self.home,
                "--limit", "3"
            ]
            env = os.environ.copy()
            env["PYTHONPATH"] = os.path.join(os.getcwd(), "src")
            
            # We want to capture the session ID from stdout?
            # Or just find the latest session dir.
            
            try:
                proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
                if proc.returncode not in (0, 1, 2): # 2 is FAIL which is okay for demo result
                     self.wfile.write(f"Error running war: {proc.stderr}".encode("utf-8"))
                     return
                
                # Find latest session
                s_dir = os.path.join(self.home, "war_sessions")
                sessions = sorted(os.listdir(s_dir), reverse=True)
                if not sessions:
                    self.wfile.write(b"No session created")
                    return
                    
                latest = sessions[0]
                
                # Redirect
                self.wfile.write(b"HTTP/1.1 302 Found\r\n")
                self.wfile.write(f"Location: /reports/war/{latest}\r\n".encode("utf-8"))
                self.wfile.write(b"\r\n")
                return

            except Exception as e:
                self.wfile.write(f"Exception: {e}".encode("utf-8"))
                return

        # UI-F: Reports List
        if path == "/reports":
            runs_dir = os.path.join(self.home, "runs")
            if not os.path.exists(runs_dir):
                self.wfile.write(b"No runs found")
                return
            runs = sorted(os.listdir(runs_dir), reverse=True)
            links = "".join([f'<li><a href="/reports/{r}">{r}</a></li>' for r in runs])
            
            html = f"""
            <html>
                <h1>Run Reports</h1>
                <p><a href="/runs/war">Start War Run (Demo)</a></p>
                <h3>Individual Runs</h3>
                <ul>{links}</ul>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-F: War Report
        if path.startswith("/reports/war/"):
            sid = path.split("/")[-1]
            s_dir = os.path.join(self.home, "war_sessions", sid)
            idx_path = os.path.join(s_dir, "index.json")
            
            if not os.path.exists(idx_path):
                self.wfile.write(b"Session index not found")
                return
                
            with open(idx_path) as f:
                rows = json.load(f)
                
            table_rows = ""
            for r in rows:
                rid = r.get("run_id", "")
                verdict = r.get("verdict", "N/A")
                color = "green" if verdict == "PASS" else ("red" if verdict == "FAIL" else "black")
                
                link = f'<a href="/reports/{rid}">{rid}</a>' if rid else "No Run"
                
                table_rows += f"""
                <tr>
                    <td>{r.get('candidate_id', 'Unknown')}</td>
                    <td><span style="color:{color}">{verdict}</span></td>
                    <td>{r.get('stage_after', '-')}</td>
                    <td>{link}</td>
                    <td>{r.get('error', '')}</td>
                </tr>
                """
                
            html = f"""
            <html>
                <h1>War Session: {sid}</h1>
                <table border="1" cellpadding="5">
                    <tr><th>Candidate</th><th>Verdict</th><th>Stage After</th><th>Report</th><th>Error</th></tr>
                    {table_rows}
                </table>
                <p><a href="/reports">Back to Reports</a></p>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-NEW: Orchestrator
        if path.startswith("/orchestrator"):
            from tezaver.matrix.core.orchestrator import OrchestratorStore, enqueue_job, run_ticks
            
            # Actions
            if path.startswith("/orchestrator/run"):
                # Run ticks
                run_ticks(self.home, ticks=5)
                self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /orchestrator\r\n\r\n")
                return
                
            if path.startswith("/orchestrator/enqueue/sniper/"):
                cid = path.split("/")[-1]
                bars = os.path.join(self.home, "sample_bars.json") # Demo
                if not os.path.exists(bars):
                     with open(bars, "w") as f: json.dump([{"ts":1000,"close":10,"closed":True}], f)
                     
                enqueue_job(self.home, "SNIPER", {"candidate_id": cid, "bars_path": bars}, priority=60)
                self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /orchestrator\r\n\r\n")
                return

            if path.startswith("/orchestrator/enqueue/live_step/"):
                rid = path.split("/")[-1].split("?")[0]
                bars = os.path.join(self.home, "sample_bars.json")
                enqueue_job(self.home, "LIVE_STEP", {"run_id": rid, "bars_path": bars, "steps": 5}, priority=100)
                self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /orchestrator\r\n\r\n")
                return

            # Dashboard
            store = OrchestratorStore(self.home)
            queue = store.load_queue()
            locks = store.load_locks()
            history = store.load_history()
            
            q_rows = ""
            for j in queue:
                q_rows += f"<tr><td>{j.job_id}</td><td>{j.type}</td><td>{j.priority}</td><td>{j.status}</td></tr>"
                
            h_rows = ""
            for j in history:
                res_sum = str(j.get('result', {}))[:50]
                h_rows += f"<tr><td>{j.get('job_id')}</td><td>{j.get('type')}</td><td>{j.get('status')}</td><td>{res_sum}</td></tr>"
                
            html = f"""
            <html>
                <h1>Orchestrator</h1>
                <p>
                    <a href="/reports">Reports</a> | 
                    <a href="/orchestrator/run"><button>RUN TICKS (5)</button></a>
                </p>
                
                <div style="display:flex; gap:20px">
                    <div style="flex:1">
                        <h3>Job Queue ({len(queue)})</h3>
                        <table border="1">
                            <tr><th>ID</th><th>Type</th><th>Pri</th><th>Status</th></tr>
                            {q_rows}
                        </table>
                    </div>
                    <div style="flex:1">
                        <h3>Locks</h3>
                        <pre>{json.dumps(locks, indent=2)}</pre>
                    </div>
                </div>
                
                <h3>History</h3>
                <table border="1">
                    <tr><th>ID</th><th>Type</th><th>Status</th><th>Result</th></tr>
                    {h_rows}
                </table>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

            self.wfile.write(html.encode("utf-8"))
            return

        # UI-NEW: Approved Pool
        if path.startswith("/approved"):
            # Detail
            if len(path.split("/")) > 2:
                cid = path.split("/")[-1]
                app_dir = os.path.join(self.home, "approved", cid)
                man_path = os.path.join(app_dir, "manifest.json")
                
                content = "<h3>Not Found</h3>"
                if os.path.exists(man_path):
                    with open(man_path) as f: man = json.load(f)
                    
                    last_live = man.get("last_live_run_id", "")
                    content = f"""
                    <h2>Approved Details: {cid}</h2>
                    <ul>
                        <li>Symbol: {man.get('symbol')}</li>
                        <li>Timeframe: {man.get('timeframe')}</li>
                        <li>Approved TS: {man.get('approved_ts')}</li>
                        <li>Last Live Run: <a href="/reports/{last_live}">{last_live}</a></li>
                        <li>Story: <a href="/story/{cid}?mode=read">View Story</a></li>
                    </ul>
                    <h3>Manifest</h3>
                    <pre>{json.dumps(man, indent=2)}</pre>
                    <h3>Proofs</h3>
                    <ul>
                        <li><a href="/approved/{cid}/proofs/last_live_run_judge.json">Judge</a></li>
                        <li><a href="/approved/{cid}/proofs/last_live_run_scorecard.json">Scorecard</a></li>
                    </ul>
                    """
                
                html = f"""<html><a href="/approved"><< Back</a>{content}</html>"""
                self.wfile.write(html.encode("utf-8"))
                return
            
            # List
            app_root = os.path.join(self.home, "approved")
            rows = ""
            if os.path.exists(app_root):
                for cid in sorted(os.listdir(app_root)):
                    if cid.startswith("EXPORT_"): continue # Just in case
                    mp = os.path.join(app_root, cid, "manifest.json")
                    ts = ""
                    if os.path.exists(mp):
                        with open(mp) as f: ts = json.load(f).get("approved_ts", "")
                    rows += f"<tr><td><a href='/approved/{cid}'>{cid}</a></td><td>{ts}</td></tr>"
            
            html = f"""
            <html>
                <h1>Approved Pool</h1>
                <table border="1">
                    <tr><th>Candidate</th><th>Approved TS</th></tr>
                    {rows}
                </table>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-NEW: Exports
        if path.startswith("/exports"):
            exp_root = os.path.join(self.home, "exports")
            rows = ""
            if os.path.exists(exp_root):
                for eid in sorted(os.listdir(exp_root), reverse=True):
                    mp = os.path.join(exp_root, eid, "export_manifest.json")
                    info = ""
                    if os.path.exists(mp):
                        with open(mp) as f: 
                            m = json.load(f)
                            info = f"{m.get('candidate_id')} ({len(m.get('files',[]))} files)"
                    rows += f"<tr><td>{eid}</td><td>{info}</td></tr>"
                    
            html = f"""
            <html>
                <h1>Exports</h1>
                <table border="1">
                    <tr><th>Export ID</th><th>Info</th></tr>
                    {rows}
                </table>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

            self.wfile.write(html.encode("utf-8"))
            return

        # UI-NEW: Cloud Registry
        if path.startswith("/cloud"):
            from tezaver.matrix.core.cloud_registry import list_strategies, read_strategy, set_status
            
            # Actions
            if "/activate" in path or "/pause" in path:
                sid = path.split("/")[2]
                new_status = "ACTIVE" if "/activate" in path else "PAUSED"
                set_status(self.home, sid, new_status)
                self.wfile.write(f"HTTP/1.1 302 Found\r\nLocation: /cloud/{sid}\r\n\r\n".encode("utf-8"))
                return
                
            # Detail
            if len(path.split("/")) > 2:
                sid = path.split("/")[2]
                strat = read_strategy(self.home, sid)
                
                content = "<h3>Not Found</h3>"
                if strat:
                    status = strat.get("status_info", {}).get("status", "UNKNOWN")
                    # Action buttons
                    actions = ""
                    if status == "ACTIVE":
                        actions = f"""<a href="/cloud/{sid}/pause"><button style="background:orange">PAUSE</button></a>"""
                    else:
                        actions = f"""<a href="/cloud/{sid}/activate"><button style="background:green;color:white">ACTIVATE</button></a>"""
                        
                    content = f"""
                    <h2>Cloud Strategy: {sid}</h2>
                    <div style="padding:10px; border:1px solid #ccc; background:#eee">
                        Status: <b>{status}</b> {actions}
                    </div>
                    <ul>
                        <li>Candidate: {strat.get('candidate_id')}</li>
                        <li>Symbol: {strat.get('symbol')}</li>
                        <li>Imported: {strat.get('imported_ts')}</li>
                    </ul>
                    <h3>Strategy JSON</h3>
                    <pre>{json.dumps(strat, indent=2)}</pre>
                    """
                
                html = f"""<html><a href="/cloud"><< Back</a>{content}</html>"""
                self.wfile.write(html.encode("utf-8"))
                return
            
            # List
            strategies = list_strategies(self.home)
            rows = ""
            for sid in strategies:
                s = read_strategy(self.home, sid)
                st = s.get("status_info", {}).get("status", "UNKNOWN")
                rows += f"<tr><td><a href='/cloud/{sid}'>{sid}</a></td><td>{s.get('symbol')}</td><td>{st}</td></tr>"
            
            html = f"""
            <html>
                <h1>Cloud Registry</h1>
                <table border="1">
                    <tr><th>Strategy ID</th><th>Symbol</th><th>Status</th></tr>
                    {rows}
                </table>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-NEW: Ops & Maintenance
        if path.startswith("/maintenance/run_preflight"):
            from tezaver.matrix.core.preflight import run_preflight
            run_preflight(self.home)
            # Save report logic in run_preflight doesn't save to file by default in core?
            # Wait, preflight_cli saves. core checking function returns dict.
            # We should save here too.
            rep = run_preflight(self.home)
            rp = os.path.join(self.home, "ops", "preflight", "latest.json")
            os.makedirs(os.path.dirname(rp), exist_ok=True)
            with open(rp, "w") as f: json.dump(rep, f, indent=2)
            
            self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /ops\r\n\r\n")
            return

            self.wfile.write(html.encode("utf-8"))
            return
            
        # Recovery Action
        if path.startswith("/maintenance/recover"):
            from tezaver.matrix.apps.recover import run_recovery
            run_recovery(self.home)
            self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /ops\r\n\r\n")
            return

        if path.startswith("/ops") or path.startswith("/maintenance"):
            # Load Preflight
            pp = os.path.join(self.home, "ops", "preflight", "latest.json")
            p_html = "<p>No preflight report.</p>"
            if os.path.exists(pp):
                with open(pp) as f: r = json.load(f)
                color = "green" if r.get("ok") else "red"
                p_html = f"<h3 style='color:{color}'>Preflight Status: {'PASS' if r.get('ok') else 'FAIL'}</h3>"
                p_html += "<ul>"
                for c in r.get("checks", []):
                    p_html += f"<li>[{c['status']}] {c['name']}: {c['detail']}</li>"
                p_html += "</ul>"
                if r.get("warnings"):
                    p_html += "<h4>Warnings</h4><ul>"
                    for w in r.get("warnings"): p_html += f"<li>{w}</li>"
                    p_html += "</ul>"
            
            # Load Recovery
            rec_html = "<p>No recovery report.</p>"
            rp = os.path.join(self.home, "ops", "recovery", "latest.json")
            if os.path.exists(rp):
                with open(rp) as f: r = json.load(f)
                rec_html = f"""
                <h3>Last Recovery</h3>
                <ul>
                    <li>Requeued: {r['orchestrator']['requeued']}</li>
                    <li>Stale Locks Removed: {r['orchestrator']['stale_locks_removed']}</li>
                    <li>Live Runs: {r['live']['runs_scanned']}</li>
                </ul>
                """
                if r['live']['warnings']:
                    rec_html += "<h4>Live Warnings</h4><ul>"
                    for w in r['live']['warnings']: rec_html += f"<li>{w}</li>"
                    rec_html += "</ul>"
                    
            html = f"""
            <html>
                <h1>Ops & Maintenance</h1>
                <p>
                    <a href="/maintenance/run_preflight"><button>RUN PREFLIGHT CHECKS</button></a>
                    <a href="/maintenance/recover"><button style="background:orange">RUN RECOVERY</button></a>
                </p>
                <div style="display:flex; gap:20px">
                    <div style="flex:1; border:1px solid #ccc; padding:10px">
                        <h2>Preflight Report</h2>
                        {p_html}
                    </div>
                    <div style="flex:1; border:1px solid #ccc; padding:10px">
                        <h2>Recovery Report</h2>
                        {rec_html}
                    </div>
                </div>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

            self.wfile.write(html.encode("utf-8"))
            return
            
        # UI-NEW: E2E Scenario
        if path.startswith("/e2e/run"):
             from tezaver.matrix.core.golden_e2e import run_golden_e2e
             try:
                 res = run_golden_e2e(self.home)
                 eid = res["e2e_id"]
                 self.wfile.write(f"HTTP/1.1 302 Found\r\nLocation: /e2e/{eid}\r\n\r\n".encode("utf-8"))
             except Exception as e:
                 self.wfile.write(f"E2E Failed: {e}".encode("utf-8"))
             return

        if path.startswith("/e2e"):
            e2e_root = os.path.join(self.home, "e2e")
            
            # Detail
            if len(path.split("/")) > 2:
                eid = path.split("/")[-1]
                b_dir = os.path.join(e2e_root, eid)
                
                content = "<h3>Not Found</h3>"
                if os.path.exists(b_dir):
                    man = {}
                    with open(os.path.join(b_dir, "manifest.json")) as f: man = json.load(f)
                    
                    links = {}
                    lp = os.path.join(b_dir, "links.json")
                    if os.path.exists(lp):
                        with open(lp) as f: links = json.load(f)
                        
                    link_html = "<ul>"
                    for k, v in links.items():
                        link_html += f"<li><b>{k}:</b> <a href='{v}'>{v}</a></li>"
                    link_html += "</ul>"
                    
                    content = f"""
                    <h2>E2E Bundle: {eid}</h2>
                    <p>TS: {man.get('ts')}</p>
                    <h3>Artifact Links</h3>
                    {link_html}
                    <h3>Manifest</h3>
                    <pre>{json.dumps(man, indent=2)}</pre>
                    """
                
                html = f"""<html><a href="/e2e"><< Back</a>{content}</html>"""
                self.wfile.write(html.encode("utf-8"))
                return
            
            # List
            rows = ""
            if os.path.exists(e2e_root):
                for eid in sorted(os.listdir(e2e_root), reverse=True):
                    rows += f"<tr><td><a href='/e2e/{eid}'>{eid}</a></td></tr>"
                    
            html = f"""
            <html>
                <h1>Golden E2E Scenarios</h1>
                <p><a href="/e2e/run"><button style="background:gold; color:black">RUN GOLDEN E2E</button></a></p>
                <table border="1">
                    <tr><th>E2E ID</th></tr>
                    {rows}
                </table>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

            self.wfile.write(html.encode("utf-8"))
            return
            
        # UI-NEW: Cloud Runtime
        if path.startswith("/cloud/runtime/run"):
             # Parse ticks from query? Simple parsing
             ticks = 1
             if "ticks=" in path:
                 try:
                     ticks = int(path.split("ticks=")[1].split("&")[0])
                 except: pass
                 
             from tezaver.matrix.core.cloud_runtime import cloud_runtime_tick
             try:
                 cloud_runtime_tick(self.home, ticks=ticks)
                 self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /cloud/runtime\r\n\r\n")
             except Exception as e:
                 self.wfile.write(f"Runtime Failed: {e}".encode("utf-8"))
             return

        # UI-NEW: Strategy Detail
        if path.startswith("/cloud/runtime/strategy/"):
             sid = path.split("/cloud/runtime/strategy/")[1]
             # Load artifacts
             s_path = os.path.join(self.home, "cloud_registry", "strategies", sid, "strategy.json")
             pf_path = os.path.join(self.home, "cloud_runtime", "strategies", sid, "portfolio.json")
             ord_path = os.path.join(self.home, "cloud_runtime", "strategies", sid, "orders.ndjson")
             
             s_json = {}
             if os.path.exists(s_path):
                 with open(s_path) as f: s_json = json.load(f)
             
             pf_json = {}
             if os.path.exists(pf_path):
                 with open(pf_path) as f: pf_json = json.load(f)
                 
             orders_html = "<p>No orders</p>"
             if os.path.exists(ord_path):
                 # Tail last 20
                 lines = []
                 with open(ord_path) as f:
                     for line in f: lines.append(line)
                 tail = lines[-20:]
                 orders_html = "<pre>" + "".join(tail) + "</pre>"
                 
             html = f"""
             <html>
                <h1>Strategy Detail: {sid}</h1>
                <p><a href="/cloud/runtime">Back to Runtime</a></p>
                
                <h2>Portfolio</h2>
                <pre>{json.dumps(pf_json, indent=2)}</pre>
                
                <h2>Orders (Tail)</h2>
                {orders_html}
                
                <h2>Strategy Config</h2>
                <pre>{json.dumps(s_json, indent=2)}</pre>
             </html>
             """
             self.wfile.write(html.encode("utf-8"))
             return
             
        # UI-NEW: Pause/Resume
        if path.startswith("/cloud/runtime/pause"):
             from tezaver.matrix.core.global_risk import load_global_risk, save_global_risk
             cfg = load_global_risk(self.home)
             cfg["paused"] = True
             save_global_risk(self.home, cfg)
             self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /cloud/runtime\r\n\r\n")
             return
             
        if path.startswith("/cloud/runtime/resume"):
             from tezaver.matrix.core.global_risk import load_global_risk, save_global_risk
             cfg = load_global_risk(self.home)
             cfg["paused"] = False
             save_global_risk(self.home, cfg)
             self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /cloud/runtime\r\n\r\n")
             return

        # UI-NEW: Broker Mode Switch
        if path.startswith("/cloud/runtime/broker/paper"):
             from tezaver.matrix.core.broker_config import load_broker_config, save_broker_config
             cfg = load_broker_config(self.home)
             cfg["mode"] = "PAPER"
             save_broker_config(self.home, cfg)
             self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /cloud/runtime\r\n\r\n")
             return
             
        if path.startswith("/cloud/runtime/broker/real_dryrun"):
             from tezaver.matrix.core.broker_config import load_broker_config, save_broker_config
             cfg = load_broker_config(self.home)
             cfg["mode"] = "REAL_DRYRUN"
             save_broker_config(self.home, cfg)
             self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /cloud/runtime\r\n\r\n")
             return
             
        if path.startswith("/cloud/runtime/broker/real_binance_stub"):
             from tezaver.matrix.core.broker_config import load_broker_config, save_broker_config
             cfg = load_broker_config(self.home)
             cfg["mode"] = "REAL_BINANCE_STUB"
             save_broker_config(self.home, cfg)
             self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /cloud/runtime\r\n\r\n")
             return

        if path.startswith("/cloud/runtime"):
            from tezaver.matrix.core.cloud_runtime import list_active_strategies, start_or_load_runtime_state, load_strategy_state
            from tezaver.matrix.core.paper_broker import load_portfolio
            from tezaver.matrix.core.global_risk import load_global_risk, compute_totals, evaluate_risk_status
            from tezaver.matrix.core.broker_config import load_broker_config
            from tezaver.matrix.core.secrets import load_binance_secrets, redact_secrets
            
            active = list_active_strategies(self.home)
            state = start_or_load_runtime_state(self.home) # ensure structure exists
            
            # Global Risk
            risk_cfg = load_global_risk(self.home)
            risk_totals = compute_totals(self.home, active)
            risk_status = evaluate_risk_status(risk_cfg, risk_totals)
            
            risk_color = "red" if risk_status or risk_cfg["paused"] else "green"
            pause_btn = '<a href="/cloud/runtime/resume"><button style="background:green;color:white">RESUME</button></a>' if risk_cfg["paused"] else '<a href="/cloud/runtime/pause"><button style="background:red;color:white">PAUSE (Kill Switch)</button></a>'
            
            # Broker Config & Secrets
            broker_cfg = load_broker_config(self.home)
            broker_mode = broker_cfg.get("mode", "PAPER")
            broker_color = "blue"
            if broker_mode == "REAL_DRYRUN": broker_color = "orange"
            if broker_mode == "REAL_BINANCE_STUB": broker_color = "purple"
            
            secrets = load_binance_secrets(self.home)
            rsec = redact_secrets(secrets)
            sec_html = f"<span style='color:green'>SECRETS OK ({rsec['source']})</span>" if secrets['present'] else "<span style='color:red'>SECRETS MISSING</span>"
            
            broker_html = f"""
            <div style="border:2px solid {broker_color}; padding: 10px; margin-bottom: 20px;">
                <h3>Broker Adapter</h3>
                <p>Mode: <b>{broker_mode}</b></p>
                <p>Secrets Health: {sec_html}</p>
                <p>
                    <a href="/cloud/runtime/broker/paper"><button>PAPER</button></a>
                    <a href="/cloud/runtime/broker/real_dryrun"><button>REAL_DRYRUN</button></a>
                    <a href="/cloud/runtime/broker/real_binance_stub"><button>REAL_BINANCE_STUB</button></a>
                </p>
            </div>
            """
            
            risk_html = f"""
            <div style="border:2px solid {risk_color}; padding: 10px; margin-bottom: 20px;">
                <h3>Global Risk & Control</h3>
                <p>Status: <b>{'PAUSED' if risk_cfg['paused'] else 'RUNNING'}</b> {pause_btn}</p>
                <p>
                  Open Pos: {risk_totals['open_positions']} / {risk_cfg['max_open_positions']} <br/>
                  Notional: {risk_totals['total_notional']:.2f} / {risk_cfg['max_total_notional']:.2f}
                </p>
                <p style="color:red">{'<br/>'.join(risk_status)}</p>
            </div>
            """
            
            crid = state.get("cloud_run_id")
            
            # Load last heartbeat
            hb_html = "<p>No heartbeat</p>"
            hb_path = os.path.join(self.home, "cloud_runtime", "runs", crid, "heartbeat.json")
            if os.path.exists(hb_path):
                with open(hb_path) as f: hb = json.load(f)
                hb_html = f"<pre>{json.dumps(hb, indent=2)}</pre>"
                
            # Table Logic
            # Read state for each active strategy
            rows = ""
            for sid in active:
                s_state = load_strategy_state(self.home, sid)
                pf = load_portfolio(self.home, sid)
                
                # Default values if no state yet
                cursor = "-"
                last_ts = "-"
                
                if s_state:
                     cursor = s_state.get("cursor", 0)
                     last_ts = s_state.get("last_ts", 0)
                     
                rows += f"""
                <tr>
                    <td><a href='/cloud/runtime/strategy/{sid}'>{sid}</a></td>
                    <td>{cursor}</td>
                    <td>{last_ts}</td>
                    <td>{pf.get('position_qty')}</td>
                    <td>{pf.get('avg_price')}</td>
                </tr>
                """
            
            active_html = f"""
            <table border="1" cellpadding="5" style="border-collapse:collapse; width:100%">
                <tr>
                    <th>Strategy ID</th>
                    <th>Cursor</th>
                    <th>Last TS</th>
                    <th>Pos Qty</th>
                    <th>Avg Price</th>
                </tr>
                {rows}
            </table>
            """
            
            html = f"""
            <html>
                <h1>Cloud Runtime</h1>
                
                <div style="display:flex; gap:20px">
                    <div style="flex:1">{risk_html}</div>
                    <div style="flex:1">{broker_html}</div>
                </div>
                
                <p>
                    <b>Run ID:</b> {crid} <br/>
                    <b>Total Ticks:</b> {state.get('total_ticks')} <br/>
                    <b>Last Tick:</b> {state.get('last_tick_ts')}
                </p>
                <p>
                    <a href="/cloud/runtime/run?ticks=1&steps=10"><button>Tick (1)</button></a>
                    <a href="/cloud/runtime/run?ticks=5&steps=20"><button>Tick (5)</button></a>
                </p>
                <div style="display:flex; gap:20px">
                    <div style="flex:2; border:1px solid #ccc; padding:10px">
                        <h2>Active Strategies ({len(active)})</h2>
                        {active_html}
                    </div>
                    <div style="flex:1; border:1px solid #ccc; padding:10px">
                        <h2>Last Heartbeat</h2>
                        {hb_html}
                    </div>
                </div>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-C: Live Runner (Demo)
        if path.startswith("/runs/live/"):
            parts = path.split("/")
            # /runs/live/<cid> -> Start New
            # /runs/live/step/<rid>?steps=N -> Step (Resume)
            
            # Start New
            if len(parts) == 4 and parts[2] == "live":
                cid = parts[3]
                # Use run_live CLI logic or embedded live_engine? 
                # Embedded is cleaner for demo speed.
                
                from tezaver.matrix.core.live_engine import start_live_run, live_step
                from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
                from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
                from tezaver.matrix.adapters.broker_sim import SimBroker
                from tezaver.matrix.adapters.store_run_fs import FileRunStore
                from tezaver.matrix.core.trace import TraceIds
                from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig
                
                c_store = FileCandidateStore(self.home)
                candidate = c_store.load(cid)
                if not candidate:
                    self.wfile.write(b"Candidate not found")
                    return
                
                # Bars
                bars_path = os.path.join(self.home, "sample_bars.json")
                if not os.path.exists(bars_path):
                     with open(bars_path, "w") as f:
                        json.dump([
                             {"ts": 1000, "open":10, "high":12, "low":9, "close":11, "volume":100, "closed": True},
                             {"ts": 2000, "open":11, "high":13, "low":10, "close":12, "volume":100, "closed": True},
                             # Gap
                             {"ts": 5000000, "open":12, "high":14, "low":11, "close":13, "volume":100, "closed": True} 
                        ], f)
                
                rid = start_live_run(
                    home=self.home,
                    symbol=candidate["symbol"],
                    timeframe=candidate["timeframe"],
                    candidate_build_ts=candidate["build_ts"],
                    trace_ids=TraceIds("panel-live", "sample", "live"),
                    data=JsonFileDataPort(bars_path),
                    broker=SimBroker(),
                    store=FileRunStore(self.home),
                    gov_cfg=GovernanceConfig(allowlist=[candidate["symbol"]], max_age_seconds=999999999),
                    risk_cfg=RiskGateConfig()
                )
                
                # Step initial 10
                live_step(
                    home=self.home,
                    run_id=rid,
                    steps=1,
                    symbol=candidate["symbol"],
                    timeframe=candidate["timeframe"],
                    trace_ids=TraceIds("panel-live", "sample", "live"),
                    data=JsonFileDataPort(bars_path),
                    broker=SimBroker(),
                    store=FileRunStore(self.home),
                    gov_cfg=GovernanceConfig(allowlist=[candidate["symbol"]], max_age_seconds=999999999),
                    risk_cfg=RiskGateConfig(),
                    candidate_id=cid
                )
                
                # Redirect
                self.wfile.write(b"HTTP/1.1 302 Found\r\n")
                self.wfile.write(f"Location: /reports/{rid}\r\n".encode("utf-8"))
                self.wfile.write(b"\r\n")
                return

            # Step Existing
            if len(parts) >= 4 and parts[2] == "live" and parts[3] == "step":
                # /runs/live/step/<rid>?steps=20
                rid = parts[4].split("?")[0]
                
                # We need symbol/tf from meta.
                mp = os.path.join(self.home, "runs", rid, "meta.json")
                if not os.path.exists(mp):
                    self.wfile.write(b"Run not found")
                    return
                with open(mp) as f: meta = json.load(f)
                
                sym = meta["candidate"]["symbol"]
                tf = meta["candidate"]["timeframe"]
                cid = meta.get("candidate", {}).get("symbol", "UNKNOWN") # approximate
                
                bars_path = os.path.join(self.home, "sample_bars.json")
                
                from tezaver.matrix.core.live_engine import live_step
                from tezaver.matrix.adapters.data_port_json import JsonFileDataPort
                from tezaver.matrix.adapters.broker_sim import SimBroker
                from tezaver.matrix.adapters.store_run_fs import FileRunStore
                from tezaver.matrix.core.trace import TraceIds
                from tezaver.matrix.core.gates import RiskGateConfig, GovernanceConfig

                live_step(
                    home=self.home,
                    run_id=rid,
                    steps=1, # Just 1 for demo click
                    symbol=sym,
                    timeframe=tf,
                    trace_ids=TraceIds("panel-live", "sample", "live"),
                    data=JsonFileDataPort(bars_path),
                    broker=SimBroker(),
                    store=FileRunStore(self.home),
                    gov_cfg=GovernanceConfig(allowlist=[sym], max_age_seconds=999999999),
                    risk_cfg=RiskGateConfig(),
                    candidate_id=cid
                )
                
                # Redirect
                self.wfile.write(b"HTTP/1.1 302 Found\r\n")
                self.wfile.write(f"Location: /reports/{rid}\r\n".encode("utf-8"))
                self.wfile.write(b"\r\n")
                return

        # UI-F: Report Detail
        if path.startswith("/reports/"):
            rid = path.split("/")[-1]
            from tezaver.matrix.adapters.run_store_fs import RunStoreFS
            store = RunStoreFS()
            
            # Load artifacts
            run_dir = store._run_dir(rid)
            judge = {}
            score = {}
            meta = {}
            
            jp = os.path.join(run_dir, "judge.json")
            if os.path.exists(jp): 
                with open(jp) as f: judge = json.load(f)
                
            sp = os.path.join(run_dir, "scorecard.json")
            if os.path.exists(sp): 
                with open(sp) as f: score = json.load(f)
                
            mp = os.path.join(run_dir, "meta.json")
            if os.path.exists(mp): 
                with open(mp) as f: meta = json.load(f)
            
            verdict = judge.get("overall", "UNKNOWN")
            color = "green" if verdict == "PASS" else ("red" if verdict == "FAIL" else "orange")
            
            cid = meta.get("candidate", {}).get("symbol", "??") # Approximate
            profile = meta.get("run_profile", "UNKNOWN")
            
            # Try to get candidate_id if stored? We decided to rely on meta or external.
            # Links
            
            # Live State
            live_html = ""
            ls_path = os.path.join(run_dir, "live_state.json")
            if os.path.exists(ls_path):
                with open(ls_path) as f: ls = json.load(f)
                live_html = f"""
                <div style="padding:10px; background:#eef; margin-bottom:20px">
                    <h3>LIVE STATE</h3>
                    <p><b>Cursor:</b> {ls.get('cursor', '?')}</p>
                    <p><b>Last Bar TS:</b> {ls.get('last_bar_ts', '?')}</p>
                    <p>
                        <a href="/runs/live/step/{rid}"><button>Step >></button></a>
                    </p>
                </div>
                """
            
            html = f"""
            <html>
                <h1>Report: {rid}</h1>
                <p><a href="/reports">Back</a> | <a href="/runs/{rid}">Raw Run</a></p>
                
                <div style="padding:20px; border:2px solid {color}; margin-bottom:20px">
                    <h2>Verdict: {verdict}</h2>
                    <h3>Profile: {profile}</h3>
                </div>
                
                {live_html}
                
                <h3>Jury Scorecard (MX-7001)</h3>
                <pre>{json.dumps(score, indent=2)}</pre>
                
                <h3>Judge Gates (MX-7002)</h3>
                <pre>{json.dumps(judge, indent=2)}</pre>
                
                <h3>Links</h3>
                <ul>
                    <li><a href="/evidence/{rid}">Evidence (Audit)</a></li>
                    <li><a href="/judge/{rid}">Judge View</a></li>
                </ul>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-E: Judge View
        if path.startswith("/judge/"):
            rid = path.split("/")[-1]
            # Same content as report section basically, simplified
            html = f"<html><h1>Judge: {rid}</h1><p>See <a href='/reports/{rid}'>Report</a></p></html>"
            self.wfile.write(html.encode("utf-8")) # Correction: encode(str) -> bytes. Fixed bug below.
            return

        # UI-C: Alerts (Phase-13C)
        if path == "/alerts":
            from tezaver.matrix.adapters.notifier_file import FileNotifier
            notifier = FileNotifier(self.home)
            active = notifier.list_active()
            
            rows = ""
            for a in active:
                aid = a["alert_id"]
                sev = a["severity"]
                color = "black"
                if sev == "CRIT": color = "red"
                if sev == "WARN": color = "orange"
                if sev == "INFO": color = "blue"
                
                rows += f"""
                <tr>
                    <td><b style="color:{color}">{sev}</b></td>
                    <td>{a.get('type')}</td>
                    <td><a href="/alerts/{aid}">{aid}</a></td>
                    <td>{a.get('ts')}</td>
                    <td>{a.get('message_tr')}</td>
                    <td><a href="/alerts/{aid}/ack"><button>ACK</button></a></td>
                </tr>
                """
                
            if not active:
                rows = "<tr><td colspan='6'>No active alerts.</td></tr>"
                
            html = f"""
            <html>
                <h1>Active Alerts ({len(active)})</h1>
                <p><a href="/">Back to Home</a> | <a href="/cloud/runtime">Runtime</a></p>
                <table border="1">
                    <tr><th>Sev</th><th>Type</th><th>ID</th><th>TS</th><th>Message</th><th>Action</th></tr>
                    {rows}
                </table>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return
            
        if path.startswith("/alerts/") and "/ack" in path:
            # /alerts/<id>/ack
            aid = path.split("/")[2]
            from tezaver.matrix.adapters.notifier_file import FileNotifier
            notifier = FileNotifier(self.home)
            notifier.ack(aid)
            
            self.wfile.write(b"HTTP/1.1 302 Found\r\nLocation: /alerts\r\n\r\n")
            return
            
        if path.startswith("/alerts/"):
            aid = path.split("/")[-1]
            # Detail
            from tezaver.matrix.adapters.notifier_file import FileNotifier
            # Load manually or list? List is inefficient. Direct read active/history.
            # But adapter doesn't expose read. Just use active check first.
            p_act = os.path.join(self.home, "alerts", "active", f"{aid}.json")
            p_hist = os.path.join(self.home, "alerts", "history", f"{aid}.json")
            
            data = {}
            status = "UNKNOWN"
            if os.path.exists(p_act):
                status = "ACTIVE"
                with open(p_act) as f: data = json.load(f)
            elif os.path.exists(p_hist):
                status = "HISTORY (ACK)"
                with open(p_hist) as f: data = json.load(f)
                
            ack_btn = f'<a href="/alerts/{aid}/ack"><button>ACKNOWLEDGE</button></a>' if status == "ACTIVE" else ""
            
            html = f"""
            <html>
                <h1>Alert: {aid}</h1>
                <p><a href="/alerts">Back to Alerts</a></p>
                <h2>Status: {status} {ack_btn}</h2>
                <pre>{json.dumps(data, indent=2)}</pre>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

            
        # UI-I: Story Timeline
        if path.startswith("/story/"):
            cid = path.split("/")[-1]
            from tezaver.matrix.adapters.candidate_store_fs import FileCandidateStore
            from tezaver.matrix.core.story_render import render_story_html
            from tezaver.matrix.ports.candidate_bundle import candidate_id, bundle_from_dict
            
            c_store = FileCandidateStore()
            bundle = c_store.load(cid)
            if not bundle:
                self.wfile.write(b"Candidate not found")
                return
                
            # Render HTML
            story_html = render_story_html(bundle)
            
            # Derived Links Logic (MX-6003)
            # Check for same bundle_version + build_ts but 1h/4h
            # Reconstruct potential IDs
            derived_links = []
            current_tf = bundle.get("timeframe")
            
            if current_tf == "15m":
                # Check 1h and 4h
                def check_derived(tf):
                     # Construct hypothetical bundle dict to reuse ID logic
                     # (CandidateID depends on symbol, tf, ver, ts)
                     # We can just manually construct the ID string if logic is known,
                     # but using helper is safer if we had the object.
                     # Helper: {symbol}_{tf}_{ver}_{ts_clean}
                     from tezaver.matrix.ports.candidate_bundle import sanitize_id_part
                     ts_clean = sanitize_id_part(bundle.get("build_ts"))
                     did = f"{bundle.get('symbol')}_{tf}_{bundle.get('bundle_version')}_{ts_clean}"
                     if c_store.load(did):
                         return f'<a href="/story/{did}">{tf}</a>'
                     return None
                
                l1 = check_derived("1h")
                l4 = check_derived("4h")
                if l1: derived_links.append(l1)
                if l4: derived_links.append(l4)
            
            derived_html = ""
            if derived_links:
                derived_html = f"<div style='margin-top:10px;'>Derived Stories: {' | '.join(derived_links)}</div>"
            
            html = f"""
            <html>
                <h1>Story Timeline (UI-I)</h1>
                <p><a href="/">Back to Home</a> | <a href="/candidates/{cid}">View JSON</a></p>
                {derived_html}
                <hr/>
                {story_html}
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        # UI-D: Engine
        if path == "/engine":
            html = """
            <html>
                <h1>Engine Info (UI-D)</h1>
                <p><a href="/">Back to Home</a></p>
                <ul>
                    <li>Version: Matrix v4-dev</li>
                    <li>Architecture: Ports & Adapters (Hexagonal)</li>
                    <li><b>DataPort:</b> JsonFileDataPort</li>
                    <li><b>BrokerPort:</b> SimBroker (Simulation)</li>
                    <li><b>StorePort:</b> FileRunStore (FileSystem)</li>
                    <li><b>StoryEngine:</b> Timeline Renderer & Compiler (MX-6001/6003)</li>
                </ul>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
            return

        if path in ROUTES:
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            
            title = ROUTES[path]
            links = "".join([f'<li><a href="{r}">{n}</a></li>' for r, n in ROUTES.items()])
            
            html = f"""
            <html>
                <head><title>{title}</title></head>
                <body>
                    <h1>{title}</h1>
                    <p>Status: <b>ok</b></p>
                    <hr/>
                    <ul>{links}</ul>
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

def run_server():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, PanelHandler)
    print(f"Panel Server running at http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Server error: {e}")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    try:
         run_server()
    except KeyboardInterrupt:
        sys.exit(0)
