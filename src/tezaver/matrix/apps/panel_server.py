from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

PORT = 8085

import os
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
