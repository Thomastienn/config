Eight cards sit around the wallpaper's character, where it leaves room: time
and weather, the week forecast, now playing and the next 24 hours on the left
(the last one covers the tail); the year above the head; system, momentum and
agenda on the right. `conky/run.sh` starts them.

`deck.lua` places and sizes the cards from the primary monitor's width, not from
`Xft.dpi`, so they stay put at any zoom: text is 1.33 px per unit on a 1920 px
screen. To move or resize, change the places, unit count and card sizes there
and the matching `WIDTH` in each card's Lua file. All cards are drawn with
Lua/Cairo and share one look from `panel.lua`: a soft glow from the top, a
hairline edge, and headings with fading rules.

- Time and weather (`weather.lua`, `weather.conf`): clock and date over a
  midnight-to-midnight line whose warm span is today's daylight; current Calgary
  conditions; each forecast hour sits on a card whose bar is the precipitation
  chance.
- Week (`weather.lua`, `forecast.conf`): seven days of lows and highs from the
  same cached response. Each day's bar is its span on the week's range, lavender
  at the cold end and amber at the warm end.
- Next 24 hours (`weather.lua`, `hours.conf`): three lanes on the same hours,
  each naming its peak: the temperature curve (warmest and coldest hour), a bar
  per hour for the precipitation chance, and the wind speed in km/h.
- Year (`year.lua`, `year.conf`): the twelve months as one line filled up to
  today, with the week, day of the year and days left.
- Now playing (`playing.lua`, `playing.conf`): the first MPRIS player's title,
  artist and progress, asked from `playerctl` every two seconds.
- Momentum (`momentum.lua`, `momentum.conf`): tasks completed per day over 31
  weeks as a heat map, from `tasks.py done`, with today ringed; counts for
  today, this week and the streak of days with a finished task. Today breaks
  the streak only once it is over.
- Agenda (`calendar.lua`, `calendar.conf`): Taskwarrior's twelve most urgent
  tasks beside four months. `tasks.py` feeds both once a minute. A task and its
  day carry the same mark: filled for today, outlined for a due date, red when
  overdue. Tasks show days until due and the date; past days are dimmed. Tasks
  tagged `nocal` stay off the calendar, waiting tasks off the list. Vietnamese
  task text falls back to Lato.
- System (`gauges.lua`, `system.conf`): three-quarter rings for CPU, NVIDIA GPU,
  and RAM with temperatures and used memory inside; a mirrored one-minute CPU
  waveform; segmented storage and battery bars (storage spans the column without
  a battery); download above and upload below one axis, each on its own scale;
  the five busiest processes. Network interface names live near the top of the
  file.

`telemetry.py` reads named CPU package sensors from Linux hwmon and queries the
first NVIDIA display adapter every five seconds with a two-second timeout.
Sleeping GPUs show `Sleep` and are not queried; unavailable readings show `--`.
NVIDIA readings require the distribution's matching driver and `nvidia-smi`;
install those through Mint Driver Manager or Ubuntu's driver tools. No driver
version or sensor index is pinned to this machine. Python and Conky's Lua/Cairo
support already come from `setup/apt.txt`; no extra Python packages are needed.

After pulling, use `./setup.sh apply --configs-only`. Changed themes refresh only
the panels already running, respecting Battery Saver. Colors and fonts come from
the selected `themes/*.toml` preset, including Lua gauges and calendar/task text.
Use `theme apply` to reapply it without logging out.

Weather data comes from [Open-Meteo](https://open-meteo.com/), under
[CC BY 4.0](https://open-meteo.com/en/licence). Personal use needs no account,
API key, or subscription.

`weather.py` fetches one response every 15 minutes and caches it in
`${XDG_CACHE_HOME:-~/.cache}/conky-weather`. Failed requests preserve previous
readings and wait 15 minutes before retrying. The footer marks stale readings
as cached. Forecast percentages mean precipitation chance, including snow.

Temperatures use Celsius. Calgary coordinates and timezone live near the top
of `weather.py`. The marker on the day line moves using the local clock, without
extra API requests.

Installation checks: run `./setup.sh check` from the repository root.
