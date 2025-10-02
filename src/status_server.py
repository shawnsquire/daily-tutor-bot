import logging
from http.server import BaseHTTPRequestHandler, HTTPServer

status_server_port = 8080


class StatusPageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")


def run_status_server():
    server_address = ("0.0.0.0", status_server_port)
    logging.info(f"Status server running on port {status_server_port}")
    # noinspection PyTypeChecker
    httpd = HTTPServer(server_address, StatusPageHandler)
    httpd.serve_forever()
