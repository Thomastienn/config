The Calgary weather widget starts automatically with `conky/run.sh`.

Weather data comes from [Open-Meteo](https://open-meteo.com/), under
[CC BY 4.0](https://open-meteo.com/en/licence). Personal use needs no account,
API key, or subscription.

`weather.py` fetches one response every 15 minutes and caches it in
`${XDG_CACHE_HOME:-~/.cache}/conky-weather`. Failed requests preserve previous
readings and wait 15 minutes before retrying. The footer marks stale readings
as cached. Forecast percentages mean precipitation chance, including snow.

Temperatures use Celsius. Calgary coordinates and timezone live near the top
of `weather.py`. The daylight marker moves using the local clock, without
extra API requests.

Checks: `python3 conky/test_weather.py` and `lua conky/test-weather.lua`.
