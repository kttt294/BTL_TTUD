"""Kết nối API BTC: đọc token, gửi GET/POST và nhận JSON."""

import base64
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class APIError(ValueError):
    def __init__(self, status, detail):
        self.status = status
        super().__init__(f'API HTTP {status}: {detail}')


class LiveAPI:
    def __init__(self, env_file, base_url='https://hexudon.hairbui76.id.vn', timeout=5):
        values = {}
        if Path(env_file).exists():
            for line in Path(env_file).read_text(encoding='utf-8-sig').splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    key, value = line.split('=', 1)
                    values[key.strip()] = value.strip().strip('"').strip("'")
        self.token = os.environ.get('HEXUDON_TOKEN') or values.get('HEXUDON_TOKEN')
        if not self.token:
            raise ValueError('Cần HEXUDON_TOKEN trong .env hoặc biến môi trường.')
        self.base_url, self.timeout = base_url.rstrip('/'), timeout
        try:
            payload = self.token.split('.')[1]
            claims = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
            # Chỉ lấy ID mặc định; việc xác thực token luôn do máy chủ thực hiện.
            self.team_id = str(claims['id'])
            # Hạn token (giây Unix) chỉ dùng để cảnh báo sớm; máy chủ vẫn là nơi xác thực.
            self.expires_at = claims.get('exp')
        except (ValueError, KeyError, IndexError):
            self.team_id, self.expires_at = None, None

    def request(self, method, endpoint, game_id=None, body=None, timeout=None):
        url = self.base_url + endpoint
        if game_id is not None:
            url += '?' + urlencode({'game_id': game_id})
        headers = {'Authorization': 'Bearer ' + self.token,
                   'User-Agent': 'Hexudon-TTUD-runner', 'Accept': 'application/json'}
        data = None
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout if timeout is None else timeout) as response:
                return json.load(response)
        except HTTPError as error:
            detail = error.read().decode('utf-8', errors='replace')[:1000]
            raise APIError(error.code, detail.replace(self.token, '[TOKEN]')) from None
