from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

PORT = 8085

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
