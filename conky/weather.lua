-- Weather panel, drawn entirely in Cairo from the numbers weather.py passes in.
local ui = dofile(os.getenv('HOME') .. '/thomas_config/conky/panel.lua')
local c = ui.colors
local state = {}

function conky_weather(...)
    state = {}
    for index, value in ipairs({...}) do state[index] = tonumber(value) end
    conky_set_update_interval(60)
    return ''
end

local function temperature(value)
    return value and string.format('%.0f°', value) or '--°'
end

local function clock(value)
    return value and string.format('%02d:%02d', math.floor(value/60), value%60) or '--:--'
end

local function condition(code)
    if code == 0 then return 'Clear', 'clear' end
    if code == 1 then return 'Mostly clear', 'clear' end
    if code == 2 then return 'Partly cloudy', 'cloud' end
    if code == 3 then return 'Overcast', 'cloud' end
    if code == 45 or code == 48 then return 'Fog', 'fog' end
    if code and code >= 51 and code <= 57 then return 'Drizzle', 'rain' end
    if code and code >= 61 and code <= 67 then return 'Rain', 'rain' end
    if code and code >= 71 and code <= 77 then return 'Snow', 'snow' end
    if code and code >= 80 and code <= 82 then return 'Showers', 'rain' end
    if code == 85 or code == 86 then return 'Snow showers', 'snow' end
    if code and code >= 95 and code <= 99 then return 'Thunderstorm', 'storm' end
    return 'Weather unavailable', nil
end

local function icon(context, code, is_day, x, y, scale)
    local _, kind = condition(code)
    if not kind then return end
    cairo_save(context)
    cairo_translate(context, x, y)
    cairo_scale(context, scale or 1, scale or 1)
    ui.color(context, c.primary)
    cairo_set_line_width(context, 1.4)
    cairo_new_path(context)
    if kind == 'clear' then
        if is_day == 0 then
            cairo_arc(context, 0, 0, 7, 0.4, 5.2)
            cairo_curve_to(context, -2, -5, -2, 4, 6.5, 2.7)
        else
            cairo_arc(context, 0, 0, 4, 0, 2*math.pi)
            for index = 0, 7 do
                local angle = index * math.pi/4
                cairo_move_to(context, math.cos(angle)*7, math.sin(angle)*7)
                cairo_line_to(context, math.cos(angle)*9, math.sin(angle)*9)
            end
        end
    else
        cairo_move_to(context, -7, 4)
        cairo_curve_to(context, -14, 3, -12, -6, -6, -5)
        cairo_curve_to(context, -5, -13, 6, -12, 8, -5)
        cairo_curve_to(context, 15, -6, 16, 4, 9, 4)
        cairo_close_path(context)
        if kind == 'rain' then
            for _, dx in ipairs({-5, 1, 7}) do
                cairo_move_to(context, dx, 8)
                cairo_line_to(context, dx - 2, 11)
            end
        elseif kind == 'snow' then
            for _, dx in ipairs({-5, 1, 7}) do
                cairo_move_to(context, dx - 1.5, 9)
                cairo_line_to(context, dx + 1.5, 9)
                cairo_move_to(context, dx, 7.5)
                cairo_line_to(context, dx, 10.5)
            end
        elseif kind == 'fog' then
            for _, dy in ipairs({8, 11}) do
                cairo_move_to(context, -8, dy)
                cairo_line_to(context, 9, dy)
            end
        elseif kind == 'storm' then
            cairo_move_to(context, 2, 6)
            cairo_line_to(context, -2, 10)
            cairo_line_to(context, 2, 10)
            cairo_line_to(context, -2, 15)
        end
    end
    cairo_stroke(context)
    cairo_restore(context)
end

