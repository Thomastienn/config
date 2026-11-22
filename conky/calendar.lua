-- Agenda card: Taskwarrior's most urgent tasks beside four months of due dates.
local ui = dofile(os.getenv('HOME') .. '/thomas_config/conky/panel.lua')
local c = ui.colors

-- 592 units wide, as sized in deck.lua: tasks up to SPLIT, then two columns of months.
local WIDTH, LEFT, SPLIT, RIGHT = 592, 16, 250, 576
local CELL, ROW, PITCH = 21, 13, 110
local due, tasks, loaded = {}, nil, nil

-- tasks.py prints plain fields that only Cairo draws, so task text never becomes Conky commands.
local function load()
    local pipe = io.popen('/usr/bin/python3 ' .. os.getenv('HOME') .. '/thomas_config/conky/tasks.py 2>/dev/null')
    local output = pipe and pipe:read('*a') or ''
    if pipe then pipe:close() end
    local days, rows = output:match('^([^\n]*)\n(.*)$')
    due, tasks = {}, days and {}
    for day in (days or ''):gmatch('%d+') do due[day] = true end
    for line in (rows or ''):gmatch('[^\n]+') do
        tasks[#tasks + 1] = {line:match('^(%S+)\t([^\t]*)\t(.*)$')}
    end
end

-- Filled marks today; outlined marks a due date.
local function pill(context, x, y, width, height, color, filled)
    ui.rounded(context, x, y, width, height, height/2)
    ui.color(context, color)
    if filled then
        cairo_fill(context)
    else
        cairo_set_line_width(context, 1)
        cairo_stroke(context)
    end
end

-- One task: the mark its day carries in the calendar, the description, then when it is due.
local function task(context, y, row, today)
    local day, label, text = row[1], row[2], row[3]
    local family = ui.family(text)
    if day == '-' then
        ui.color(context, c.separator)
        cairo_new_path(context)
        cairo_arc(context, LEFT + 5.5, y - 3.5, 1.8, 0, 2*math.pi)
        cairo_fill(context)
        ui.text(context, text, LEFT + 18, y, 10.5, c.muted, 0, false, family)
        return
    end
    local color = day == today and c.warning or day < today and c.error or c.secondary
    pill(context, LEFT, y - 7.5, 11, 7, color, day == today)
    ui.text(context, text, LEFT + 18, y, 10.5, c.text, 0, false, family)
    ui.text(context, label, SPLIT, y, 10, color, 1, true)
end

local function month(context, x, y, first, today)
    local stamp = os.time(first)
    local width = ui.text(context, os.date('%B', stamp), x + 4, y, 10.5,
                          os.date('%Y%m', stamp) == today:sub(1, 6) and c.primary or c.text, 0, true)
    ui.text(context, os.date('%Y', stamp), x + 9 + width, y, 9.5, c.muted)
    for column, letter in ipairs({'S', 'M', 'T', 'W', 'T', 'F', 'S'}) do
        ui.text(context, letter, x + (column - 0.5) * CELL, y + 14, 9, c.separator, 0.5, true)
    end
    local days = os.date('*t', os.time{year = first.year, month = first.month + 1, day = 0, hour = 12}).day
    for day = 1, days do
        local slot = first.wday + day - 2
        local middle, baseline = x + (slot % 7 + 0.5) * CELL, y + 29 + math.floor(slot / 7) * ROW
        local key = string.format('%04d%02d%02d', first.year, first.month, day)
        local color = c.text
        if key == today then
            pill(context, middle - 9.5, baseline - 9.5, 19, 13, due[key] and c.warning or c.primary, true)
            color = c.background
        elseif due[key] then
            color = key < today and c.error or c.secondary
            pill(context, middle - 9.5, baseline - 9.5, 19, 13, color)
        elseif key < today then
            color = c.separator
        elseif slot % 7 == 0 or slot % 7 == 6 then
            color = c.muted
        end
        ui.text(context, tostring(day), middle, baseline, 10, color, 0.5, key == today)
    end
end

function conky_draw_calendar()
    if not conky_window then return end
    -- Expose events redraw without new data; read Taskwarrior once per update.
    local update = conky_parse('${updates}')
    if loaded ~= update then
        loaded = update
        load()
    end
    local context, surface = ui.open(WIDTH)
    local today = os.date('%Y%m%d')
    ui.section(context, 'Upcoming', LEFT, 28, SPLIT)
    if not tasks or #tasks == 0 then
        ui.text(context, tasks and 'No pending tasks' or 'Taskwarrior unavailable', LEFT, 52, 10.5, c.muted)
    end
    for index, row in ipairs(tasks or {}) do task(context, 34.5 + index * 17.5, row, today) end

    local months = SPLIT + 20
    ui.section(context, 'Calendar', months, 28, RIGHT)
    local now = os.date('*t')
    for offset = 0, 3 do
        local first = os.date('*t', os.time{year = now.year, month = now.month + offset, day = 1, hour = 12})
        month(context, months + (offset % 2) * (7 * CELL + 12), 48 + math.floor(offset / 2) * PITCH, first, today)
    end
    ui.close(context, surface)
end
