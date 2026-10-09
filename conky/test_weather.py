"""Run with: python3 conky/test_weather.py."""

from copy import deepcopy
from datetime import datetime
import fcntl
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import weather


def stamp(value):
    return datetime.fromisoformat(value).replace(tzinfo=weather.ZONE).timestamp()


now = stamp("2026-10-08T18:30")
data = {
    "current": {"time": now, "temperature_2m": 12.5, "apparent_temperature": 10.2, "weather_code": 2},
    "hourly": {
        "time": [stamp(f"2026-10-08T{hour}:00") for hour in range(18, 24)],
        "temperature_2m": [13, 12, 11, 10, 9, 8],
        "weather_code": [2, 3, 61, 71, 95, 0],
        "precipitation_probability": [0, 10, 30, 40, 50, 60],
        "is_day": [1, 0, 0, 0, 0, 0],
    },
    "daily": {
        "sunrise": [stamp("2026-10-08T07:48"), stamp("2026-10-09T07:50")],
        "sunset": [stamp("2026-10-08T18:58"), stamp("2026-10-09T18:56")],
    },
}

weather.validate(data)
query = parse_qs(urlparse(weather.URL).query)
assert "apikey" not in query
assert query["timezone"] == ["America/Edmonton"]
assert sum(len(query[key][0].split(",")) for key in ("current", "hourly", "daily")) <= 10

with TemporaryDirectory() as directory:
    cache_dir = Path(directory)
    with patch.object(weather, "fetch", return_value=data) as fetch:
        first = weather.load_weather(cache_dir, now)
        assert fetch.call_count == 1
        assert weather.load_weather(cache_dir, now + 60) == first
        assert weather.load_weather(cache_dir, now + 899) == first
        assert fetch.call_count == 1
        assert weather.load_weather(cache_dir, now + 900)["updated"] == now + 900
        assert fetch.call_count == 2
    with patch.object(weather, "fetch", side_effect=OSError("offline")) as fetch:
        stale = weather.load_weather(cache_dir, now + 1800)
        assert stale["updated"] == now + 900
        assert weather.load_weather(cache_dir, now + 1860) == stale
        assert fetch.call_count == 1
        assert json.loads((cache_dir / "weather.json").read_text())["data"] == data
        weather.load_weather(cache_dir, now + 2700)
        assert fetch.call_count == 2
    with (cache_dir / "refresh.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with patch.object(weather, "fetch") as fetch:
            assert weather.load_weather(cache_dir, now + 3600) == stale
            fetch.assert_not_called()
    (cache_dir / "weather.json").write_text("broken JSON")
    with patch.object(weather, "fetch", return_value=data):
        assert weather.load_weather(cache_dir, now + 3600)["data"] == data

with TemporaryDirectory() as directory:
    with patch.object(weather, "fetch", side_effect=OSError("offline")) as fetch:
        assert weather.load_weather(Path(directory), now) == {}
        assert weather.load_weather(Path(directory), now + 60) == {}
        assert fetch.call_count == 1

output = weather.render({"data": data, "updated": now}, now)
values = output.removeprefix("${lua weather ").removesuffix("}").split()
assert len(values) == 30
assert values[:5] == ["12.5", "10.2", "2", "1110", "0"]
assert values[10:15] == ["19", "12", "3", "10", "0"]
assert weather.render({}, now) == "${lua weather}"
stale_values = weather.render({"data": data, "updated": now}, now + 900).split()
assert stale_values[6] == "1"
missing = deepcopy(data)
missing["current"]["temperature_2m"] = None
missing["hourly"]["temperature_2m"][1] = None
weather.validate(missing)
assert weather.render({"data": missing, "updated": now}, now).startswith("${lua weather - ")
assert weather.render({"data": data, "updated": now}, now + 3 * 86400).endswith("- - - - -}")

for value in (float("nan"), float("inf"), "${exec touch /tmp/weather-injection}", True):
    bad = deepcopy(data)
    bad["current"]["temperature_2m"] = value
    try:
        weather.validate(bad)
        raise AssertionError("Invalid API value accepted")
    except ValueError:
        pass
bad = deepcopy(data)
bad["hourly"]["weather_code"].pop()
try:
    weather.validate(bad)
    raise AssertionError("Mismatched forecast arrays accepted")
except ValueError:
    pass

# Calgary labels follow daylight-saving changes independently of the host timezone.
assert weather.local_time(stamp("2024-11-03T00:30")).utcoffset().total_seconds() == -6 * 3600
assert weather.local_time(stamp("2024-11-03T03:30")).utcoffset().total_seconds() == -7 * 3600
print("Weather cache, 15-minute retries, concurrent fetches, missing data, validation, and Calgary time passed")
