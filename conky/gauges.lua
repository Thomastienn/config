require('cairo')

local metrics = {
    {label = 'CPU', variable = '${cpu cpu0}', color = {167/255, 204/255, 174/255}},
    {label = 'GPU', color = {222/255, 194/255, 138/255}},
    {label = 'RAM', variable = '${memperc}', color = {192/255, 175/255, 213/255}},
}

local telemetry = {}

function conky_telemetry(cpu_temperature, gpu_usage, gpu_temperature)
    telemetry.cpu_temperature = tonumber(cpu_temperature)
    telemetry.gpu_usage = tonumber(gpu_usage)
    telemetry.gpu_temperature = tonumber(gpu_temperature)
    telemetry.sleeping = gpu_usage == 'sleep'
    return ''
end

local histories = {
    cpu = {height = 24, y = 248, color = metrics[1].color, values = {}},
    download = {height = 22, bottom = 230, color = metrics[1].color, values = {}},
    upload = {height = 22, bottom = 173, color = metrics[3].color, values = {}},
}

function conky_history(name, variable, argument)
    local history = histories[name]
    local query = '${' .. variable .. ' ' .. argument .. '}'
    local update = tonumber(conky_parse('${updates}')) or 0
    if history.variable ~= query or (history.requested and update - history.requested > 1) then
        history.values, history.last_update = {}, nil
    end
    history.variable, history.requested = query, update
    return ''
end

function conky_history_span()
    local seconds = math.min(60, math.max(0, (tonumber(conky_parse('${updates}')) or 0) - 1))
    return seconds == 0 and 'live' or ('last ' .. seconds .. 's')
end

local function centered_text(context, text, x, y, size, weight)
    cairo_select_font_face(context, 'ComicShannsMono Nerd Font', CAIRO_FONT_SLANT_NORMAL, weight)
    cairo_set_font_size(context, size)
    local extents = cairo_text_extents_t:create()
    cairo_text_extents(context, text, extents)
    cairo_move_to(context, x - extents.width/2 - extents.x_bearing,
                  y - extents.height/2 - extents.y_bearing)
    cairo_show_text(context, text)
end

