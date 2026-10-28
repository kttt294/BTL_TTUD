"""Kết nối API BTC: đọc token, gửi GET/POST và nhận JSON."""

import base64
import json
import os
from pathlib import Path
import re
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
        return self.open(Request(url, data=data, headers=headers, method=method), timeout)

    def manager(self, endpoint, params=None, timeout=None):
        """GET API quản lý của website (trận, câu hỏi, danh sách đội).

        Website dùng cùng token nhưng gửi không có tiền tố Bearer cho API này.
        """
        url = self.base_url + '/manager/api' + endpoint
        if params:
            url += '?' + urlencode(params)
        headers = {'Authorization': self.token, 'User-Agent': 'Hexudon-TTUD-runner', 'Accept': 'application/json'}
        return self.open(Request(url, headers=headers), timeout)

    def open(self, request, timeout=None):
        try:
            with urlopen(request, timeout=self.timeout if timeout is None else timeout) as response:
                return json.load(response)
        except HTTPError as error:
            detail = error.read().decode('utf-8', errors='replace')[:1000]
            raise APIError(error.code, detail.replace(self.token, '[TOKEN]')) from None


GAME_ID = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?::[0-9]+)?')


def list_matches(api):
    """Các trận trên website, mỗi trận kèm danh sách câu hỏi; ID câu hỏi chính là game_id."""
    matches = api.manager('/match')['data']
    for match in matches:
        questions = api.manager('/question', {'match[eq_id]': match['id']})['data']
        match['questions'] = sorted(questions, key=lambda q: q.get('order') or 0)
    return matches


def resolve_game_id(api, name, match_id=None, practice=None, matches=None):
    """Đổi tên câu hỏi (Q02) thành game_id.

    ID dạng UUID hoặc tên không khớp câu nào được giữ nguyên để không chặn ID kiểu khác;
    chỉ báo lỗi khi tên có ở nhiều trận.
    """
    if GAME_ID.fullmatch(name):
        return name
    matches = list_matches(api) if matches is None else matches
    found = [(match, question) for match in matches for question in match['questions']
             if question['name'].lower() == name.lower()
             and (match_id is None or match['id'] == match_id)
             and (practice is None or bool(match['is_practice']) == practice)]
    if len(found) > 1:
        options = ', '.join(f"trận {m['id']} {m['name']}" for m, _ in found)
        raise ValueError(f'Câu {name} có ở nhiều trận ({options}); thêm --match MÃ_TRẬN.')
    return found[0][1]['id'] if found else name
