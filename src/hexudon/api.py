"""Giao tiếp với API BTC và lưu bằng chứng đối chiếu, không ghi token vào nhật ký."""

from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "https://hexudon.hairbui76.id.vn"


class CompetitionAPI:
    def __init__(self, env_file=".env", evidence_dir="experiments/api_evidence"):
        values = {}
        for line in Path(env_file).read_text(encoding="utf-8-sig").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip().strip('"').strip("'")
        self.token = values["HEXUDON_TOKEN"]
        self.directory = Path(evidence_dir)
        self.directory.mkdir(parents=True, exist_ok=True)

    def request(self, method, endpoint, params=None, body=None, label="request"):
        url = BASE_URL + endpoint
        if params:
            url += "?" + urlencode(params)
        headers = {"Authorization": "Bearer " + self.token,
                   "User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                status = response.status
                raw = response.read().decode("utf-8")
        except HTTPError as error:
            status = error.code
            raw = error.read().decode("utf-8", errors="replace")
        try:
            response_data = json.loads(raw)
        except json.JSONDecodeError:
            response_data = {"text": raw[:2000]}
        record = {"time_utc": datetime.now(timezone.utc).isoformat(), "method": method,
                  "endpoint": endpoint, "params": params, "body": body,
                  "status": status, "response": response_data}
        filename = self.directory / (label + ".json")
        filename.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        if status >= 400:
            raise ValueError(f"API trả HTTP {status}; xem bằng chứng {filename}.")
        return response_data

    def get(self, endpoint, game_id, label):
        return self.request("GET", endpoint, {"game_id": game_id}, label=label)

    def practice_actions(self, game_id, day, actions, label):
        return self.request("POST", "/api/game/practice/actions",
                            body={"game_id": game_id, "day": day, "actions": actions}, label=label)
