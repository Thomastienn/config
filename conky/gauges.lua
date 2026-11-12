-- System panel, drawn entirely in Cairo; system.conf only polls telemetry.py.
local ui = dofile(os.getenv('HOME') .. '/thomas_config/conky/panel.lua')
local c = ui.colors

-- 240 units of content inside 12 units of padding, as sized in system.conf.
local WIDTH, LEFT, RIGHT = 266, 14, 252
-- At one-second updates, 61 readings span one minute.
local SLOTS = 61
-- First interface that is up wins; the flag marks wireless.
local INTERFACES = {{'wlo1', true}, {'enp55s0', false}}

local telemetry = {}
local histories = {cpu = {}, download = {}, upload = {}}
local sampled, interface

function conky_telemetry(cpu_temperature, gpu_usage, gpu_temperature)
    telemetry.cpu_temperature = tonumber(cpu_temperature)
    telemetry.gpu_usage = tonumber(gpu_usage)
    telemetry.gpu_temperature = tonumber(gpu_temperature)
    telemetry.sleeping = gpu_usage == 'sleep'
    return ''
end

local function parse(variable)
    return conky_parse('${' .. variable .. '}')
end

local function record(name, reading)
    local values = histories[name]
    values[#values + 1] = math.max(0, tonumber(reading) or 0)
    if #values > SLOTS then table.remove(values, 1) end
end

local function clock(context)
    local width = ui.text(context, os.date('%H'), LEFT, 60, 54, c.primary, 0, true)
    width = width + ui.text(context, ':', LEFT + width, 56, 54, c.separator, 0, true)
    ui.text(context, os.date('%M'), LEFT + width, 60, 54, c.text, 0, true)
    ui.text(context, os.date('%A'), RIGHT, 30, 11, c.primary, 1, true)
    ui.text(context, tonumber(os.date('%d')) .. ' ' .. os.date('%B'), RIGHT, 45, 11, c.text, 1)
    ui.text(context, os.date('%Y'), RIGHT, 59, 9, c.muted, 1)
    -- The day so far, midnight to midnight.
    local now = os.date('*t')
    local tip = LEFT + (RIGHT - LEFT) * (now.hour * 3600 + now.min * 60 + now.sec) / 86400
    cairo_set_line_width(context, 2)
    ui.color(context, c.border, 0.6)
    cairo_new_path(context)
    cairo_move_to(context, LEFT, 78)
    cairo_line_to(context, RIGHT, 78)
    cairo_stroke(context)
    ui.fade(context, tip, 78, LEFT, 78, c.primary)
    ui.glow(context, tip, 78, 8, c.primary)
    ui.color(context, c.text)
    cairo_arc(context, tip, 78, 2.2, 0, 2*math.pi)
    cairo_fill(context)
end

-- Three-quarter ring, open at the bottom where the label sits.
local function gauge(context, x, y, value, color, reading, detail, label)
    local radius, start, sweep = 32, 0.75*math.pi, 1.5*math.pi
    cairo_set_line_width(context, 4)
    ui.color(context, c.border, 0.6)
    cairo_new_path(context)
    cairo_arc(context, x, y, radius, start, start + sweep)
    cairo_stroke(context)
    if value and value > 0 then
        local finish = start + sweep * math.min(value, 100)/100
        local stroke = cairo_pattern_create_linear(x - radius, 0, x + radius, 0)
        cairo_pattern_add_color_stop_rgba(stroke, 0, color[1], color[2], color[3], 0.45)
        cairo_pattern_add_color_stop_rgba(stroke, 1, color[1], color[2], color[3], 1)
        cairo_set_source(context, stroke)
        cairo_new_path(context)
        cairo_arc(context, x, y, radius, start, finish)
        cairo_stroke(context)
        cairo_pattern_destroy(stroke)
        local tip_x, tip_y = x + radius * math.cos(finish), y + radius * math.sin(finish)
        ui.glow(context, tip_x, tip_y, 9, color)
        ui.color(context, c.text)
        cairo_new_path(context)
        cairo_arc(context, tip_x, tip_y, 2, 0, 2*math.pi)
        cairo_fill(context)
    end
    ui.text(context, reading, x, y + 3, 15, c.text, 0.5, true)
    ui.text(context, detail, x, y + 16, 8.5, c.muted, 0.5)
    ui.text(context, label, x, y + radius + 4, 9, color, 0.5, true)
end

-- Mirrored bars, newest on the right; empty slots stay as dots while the minute fills.
local function waveform(context, values, y)
    local step = (RIGHT - LEFT) / (SLOTS - 1)
    cairo_set_line_width(context, 2.2)
    for slot = 1, SLOTS do
        local value = values[slot - SLOTS + #values]
        local x = LEFT + step * (slot - 1)
        local half = value and 1 + 11 * math.sqrt(math.min(value, 100)/100) or 0
        if value then ui.color(context, c.primary, 0.35 + 0.65 * math.min(value, 100)/100)
        else ui.color(context, c.border, 0.6) end
        cairo_new_path(context)
        cairo_move_to(context, x, y - half)
        cairo_line_to(context, x, y + half)
        cairo_stroke(context)
    end
end

-- Labelled row of rounded segments.
local function segments(context, x, width, y, label, variable, color)
    local value = tonumber(parse(variable))
    ui.text(context, label, x, y, 10, c.muted)
    ui.text(context, value and string.format('%.0f%%', value) or '--', x + width, y, 10, c.text, 1, true)
    local count = math.floor(width / 9.5)
    local span = (width + 2) / count
    for index = 0, count - 1 do
        local fraction = value and math.min(1, math.max(0, value/100 * count - index)) or 0
        ui.rounded(context, x + index * span, y + 7, span - 2, 4, 2)
        ui.color(context, c.border, 0.6)
        cairo_fill(context)
        if fraction > 0 then
            ui.rounded(context, x + index * span, y + 7, math.max(4, (span - 2) * fraction), 4, 2)
            ui.color(context, color)
            cairo_fill(context)
        end
    end
end

-- Area plot on fixed slots; a negative height hangs it below the baseline.
local function area(context, values, baseline, height, color)
    if #values < 2 then return end
    local maximum = 1
    for _, value in ipairs(values) do maximum = math.max(maximum, value) end
    local step = (RIGHT - LEFT) / (SLOTS - 1)
    local first = LEFT + step * (SLOTS - #values)
    cairo_new_path(context)
    for index, value in ipairs(values) do
        cairo_line_to(context, first + step * (index - 1), baseline - height * value / (maximum * 1.15))
    end
    cairo_set_line_width(context, 1.4)
    ui.color(context, color)
    cairo_stroke_preserve(context)
    cairo_line_to(context, RIGHT, baseline)
    cairo_line_to(context, first, baseline)
    cairo_close_path(context)
    local fill = cairo_pattern_create_linear(0, baseline - height, 0, baseline)
    cairo_pattern_add_color_stop_rgba(fill, 0, color[1], color[2], color[3], 0.4)
    cairo_pattern_add_color_stop_rgba(fill, 1, color[1], color[2], color[3], 0.03)
    cairo_set_source(context, fill)
    cairo_fill(context)
    cairo_pattern_destroy(fill)
end

local function network(context, y)
    ui.section(context, 'Network', LEFT, y, RIGHT)
    if not interface then
        ui.text(context, 'Offline', LEFT, y + 22, 11.5, c.muted)
        return
    end
    local name, wireless = interface[1], interface[2]
    ui.text(context, wireless and parse('wireless_essid ' .. name) or 'Wired', LEFT, y + 22, 11.5, c.text)
    if wireless then
        local quality = tonumber(parse('wireless_link_qual_perc ' .. name)) or 0
        for bar = 1, 4 do
            ui.color(context, c.primary, quality > (bar - 1) * 25 and 1 or 0.25)
            ui.rounded(context, RIGHT - 20 + bar * 5 - 3, y + 22 - bar * 2.5, 3, bar * 2.5, 1)
            cairo_fill(context)
        end
        ui.text(context, string.format('%.0f%%', quality), RIGHT - 24, y + 22, 9, c.muted, 1)
    else
        ui.text(context, 'Connected', RIGHT, y + 22, 9, c.muted, 1)
    end
    local axis = y + 90
    for _, flow in ipairs({{'Down', 'downspeed', 'download', c.primary, 1, 0},
                           {'Up', 'upspeed', 'upload', c.secondary, -1, 1}}) do
        local edge = flow[6] == 0 and LEFT or RIGHT
        local width = ui.text(context, flow[1], edge, y + 42, 9, c.muted, flow[6])
        ui.text(context, parse(flow[2] .. ' ' .. name) .. '/s', edge + (width + 6) * flow[5], y + 42, 10,
                flow[4], flow[6], true)
        area(context, histories[flow[3]], axis, 32 * flow[5], flow[4])
    end
    cairo_set_line_width(context, 1)
    ui.color(context, c.border, 0.7)
    cairo_new_path(context)
    cairo_move_to(context, LEFT, axis)
    cairo_line_to(context, RIGHT, axis)
    cairo_stroke(context)
end

local function processes(context, y)
    ui.section(context, 'Processes', LEFT, y, RIGHT)
    local busiest = math.max(1, tonumber(parse('top cpu 1')) or 0)
    cairo_set_line_width(context, 1.5)
    for index = 1, 5 do
        local row = y + 1 + index * 21
        local usage = tonumber(parse('top cpu ' .. index)) or 0
        ui.text(context, (parse('top name ' .. index):gsub('%s+$', '')), LEFT, row, 11,
                index == 1 and c.text or c.muted)
        ui.text(context, string.format('%.1f%%', usage), RIGHT, row, 11, c.text, 1, index == 1)
        ui.color(context, c.border, 0.4)
        cairo_new_path(context)
        cairo_move_to(context, LEFT, row + 6)
        cairo_line_to(context, RIGHT, row + 6)
        cairo_stroke(context)
        if usage > 0 then
            ui.color(context, c.primary, 1.1 - index * 0.15)
            cairo_new_path(context)
            cairo_move_to(context, LEFT, row + 6)
            cairo_line_to(context, LEFT + (RIGHT - LEFT) * usage / busiest, row + 6)
            cairo_stroke(context)
        end
    end
end

function conky_gauges()
    local update = tonumber(conky_parse('${updates}')) or 0
    if not conky_window or update < 2 then return end
    -- Expose events redraw without a new reading; sample once per update.
    if sampled ~= update then
        sampled = update
        local current
        for _, candidate in ipairs(INTERFACES) do
            if not current and conky_parse('${if_up ' .. candidate[1] .. '}1${endif}') == '1' then
                current = candidate
            end
        end
        if current ~= interface then histories.download, histories.upload = {}, {} end
        interface = current
        record('cpu', parse('cpu cpu0'))
        if interface then
            record('download', parse('downspeedf ' .. interface[1]))
            record('upload', parse('upspeedf ' .. interface[1]))
        end
    end

    local context, surface, height = ui.open(WIDTH)
    clock(context)

    ui.section(context, 'System', LEFT, 106, RIGHT)
    local ram = tonumber(parse('memperc'))
    local function percent(value) return value and string.format('%.0f%%', value) or '--' end
    local function degrees(value) return value and string.format('%.0f°C', value) or '--°C' end
    gauge(context, 53, 156, histories.cpu[#histories.cpu], c.primary,
          percent(histories.cpu[#histories.cpu]), degrees(telemetry.cpu_temperature), 'CPU')
    gauge(context, 133, 156, telemetry.gpu_usage, c.warning,
          telemetry.sleeping and 'Sleep' or percent(telemetry.gpu_usage),
          degrees(telemetry.gpu_temperature), 'GPU')
    gauge(context, 213, 156, ram, c.secondary, percent(ram), parse('mem'), 'RAM')

    ui.text(context, 'CPU activity', LEFT, 218, 9, c.muted)
    local span = math.min(60, #histories.cpu - 1)
    ui.text(context, span < 1 and 'live' or ('last ' .. span .. 's'), RIGHT, 218, 9, c.muted, 1)
    waveform(context, histories.cpu, 238)

    if conky_parse('${if_existing /sys/class/power_supply/BAT0}1${endif}') == '1' then
        segments(context, LEFT, 110, 274, 'Storage', 'fs_used_perc /', c.secondary)
        segments(context, RIGHT - 110, 110, 274, 'Battery', 'battery_percent', c.primary)
    else
        segments(context, LEFT, RIGHT - LEFT, 274, 'Storage', 'fs_used_perc /', c.secondary)
    end

    network(context, 316)
    processes(context, 472)

    cairo_set_line_width(context, 1)
    ui.fade(context, LEFT, height - 34, RIGHT, height - 34, c.separator)
    ui.text(context, 'Uptime', LEFT, height - 17, 9, c.muted)
    ui.text(context, parse('uptime_short'), RIGHT, height - 17, 9, c.text, 1)
    ui.close(context, surface)
end
