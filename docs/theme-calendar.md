# Special-date desktop themes

`themes/calendar.toml` is the shared registry. i3 starts
`thomas-theme-calendar.service` once at login. It does not poll or run again on
resume or i3 reload. It uses the desktop's local date, not Vietnam time.
Setup disables and backs up the old fifteen-minute timer when upgrading.
No downloads or extra packages are needed (Python 3.11 and systemd already required).

```sh
theme calendar                         # show today's winner without changing anything
theme calendar --date 2026-12-20       # preview any date
theme auto                             # apply today's winner now
systemctl --user status thomas-theme-calendar.service
```

Every entry names a complete theme file, a date rule, `before` and `after`
(inclusive calendar days), and `priority`. Highest priority wins, then nearest
event date, then registry order. Cozy Mint returns outside event windows.
Christmas wins December 11–25, Boxing Day December 26, New Year December 27–January 2.
Halloween starts fourteen days early, Tet fourteen days early through day seven.
Vietnamese Women’s Day takes precedence October 19–20; Halloween resumes
afterward. Most smaller events start zero or one day early. Edit each window freely.

Each of the 38 enabled holiday events has its own complete preset and distinct palette.
Cozy Mint is used only as the fallback outside event windows. Event presets color
the desktop and terminal, with matching installed Mint-Y GTK accents. They share
Cozy Mint's calibration: a near-neutral dark background with a slight event tint,
quiet muted text and soft pastel accents in the event's hues. Layout,
fonts, icons, cursor and wallpaper stay unchanged. Edit the complete preset for
further customization. Overlapping events still select just one winner.
The normal theme engine renders templates into local generated state and reloads
supported apps. Automatic switching also updates `themes/active`, just like
`theme apply FILE`; it never commits or pushes. Existing browser/shell reload
limitations from [desktop themes](desktop.md#desktop-themes) still apply.
A manual selection lasts until the next login or `theme auto`; disable automation to keep it.
If a date changes while logged in, the theme stays until the next login or `theme auto`.

## Local birthdays and anniversaries

Disabled birthday and anniversary examples at the bottom of
`themes/calendar.toml` show the available theme files. Leave those shared
examples disabled. Setup creates the Git-ignored `local/theme-calendar.toml`
from [themes/calendar.example](../themes/calendar.example) when missing and
prints a reminder to configure it. Existing local files are never overwritten.

Edit `local/theme-calendar.toml` directly: replace each sample `date = "01-01"`
with your `MM-DD` and set `enabled = true` on that event. Birthday and anniversary
use separate presets and priority 100. Adjust `before` and `after` for each event.
Changes take effect at the next login or with `theme auto`;
no setup rerun is needed after editing. Keep the local file to retain your dates.

Local events append to the shared registry; disabled shared examples are skipped.
Top-level local settings override shared defaults. Set `enabled = false` on an
event to skip it, or at the top of the local file to stop automatic switching.
The login check respects that setting. Cozy Mint remains the fallback.

Use exactly one rule per event:
`date = "MM-DD"` repeats annually;
`dates = ["2027-02-06"]` lists actual civil dates;
`weekday = [5, 6, 2]` means second Sunday of May (Monday=0).
February 29 repeats only in leap years.

## Coverage and date maintenance

Included: New Year, Christmas, Halloween, Valentine, family days, Earth/Peace
days, Canadian occasions, Vietnamese fixed holidays and cultural observances,
Tet, Hung Kings, Vesak, Doan Ngo, Vu Lan and Mid-Autumn. This is a curated
calendar, not every country's holidays; add other occasions using the same schema.

Lunar entries contain explicit **2026–2027** dates, avoiding incorrect Chinese
calendar conversions for Vietnam. Add verified Gregorian dates before 2028;
missing years skip those events while annual events continue. Dates describe the
festival itself, not government compensatory days off.

Sources checked November 7, 2026:
[Vietnam festival calendar](https://www.vietnamtourism.com/en/the-vietnamese-festival-calendar-month-by-month),
[2027 Vietnam dates](https://www.timeanddate.com/holidays/vietnam/2027).
The latter gives Hung Kings 2027 as April 16; that date takes precedence over
the conflicting April 15 in the festival guide. Verify future lunar dates against
Vietnam-specific calendars before adding them.

## Google Calendar cross-check

Checked subscribed `en.vietnamese#holiday@group.v.calendar.google.com` and
`vi.canadian#holiday@group.v.calendar.google.com` for all of 2026–2027 on
November 7, 2026. These are public holiday feeds; no personal events were read.
Confirmed Tet and Hung Kings against the feed and added St Patrick's Day,
Good Friday, Easter (through Easter Monday), Victoria Day, National Indigenous
Peoples Day, Alberta Heritage Day, Canadian Labour Day, Truth and Reconciliation,
and Boxing Day. Higher-priority commemorations take precedence over festive overlaps.

The feed contains regional holidays and substitute days off; the registry uses
actual occasion dates rather than duplicating every day off. Family Day was
absent from the returned Canadian feed, so this cross-check cannot verify it.
Vietnam's feed omits Mid-Autumn, Vu Lan, Doan Ngo and Vesak; their separately
sourced dates remain. This is a one-time cross-check, not a runtime Google
Calendar connection. The login check reads the local registry.
Movable Good Friday, Easter and Victoria Day entries also need dates added
for 2028 onward.

## Event palettes

Colors describe the design choice, not an official color standard. Every row
points to a separate editable preset.

| Event | Preset | Palette |
| --- | --- | --- |
| New Year | [new-year.toml](../themes/new-year.toml) | Midnight blue, champagne gold, ice blue |
| Valentine | [valentine.toml](../themes/valentine.toml) | Wine, rose pink, soft blush |
| International Women Day | [international-women-day.toml](../themes/international-women-day.toml) | Violet, lilac, gold |
| Earth Day | [earth-day.toml](../themes/earth-day.toml) | Forest green, leaf green, river blue |
| Vietnam Reunification | [vietnam-reunification.toml](../themes/vietnam-reunification.toml) | Deep red, coral red, flag gold |
| International Labour Day | [international-labour-day.toml](../themes/international-labour-day.toml) | Iron brown, brick, brass |
| Vietnam Children Day | [vietnam-children-day.toml](../themes/vietnam-children-day.toml) | Pool blue, sunshine yellow, aqua |
| Canada Day | [canada-day.toml](../themes/canada-day.toml) | Maple red and warm white |
| Vietnam War Invalids and Martyrs Day | [vietnam-martyrs-day.toml](../themes/vietnam-martyrs-day.toml) | Quiet earth, incense gold, muted red |
| Vietnam National Day | [vietnam-national-day.toml](../themes/vietnam-national-day.toml) | Flag gold and red on dark ochre |
| Vietnam Women Day | [vietnam-women-day.toml](../themes/vietnam-women-day.toml) | Lotus pink and sage |
| Halloween | [halloween.toml](../themes/halloween.toml) | Pumpkin orange and violet |
| Remembrance Day | [remembrance.toml](../themes/remembrance.toml) | Poppy red and stone on charcoal wine |
| Vietnam Teachers Day | [vietnam-teachers-day.toml](../themes/vietnam-teachers-day.toml) | Chalk green and ochre |
| Vietnam Culture Day | [vietnam-culture-day.toml](../themes/vietnam-culture-day.toml) | Lacquer brown, antique gold, jade |
| Christmas | [christmas.toml](../themes/christmas.toml) | Evergreen, holly red, warm white |
| International Peace Day | [international-peace-day.toml](../themes/international-peace-day.toml) | Sky blue and olive white |
| International Family Day | [international-family-day.toml](../themes/international-family-day.toml) | Warm terracotta and sage |
| Vietnam Family Day | [vietnam-family-day.toml](../themes/vietnam-family-day.toml) | Lacquer plum and warm amber |
| Mother Day | [mother-day.toml](../themes/mother-day.toml) | Carnation pink and lilac |
| Father Day | [father-day.toml](../themes/father-day.toml) | Indigo and leather tan |
| Canada Thanksgiving | [canada-thanksgiving.toml](../themes/canada-thanksgiving.toml) | Maple gold and harvest sage |
| US Thanksgiving | [us-thanksgiving.toml](../themes/us-thanksgiving.toml) | Russet and corn gold |
| Tet Nguyen Dan | [tet.toml](../themes/tet.toml) | Apricot gold and lucky red |
| Hung Kings Commemoration | [hung-kings.toml](../themes/hung-kings.toml) | Bronze and temple green |
| Tet Doan Ngo | [tet-doan-ngo.toml](../themes/tet-doan-ngo.toml) | Plum purple and rice gold |
| Vu Lan | [vu-lan.toml](../themes/vu-lan.toml) | White rose and muted rose pink |
| Mid Autumn | [mid-autumn.toml](../themes/mid-autumn.toml) | Moonlit navy, lantern amber, peach |
| Vesak | [vesak.toml](../themes/vesak.toml) | Saffron gold and pale lotus |
| St Patrick Day | [st-patrick-day.toml](../themes/st-patrick-day.toml) | Shamrock green and gold |
| Good Friday | [good-friday.toml](../themes/good-friday.toml) | Quiet violet and stone |
| Easter | [easter.toml](../themes/easter.toml) | Lavender and primrose yellow |
| Victoria Day | [victoria-day.toml](../themes/victoria-day.toml) | Royal plum and gold |
| National Indigenous Peoples Day | [indigenous-peoples-day.toml](../themes/indigenous-peoples-day.toml) | Earth and summer sage; no borrowed sacred motifs |
| Alberta Heritage Day | [alberta-heritage-day.toml](../themes/alberta-heritage-day.toml) | Prairie sky blue and wheat gold |
| Canada Labour Day | [canada-labour-day.toml](../themes/canada-labour-day.toml) | Steel blue and copper |
| National Day for Truth and Reconciliation | [truth-and-reconciliation.toml](../themes/truth-and-reconciliation.toml) | Orange and quiet linen |
| Boxing Day | [boxing-day.toml](../themes/boxing-day.toml) | Ice blue and silver lilac |
| Birthday | [birthday.toml](../themes/birthday.toml) | Periwinkle and confetti pink |
| Anniversary | [anniversary.toml](../themes/anniversary.toml) | Rose and champagne gold |
