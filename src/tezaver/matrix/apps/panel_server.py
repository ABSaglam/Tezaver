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
                candidate_build_ts=build_ts,
                trace_ids=trace,
                data=data_port,
                broker=broker_port,
                store=store_port,
                risk_cfg=risk_cfg,
                gov_cfg=gov_cfg,
                home=home
            )
            
            # Redirect
            self.send_response(302)
            self.send_header("Location", f"/runs/{meta['run_id']}")
            self.end_headers()
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
