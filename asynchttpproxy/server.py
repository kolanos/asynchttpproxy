import asyncio
import aiohttp
import aiohttp.server
import io
import json
import logging
import urllib


class RequestHandler(aiohttp.server.ServerHttpProtocol):
    @asyncio.coroutine
    def handle_request(self, message, payload):
        """Override the handle_request method to add proxy behavior."""
        url = message.path
        parsed_url = urllib.parse.urlparse(url)
        logging.info('{} {}'.format(message.method, url))

        if message.method == 'GET' and url == '/ping':
            logging.info('Ping, Pong.')
            yield from self.send_pong_response(200, message.version)
            return

        if message.method != 'GET' or parsed_url.scheme.lower() != 'http':
            logging.info('Refusing non-GET/HTTP request: {}'.format(url))
            yield from self.send_response(501, message.version)
            return

        logging.debug('Executing proxy request.')
        response = yield from aiohttp.request('GET', url,
                                              headers=message.headers)
        content = response.content
        proxy_response = aiohttp.Response(self.writer, response.status,
                                          http_version=response.version)

        proxy_headers = [
            (k, v) for k, v in response.headers.items(getall=True)
            if k != 'CONTENT-ENCODING']
        proxy_response.add_headers(*proxy_headers)
        proxy_response.send_headers()

        while True:
            chunk = yield from content.read(io.DEFAULT_BUFFER_SIZE)
            if not chunk:
                break
            proxy_response.write(chunk)
        yield from proxy_response.write_eof()

    @asyncio.coroutine
    def send_response(self, status, http_version, headers=None, text=b''):
        """Helper method to send an HTTP response."""
        response = aiohttp.Response(self.writer, status,
                                    http_version=http_version)
        if isinstance(headers, list):
            for k, v in headers:
                response.add_header(k, v)
        response.add_header('Content-Length', str(len(text)))
        response.send_headers()
        response.write(text)
        yield from response.write_eof()

    @asyncio.coroutine
    def send_pong_response(self, status, http_version):
        """Sends a pong message when pinged."""
        response_text = json.dumps({
            'ping': 'pong'
        }, indent=4).encode('ascii')
        yield from self.send_response(status, http_version, text=response_text)
