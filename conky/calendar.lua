-- Calendar panel: six months of Taskwarrior due dates, anchored to the bottom edge.
local ui = dofile(os.getenv('HOME') .. '/thomas_config/conky/panel.lua')
local c = ui.colors

-- 330 units of content inside 12 units of padding, as sized in calendar.conf.
local WIDTH, LEFT, RIGHT = 356, 14, 342
local CELL, ROW, PITCH = 22, 13, 114
-- Heading, three rows of months, legend; calendar.conf reserves the same space below the tasks.
local HEIGHT = 382
local due = {}

function conky_calendar(...)
    due = {}
    for _, day in ipairs({...}) do due[day] = true end
    return ''
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

local function month(context, x, y, first, today)
    local stamp = os.time(first)
    local width = ui.text(context, os.date('%B', stamp), x + 4, y, 10.5,
                          os.date('%Y%m', stamp) == today:sub(1, 6) and c.primary or c.text, 0, true)
    ui.text(context, os.date('%Y', stamp), x + 9 + width, y, 9, c.muted)
    for column, letter in ipairs({'S', 'M', 'T', 'W', 'T', 'F', 'S'}) do
        ui.text(context, letter, x + (column - 0.5) * CELL, y + 15, 8.5, c.separator, 0.5, true)
    end
    local days = os.date('*t', os.time{year = first.year, month = first.month + 1, day = 0, hour = 12}).day
    for day = 1, days do
        local slot = first.wday + day - 2
        local middle, baseline = x + (slot % 7 + 0.5) * CELL, y + 31 + math.floor(slot / 7) * ROW
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
        ui.text(context, tostring(day), middle, baseline, 9.5, color, 0.5, key == today)
    end
end

function conky_draw_calendar()
    if not conky_window then return end
    local context, surface, height = ui.open(WIDTH)
    ui.section(context, 'Upcoming', LEFT, 26, RIGHT)
    local top = height - 12 - HEIGHT
    ui.section(context, 'Calendar', LEFT, top + 10, RIGHT)
    local now = os.date('*t')
    for offset = 0, 5 do
        local first = os.date('*t', os.time{year = now.year, month = now.month + offset, day = 1, hour = 12})
        month(context, LEFT + (offset % 2) * (7 * CELL + 20), top + 32 + math.floor(offset / 2) * PITCH,
              first, os.date('%Y%m%d'))
    end
    local x = LEFT + 4
    for _, item in ipairs({{'Today', c.primary, true}, {'Due', c.secondary}, {'Due today', c.warning, true},
                           {'Overdue', c.error}}) do
        pill(context, x, top + HEIGHT - 9, 13, 8, item[2], item[3])
        x = x + 32 + ui.text(context, item[1], x + 18, top + HEIGHT - 2, 9, c.muted)
    end
    ui.close(context, surface)
end
