-- Momentum card: tasks completed per day as a heat map, with today's count, this week's and the streak.
local ui = dofile(os.getenv('HOME') .. '/thomas_config/conky/panel.lua')
local c = ui.colors

-- 408 units wide, as sized in deck.lua. A column is a week, Sunday on top as in the calendar.
local WIDTH, LEFT, RIGHT = 408, 16, 392
local WEEKS, PITCH, CELL, TOP = 31, 11.5, 9, 52
local GRID = RIGHT - WEEKS * PITCH + PITCH - CELL
local counts, loaded

-- tasks.py prints one count per day, oldest first and ending today.
local function load()
    local pipe = io.popen('/usr/bin/python3 ' .. os.getenv('HOME') .. '/thomas_config/conky/tasks.py done 2>/dev/null')
    local output = pipe and pipe:read('*a') or ''
    if pipe then pipe:close() end
    counts = {}
    for count in output:gmatch('%d+') do counts[#counts + 1] = tonumber(count) end
end

-- Completed tasks `back` days ago.
local function completed(back)
    return counts[#counts - back] or 0
end

local function figure(context, x, value, label, color)
    local width = ui.text(context, tostring(value), x, 164, 17, value > 0 and color or c.muted, 0, true)
    ui.text(context, label, x + width + 6, 164, 10, c.muted)
end

function conky_draw_momentum()
    if not conky_window then return end
    -- Expose events redraw without new data; read Taskwarrior once per update.
    local update = conky_parse('${updates}')
    if loaded ~= update then
        loaded = update
        load()
    end
    local context, surface = ui.open(WIDTH)
    ui.section(context, 'Momentum', LEFT, 28, RIGHT)
    if #counts == 0 then
        ui.text(context, 'Taskwarrior unavailable', LEFT, 52, 10.5, c.muted)
        ui.close(context, surface)
        return
    end

    local now = os.date('*t')
    local weekday, peak = now.wday - 1, 1
    for back = 0, WEEKS * 7 - 1 do peak = math.max(peak, completed(back)) end
    for row, letter in pairs({[1] = 'M', [3] = 'W', [5] = 'F'}) do
        ui.text(context, letter, LEFT, TOP + row * PITCH + CELL - 1.5, 9, c.separator, 0, true)
    end
    -- Today sits in the last column; earlier days fill upward and then leftward.
    for back = 0, (WEEKS - 1) * 7 + weekday do
        local slot = (WEEKS - 1) * 7 + weekday - back
        local x, y = GRID + math.floor(slot / 7) * PITCH, TOP + slot % 7 * PITCH
        local day = os.date('*t', os.time{year = now.year, month = now.month, day = now.day - back, hour = 12})
        if day.day == 1 then
            ui.text(context, os.date('%b', os.time(day)), x, TOP - 7, 9, c.muted)
        end
        local count = completed(back)
        ui.rounded(context, x, y, CELL, CELL, 2.5)
        if count > 0 then
            -- Square root keeps ordinary days visible beside one very busy day.
            ui.color(context, c.primary, 0.25 + 0.75 * math.sqrt(count / peak))
        else
            ui.color(context, c.surface, 0.8)
        end
        cairo_fill(context)
        if back == 0 then
            ui.rounded(context, x - 1.5, y - 1.5, CELL + 3, CELL + 3, 4)
            cairo_set_line_width(context, 1)
            ui.color(context, c.text)
            cairo_stroke(context)
        end
    end

    local week, streak = 0, 0
    for back = 0, weekday do week = week + completed(back) end
    -- A day without a finished task ends the streak, but today only once it is over.
    local back = completed(0) > 0 and 0 or 1
    while completed(back) > 0 do streak, back = streak + 1, back + 1 end
    figure(context, LEFT, completed(0), 'done today', c.primary)
    figure(context, LEFT + 132, week, 'this week', c.text)
    figure(context, LEFT + 256, streak, 'day streak', c.warning)
    ui.close(context, surface)
end
