"""Calgary weather from Open-Meteo; one cached request every 15 minutes."""

from datetime import datetime
import fcntl
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import urlopen
from zoneinfo import ZoneInfo


REFRESH = 15 * 60
ZONE = ZoneInfo("America/Edmonton")
URL = "https://api.open-meteo.com/v1/forecast?" + urlencode({
    "latitude": 51.05011,
    "longitude": -114.08529,
    "current": "temperature_2m,apparent_temperature,weather_code",
    "hourly": "temperature_2m,weather_code,precipitation_probability,is_day",
    "daily": "sunrise,sunset",
    "timezone": "America/Edmonton",
    "timeformat": "unixtime",
    "forecast_days": 2,
})


def number(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value):
        return value
    raise ValueError("Invalid weather value")


def validate(data):
    current = data["current"]
    if not number(current["time"]) or current["time"] <= 0:
        raise ValueError("Missing observation time")
    for key in ("temperature_2m", "apparent_temperature", "weather_code"):
        number(current[key])
    for section, fields in (("hourly", ("time", "temperature_2m", "weather_code",
                                       "precipitation_probability", "is_day")),
                            ("daily", ("sunrise", "sunset"))):
        arrays = [data[section][field] for field in fields]
        if not all(isinstance(values, list) for values in arrays) or not arrays[0]:
            raise ValueError("Missing forecast")
        if any(len(values) != len(arrays[0]) for values in arrays):
            raise ValueError("Incomplete forecast")
        for values in arrays:
            for value in values:
                number(value)
    for stamp in data["hourly"]["time"]:
        if stamp is None or stamp <= 0:
            raise ValueError("Invalid forecast time")
    for probability in data["hourly"]["precipitation_probability"]:
        if probability is not None and not 0 <= probability <= 100:
            raise ValueError("Invalid precipitation probability")
    for sunrise, sunset in zip(data["daily"]["sunrise"], data["daily"]["sunset"]):
        if sunrise is not None and sunset is not None and not 0 < sunrise < sunset:
            raise ValueError("Invalid daylight times")


def fetch():
    with urlopen(URL, timeout=10) as response:
        body = response.read(512_001)
    if len(body) > 512_000:
        raise ValueError("Weather response too large")
    data = json.loads(body)
    validate(data)
    return data


def load_weather(cache_dir, now):
    cache_file = cache_dir / "weather.json"
    cached = {}
    try:
        cached = json.loads(cache_file.read_text())
        validate(cached["data"])
        if not number(cached["updated"]) or cached["updated"] <= 0:
            raise ValueError("Invalid cache time")
    except (OSError, ValueError, KeyError, TypeError):
        cached = {}
    if cached and 0 <= now - cached["updated"] < REFRESH:
        return cached

    cache_dir.mkdir(parents=True, exist_ok=True)
    with (cache_dir / "refresh.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return cached
        lock.seek(0)
        try:
            attempted = float(lock.read() or 0)
        except ValueError:
            attempted = 0
        if 0 <= now - attempted < REFRESH:
            return cached
        # Record attempts before fetching so failures and restarts also respect the interval.
        lock.seek(0)
        lock.truncate()
        lock.write(str(now))
        lock.flush()
        try:
            updated = {"updated": now, "data": fetch()}
            temporary = cache_file.with_suffix(".tmp")
            temporary.write_text(json.dumps(updated, allow_nan=False))
            temporary.replace(cache_file)
        except (OSError, ValueError, KeyError, TypeError):
            return cached
        return updated


def local_time(stamp):
    return datetime.fromtimestamp(stamp, ZONE)


def minutes(stamp):
    local = local_time(stamp)
    return local.hour * 60 + local.minute


def render(cached, now):
    if not cached:
        return "${lua weather}"
    data, current = cached["data"], cached["data"]["current"]
    today = local_time(now).date()
    days = list(zip(data["daily"]["sunrise"], data["daily"]["sunset"]))
    sunrise, sunset = next(((rise, setting) for rise, setting in days
                            if rise and setting and local_time(rise).date() == today), (None, None))
    next_rise = next((rise for rise, _ in days if rise and rise > now), None)
    values = [current["temperature_2m"], current["apparent_temperature"], current["weather_code"],
              minutes(cached["updated"]), int(now - cached["updated"] >= REFRESH),
              sunrise, sunset, next_rise,
              minutes(sunrise) if sunrise else None, minutes(sunset) if sunset else None]
    hourly = data["hourly"]
    forecasts = sorted(zip(*(hourly[field] for field in
                            ("time", "temperature_2m", "weather_code", "precipitation_probability", "is_day"))))
    forecasts = [row for row in forecasts if row[0] > now][:4]
    for stamp, temperature, code, probability, is_day in forecasts:
        values.extend((local_time(stamp).hour, temperature, code, probability, is_day))
    values.extend([None] * (30 - len(values)))
    # Only validated numbers enter Conky's parsed output; API text never becomes commands.
    return "${lua weather " + " ".join("-" if value is None else str(value) for value in values) + "}"


def main():
    now = time.time()
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "conky-weather"
    try:
        print(render(load_weather(cache_dir, now), now))
    except (OSError, ValueError, KeyError, TypeError, OverflowError):
        print("${lua weather}")


if __name__ == "__main__":
    main()