function conky_gauges()
    local update = tonumber(conky_parse('${updates}')) or 0
    if not conky_window or update < 2 then return end
    local window = conky_window
    local surface = cairo_xlib_surface_create(window.display, window.drawable, window.visual,
                                              window.width, window.height)
    local context = cairo_create(surface)
    -- Match the 240px text area, 12px padding, and Xft scaling in system.conf.
    cairo_scale(context, window.width / 266, window.width / 266)
    cairo_set_line_width(context, 3)
    cairo_set_line_cap(context, CAIRO_LINE_CAP_ROUND)
    local details = {
        telemetry.cpu_temperature and string.format('%.0f°C', telemetry.cpu_temperature) or '--°C',
        telemetry.gpu_temperature and string.format('%.0f°C', telemetry.gpu_temperature) or '--°C',
        '',
    }
    for index, metric in ipairs(metrics) do
        local x, y, radius = 52 + (index - 1) * 80, 158, 32
        local value = telemetry.gpu_usage
        if metric.variable then value = tonumber(conky_parse(metric.variable)) end
        cairo_set_source_rgba(context, 70/255, 83/255, 74/255, 0.65)
        cairo_new_path(context)
        cairo_arc(context, x, y, radius, -math.pi/2, 3*math.pi/2)
        cairo_stroke(context)
        if value and value > 0 then
            cairo_set_source_rgb(context, metric.color[1], metric.color[2], metric.color[3])
            cairo_new_path(context)
            cairo_arc(context, x, y, radius, -math.pi/2,
                      -math.pi/2 + 2*math.pi * math.min(value, 100)/100)
            cairo_stroke(context)
        end
        cairo_set_source_rgb(context, 238/255, 232/255, 220/255)
        local reading = value and string.format('%.0f%%', value) or '--'
        if metric.label == 'GPU' and telemetry.sleeping then reading = 'Sleep' end
        centered_text(context, reading, x, metric.label == 'RAM' and y or y - 5,
                      14, CAIRO_FONT_WEIGHT_BOLD)
        cairo_set_source_rgb(context, 171/255, 175/255, 164/255)
        centered_text(context, details[index], x, y + 15, 8, CAIRO_FONT_WEIGHT_NORMAL)
        centered_text(context, metric.label, x, y + radius + 16, 9, CAIRO_FONT_WEIGHT_NORMAL)
    end
    cairo_set_source_rgb(context, 171/255, 175/255, 164/255)
    centered_text(context, conky_parse('${mem}') .. ' / ' .. conky_parse('${memmax}'),
                  212, 220, 7.5, CAIRO_FONT_WEIGHT_NORMAL)
    local battery = conky_parse('${if_existing /sys/class/power_supply/BAT0}1${endif}') == '1'
    local stacks = {
        {label = 'Storage', variable = '${fs_used_perc /}', color = metrics[3].color},
        {label = 'Battery', variable = '${battery_percent}', color = metrics[1].color},
    }
    for index, metric in ipairs(stacks) do
        if index == 1 or battery then
            local x = battery and 72 + (index - 1) * 120 or 132
            local value = tonumber(conky_parse(metric.variable))
            for segment = 0, 9 do
                local y = 330 - (segment + 1) * 4.2
                cairo_set_source_rgba(context, 70/255, 83/255, 74/255, 0.65)
                cairo_new_path(context)
                cairo_rectangle(context, x - 13, y, 26, 3)
                cairo_fill(context)
                local fraction = value and math.min(1, math.max(0, value / 10 - segment)) or 0
                if fraction > 0 then
                    cairo_set_source_rgb(context, metric.color[1], metric.color[2], metric.color[3])
                    cairo_rectangle(context, x - 13, y + 3 * (1 - fraction), 26, 3 * fraction)
                    cairo_fill(context)
                end
            end
            cairo_set_source_rgb(context, metric.color[1], metric.color[2], metric.color[3])
            centered_text(context, metric.label, x, 275, 9, CAIRO_FONT_WEIGHT_NORMAL)
            cairo_set_source_rgb(context, 238/255, 232/255, 220/255)
            centered_text(context, value and string.format('%.0f%%', value) or '--',
                          x, 343, 14, CAIRO_FONT_WEIGHT_BOLD)
        end
    end
    for name, history in pairs(histories) do
        -- Conky increments its update counter between text evaluation and the draw hook.
        if history.requested == update - 1 then
            if history.last_update ~= update then
                local value = tonumber(conky_parse(history.variable))
                if value then
                    history.values[#history.values + 1] = math.max(0, value)
                    -- At one-second updates, 61 real readings span one minute.
                    if #history.values > 61 then table.remove(history.values, 1) end
                end
                history.last_update = update
            end
            -- Network plots follow the footer when the optional battery section changes height.
            local x, width = 12, 240
            local y = history.y or (window.height * 266 / window.width - history.bottom)
            local height, maximum = history.height, 1
            for _, value in ipairs(history.values) do maximum = math.max(maximum, value) end
            if name == 'cpu' then
                local step = width / 61
                -- Fixed slots leave unrecorded time blank while the history fills.
                for index, value in ipairs(history.values) do
                    local px = x + step * (61 - #history.values + index - 1)
                    local alpha = 0.2 + 0.8 * value / (maximum * 1.15)
                    cairo_set_source_rgba(context, history.color[1], history.color[2], history.color[3], alpha)
                    cairo_new_path(context)
                    cairo_rectangle(context, px, y + 6, step - 1, height - 12)
                    cairo_fill(context)
                end
            else
                cairo_set_line_width(context, 1)
                cairo_set_source_rgba(context, 70/255, 83/255, 74/255, 0.5)
                cairo_new_path(context)
                cairo_move_to(context, x, y + height)
                cairo_line_to(context, x + width, y + height)
                cairo_stroke(context)
                if #history.values > 1 then
                    cairo_new_path(context)
                    for index, value in ipairs(history.values) do
                        local px = x + width * (index - 1) / (#history.values - 1)
                        local py = y + height - height * value / (maximum * 1.15)
                        if index == 1 then cairo_move_to(context, px, py)
                        else cairo_line_to(context, px, py) end
                    end
                    cairo_set_line_width(context, 1.5)
                    cairo_set_source_rgb(context, history.color[1], history.color[2], history.color[3])
                    cairo_stroke_preserve(context)
                    cairo_line_to(context, x + width, y + height)
                    cairo_line_to(context, x, y + height)
                    cairo_close_path(context)
                    cairo_set_source_rgba(context, history.color[1], history.color[2], history.color[3], 0.08)
                    cairo_fill(context)
                end
            end
        end
    end
    cairo_destroy(context)
    cairo_surface_destroy(surface)
end
