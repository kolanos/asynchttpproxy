import asyncio
import aiohttp
import aiohttp.server
import io
import json
import logging
import time
import urllib

from asynchttpproxy.util import human_bytes, uptime

bytes_transferred = 0
uptime_start = time.time()


class RequestHandler(aiohttp.server.ServerHttpProtocol):
    @asyncio.coroutine
    def handle_request(self, message, payload):
        """Override the handle_request method to add proxy behavior."""
        global bytes_transferred
        url = message.path
        parsed_url = urllib.parse.urlparse(url)
        query = dict(urllib.parse.parse_qsl(parsed_url[4]))
        logging.info('{} {}'.format(message.method, url))

        if message.method == 'GET' and url == '/status':
            yield from self.send_status_response(200, message.version)
            return

        if parsed_url.scheme.lower() != 'http':
            logging.info('Refusing non-HTTP request: {}'.format(url))
            yield from self.send_response(501, message.version)
            return

        if 'range' in message.headers and 'range' in query and \
                message.headers['range'][6:] != query['range']:
            yield from self.send_response(416, message.version)
            return
        if 'range' in query and 'range' not in message.headers:
            message.headers['range'] = 'bytes={}'.format(query['range'])

        logging.debug('Executing proxy request.')
        response = yield from aiohttp.request(message.method, url,
                                              headers=message.headers)
        proxy_response = aiohttp.Response(self.writer, response.status,
                                          http_version=response.version)

        # Passthrough all headers, including range parameters, except
        # Content-Encoding since aiohttp determines that automatically.
        proxy_headers = [
            (k, v) for k, v in response.headers.items(getall=True)
            if k != 'content-encoding']
        proxy_response.add_headers(*proxy_headers)
        proxy_response.send_headers()

        while True:
            chunk = yield from response.content.read(io.DEFAULT_BUFFER_SIZE)
            if not chunk:
                break
            proxy_response.write(chunk)
        yield from proxy_response.write_eof()
        bytes_transferred += int(response.headers['Content-Length'])

    @asyncio.coroutine
    def send_response(self, status, http_version, headers=None, body=b''):
        """Helper method to send an HTTP response."""
        response = aiohttp.Response(self.writer, status,
                                    http_version=http_version)
        if isinstance(headers, list):
            for k, v in headers:
                response.add_header(k, v)
        response.add_header('Content-Length', str(len(body)))
        response.send_headers()
        response.write(body)
        yield from response.write_eof()

    @asyncio.coroutine
    def send_status_response(self, status, http_version):
        """Sends bytes transfered and uptime status."""
        body = json.dumps({
            'bytes_transferred': human_bytes(bytes_transferred),
            'uptime': uptime(uptime_start, time.time())
        }, indent=4).encode('ascii')
        headers = [('Content-Type', 'application/json')]
        yield from self.send_response(status, http_version, headers, body)
