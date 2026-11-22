-- Year card: the twelve months as one line, filled up to today.
local ui = dofile(os.getenv('HOME') .. '/thomas_config/conky/panel.lua')
local c = ui.colors

-- 660 units wide, as sized in deck.lua; GAP separates the months' round-capped lines.
local WIDTH, LEFT, RIGHT, GAP = 660, 16, 644, 7

function conky_draw_year()
    if not conky_window then return end
    local context, surface = ui.open(WIDTH)
    local now = os.date('*t')
    local days = os.date('*t', os.time{year = now.year, month = 12, day = 31, hour = 12}).yday
    local stats = string.format('Week %d / day %d of %d / %d days left',
                                tonumber(os.date('%V')), now.yday, days, days - now.yday)
    ui.section(context, tostring(now.year), LEFT, 26, RIGHT - ui.text(context, stats, RIGHT, 26, 10, c.muted, 1) - 8)

    local span = (RIGHT - LEFT + GAP) / 12
    for month = 1, 12 do
        local x, width = LEFT + (month - 1) * span, span - GAP
        local length = os.date('*t', os.time{year = now.year, month = month + 1, day = 0, hour = 12}).day
        local done = month < now.month and 1 or month > now.month and 0 or (now.day - 1 + now.hour / 24) / length
        cairo_set_line_width(context, 3)
        ui.color(context, c.border, 0.6)
        ui.line(context, x, 44, x + width, 44)
        if done > 0 then
            ui.color(context, c.primary, month == now.month and 1 or 0.55)
            ui.line(context, x, 44, x + width * done, 44)
        end
        if month == now.month then
            ui.glow(context, x + width * done, 44, 8, c.primary)
            ui.color(context, c.text)
            cairo_new_path(context)
            cairo_arc(context, x + width * done, 44, 2.2, 0, 2*math.pi)
            cairo_fill(context)
        end
        ui.text(context, os.date('%b', os.time{year = now.year, month = month, day = 1, hour = 12}), x + width / 2, 59, 9.5,
                month == now.month and c.primary or month < now.month and c.separator or c.muted, 0.5, month == now.month)
    end
    ui.close(context, surface)
end
