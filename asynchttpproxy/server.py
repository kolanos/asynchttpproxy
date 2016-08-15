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
    async def handle_request(self, message, payload):
        """Override the handle_request method to add proxy behavior."""
        global bytes_transferred
        url = message.path
        parsed_url = urllib.parse.urlparse(url)
        query = dict(urllib.parse.parse_qsl(parsed_url[4]))
        logging.info('{} {}'.format(message.method, url))

        if message.method == 'GET' and url == '/stats':
            await self.send_stats_response(200, message.version)
            return

        if parsed_url.scheme.lower() != 'http':
            logging.info('Refusing non-HTTP request: {}'.format(url))
            await self.send_response(501, message.version)
            return

        if 'range' in message.headers and 'range' in query and \
                message.headers['range'][6:] != query['range']:
            await self.send_response(416, message.version)
            return
        if 'range' in query and 'range' not in message.headers:
            message.headers['range'] = 'bytes={}'.format(query['range'])

        logging.debug('Executing proxy request.')
        response = await aiohttp.request(message.method, url,
                                         headers=message.headers)
        proxy_response = aiohttp.Response(self.writer, response.status,
                                          http_version=response.version)

        # Passthrough all headers, including range parameters, except
        # Content-Encoding since aiohttp determines that automatically.
        proxy_headers = [
            (k, v) for k, v in response.headers.items()
            if k != 'content-encoding']
        proxy_response.add_headers(*proxy_headers)
        proxy_response.send_headers()

        while True:
            chunk = await response.content.read(io.DEFAULT_BUFFER_SIZE)
            if not chunk:
                break
            proxy_response.write(chunk)
            bytes_transferred += len(chunk)
        await proxy_response.write_eof()

    async def send_response(self, status, http_version, headers=None,
                            body=b''):
        """Helper method to send an HTTP response."""
        response = aiohttp.Response(self.writer, status,
                                    http_version=http_version)
        if isinstance(headers, list):
            for k, v in headers:
                response.add_header(k, v)
        response.add_header('Content-Length', str(len(body)))
        response.send_headers()
        response.write(body)
        await response.write_eof()

    async def send_stats_response(self, status, http_version):
        """Sends bytes transfered and uptime stats."""
        body = json.dumps({
            'bytes_transferred': human_bytes(bytes_transferred),
            'uptime': uptime(uptime_start, time.time())
        }, indent=4).encode('ascii')
        headers = [('Content-Type', 'application/json')]
        await self.send_response(status, http_version, headers, body)
