The system, calendar, and Calgary weather panels start with `conky/run.sh`.

The system panel uses matching circular gauges for CPU, NVIDIA GPU, and RAM.
CPU/GPU temperatures appear inside their circles; RAM shows used/total memory
underneath. Storage and battery use vertical stacks of ten horizontal segments
below CPU activity. Without a battery, the storage stack is centered. CPU and
network activity histories retain their styles.

`telemetry.py` reads named CPU package sensors from Linux hwmon and queries the
first NVIDIA display adapter every five seconds with a two-second timeout.
Sleeping GPUs show `Sleep` and are not queried; unavailable readings show `--`.
NVIDIA readings require the distribution's matching driver and `nvidia-smi`;
install those through Mint Driver Manager or Ubuntu's driver tools. No driver
version or sensor index is pinned to this machine. Python and Conky's Lua/Cairo
support already come from `setup/apt.txt`; no extra Python packages are needed.

After pulling, use `./setup.sh apply --configs-only` and reload the system panel
to regenerate its themed runtime config. No logout is required.

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

Installation checks: run `./setup.sh check` from the repository root.