-- One forecast hour on a soft card; the bar along its foot is the precipitation chance.
local function hour(context, x, start)
    local middle, probability = x + 20.5, state[start + 3]
    ui.rounded(context, x, 40, 41, 96, 9)
    ui.color(context, c.surface, 0.6)
    cairo_fill(context)
    ui.text(context, state[start] and string.format('%02d', state[start]) or '--', middle, 55, 9, c.muted, 0.5)
    icon(context, state[start + 2], state[start + 4], middle, 74)
    ui.text(context, temperature(state[start + 1]), middle, 106, 11.5, c.text, 0.5, true)
    ui.text(context, probability and string.format('%.0f%%', probability) or '--', middle, 121, 8.5, c.muted, 0.5)
    cairo_set_line_width(context, 2.5)
    ui.color(context, c.border, 0.8)
    cairo_new_path(context)
    cairo_move_to(context, x + 9, 128)
    cairo_line_to(context, x + 32, 128)
    cairo_stroke(context)
    if probability and probability > 0 then
        ui.color(context, c.secondary)
        cairo_new_path(context)
        cairo_move_to(context, x + 9, 128)
        cairo_line_to(context, x + 9 + 23 * probability/100, 128)
        cairo_stroke(context)
    end
end

local function daylight(context, now)
    local rise, setting, next_rise = state[6], state[7], state[8]
    local x, y, across, up = 400, 100, 48, 36
    local function arc(finish)
        cairo_save(context)
        cairo_translate(context, x, y)
        cairo_scale(context, 1, up/across)
        cairo_new_path(context)
        cairo_arc(context, 0, 0, across, math.pi, finish)
        cairo_restore(context)
    end
    cairo_set_line_width(context, 1)
    ui.color(context, c.border, 0.8)
    cairo_new_path(context)
    cairo_move_to(context, x - across - 8, y)
    cairo_line_to(context, x + across + 8, y)
    cairo_stroke(context)
    cairo_set_line_width(context, 1.6)
    ui.color(context, c.separator)
    arc(2*math.pi)
    cairo_stroke(context)
    if rise and setting and now >= rise and now <= setting then
        local angle = math.pi + math.pi * (now - rise)/(setting - rise)
        local sky = cairo_pattern_create_linear(x - across, 0, x + across, 0)
        cairo_pattern_add_color_stop_rgb(sky, 0, c.warning[1], c.warning[2], c.warning[3])
        cairo_pattern_add_color_stop_rgb(sky, 1, c.primary[1], c.primary[2], c.primary[3])
        cairo_set_source(context, sky)
        arc(angle)
        cairo_stroke(context)
        cairo_pattern_destroy(sky)
        local sun_x, sun_y = x + across * math.cos(angle), y + up * math.sin(angle)
        ui.glow(context, sun_x, sun_y, 13, c.warning)
        ui.color(context, c.text)
        cairo_new_path(context)
        cairo_arc(context, sun_x, sun_y, 3.2, 0, 2*math.pi)
        cairo_fill(context)
    end
    ui.text(context, clock(state[9]), x - across, y + 13, 8.5, c.muted, 0.5)
    ui.text(context, clock(state[10]), x + across, y + 13, 8.5, c.muted, 0.5)
    local event, label
    if rise and now < rise then event, label = rise, 'Sunrise'
    elseif setting and now < setting then event, label = setting, 'Sunset'
    elseif next_rise then event, label = next_rise, 'Sunrise' end
    local remaining = event and math.ceil((event - now)/60)
    ui.text(context, remaining and string.format('%s in %dh %02dm', label, math.floor(remaining/60), remaining%60)
                               or 'Times unavailable', x, y + 31, 9, c.text, 0.5)
end

function conky_draw_weather()
    if not conky_window then return end
    -- 440 units of content inside 12 units of padding, as sized in weather.conf.
    local context, surface, height = ui.open(466)
    ui.section(context, 'Calgary', 14, 26, 128)
    ui.section(context, 'Next hours', 152, 26, 330)
    ui.section(context, 'Daylight', 352, 26, 452)
    ui.text(context, temperature(state[1]), 14, 82, 42, c.text, 0, true)
    ui.text(context, 'Feels like ' .. temperature(state[2]), 14, 104, 10, c.muted)
    icon(context, state[3], 1, 25, 124, 0.8)
    ui.text(context, (condition(state[3])), state[3] and 42 or 14, 128, 10.5, c.text)
    for index = 0, 3 do hour(context, 152 + index * 46, 11 + index * 5) end
    daylight(context, os.time())
    local footer = state[4] and ((state[5] == 1 and 'Cached ' or 'Updated ') .. clock(state[4]))
                             or 'Weather unavailable'
    ui.text(context, footer .. ' / Open-Meteo', 233, height - 11, 8.5, c.muted, 0.5)
    ui.close(context, surface)
end
