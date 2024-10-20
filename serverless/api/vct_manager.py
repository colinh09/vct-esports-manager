from http.server import BaseHTTPRequestHandler
import json
import asyncio
import os
from agents.vct_agent import process_vct_query

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(post_data)

        user_input = data.get('query', '')
        user_id = data.get('user_id', 'user123')
        session_id = data.get('session_id', None)

        # Check for authentication
        auth_token = self.headers.get('Authorization', '').split(' ')[-1]
        if auth_token != os.environ.get('AUTH_TOKEN', 'default_token'):
            self.send_response(401)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode())
            return

        try:
            result = asyncio.run(process_vct_query(user_input, user_id, session_id))

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())