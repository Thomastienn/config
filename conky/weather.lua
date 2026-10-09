require('cairo')

local mint = {167/255, 204/255, 174/255}
local cream = {238/255, 232/255, 220/255}
local muted = {171/255, 175/255, 164/255}
local rail = {93/255, 109/255, 94/255}
local state = {}

function conky_weather(...)
    state = {}
    for index, value in ipairs({...}) do state[index] = tonumber(value) end
    return ''
end

local function text(context, value, x, y, size, color, centered, bold)
    cairo_set_source_rgb(context, color[1], color[2], color[3])
    cairo_select_font_face(context, 'ComicShannsMono Nerd Font', CAIRO_FONT_SLANT_NORMAL,
                           bold and CAIRO_FONT_WEIGHT_BOLD or CAIRO_FONT_WEIGHT_NORMAL)
    cairo_set_font_size(context, size)
    if centered then
        local extents = cairo_text_extents_t:create()
        cairo_text_extents(context, value, extents)
        x = x - extents.width/2 - extents.x_bearing
    end
    cairo_move_to(context, x, y)
    cairo_show_text(context, value)
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

local function icon(context, code, is_day, x, y)
    local _, kind = condition(code)
    if not kind then return end
    cairo_save(context)
    cairo_translate(context, x, y)
    cairo_set_source_rgb(context, mint[1], mint[2], mint[3])
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

local function daylight(context, now)
    local rise, setting, next_rise = state[6], state[7], state[8]
    local fraction = rise and setting and math.max(0, math.min(1, (now - rise)/(setting - rise)))
    cairo_save(context)
    cairo_translate(context, 382, 83)
    cairo_scale(context, 1, 0.48)
    cairo_set_line_width(context, 1.5)
    cairo_set_source_rgb(context, rail[1], rail[2], rail[3])
    cairo_new_path(context)
    cairo_arc(context, 0, 0, 57, math.pi, 2*math.pi)
    cairo_stroke(context)
    if fraction and now >= rise and now <= setting then
        cairo_set_source_rgb(context, mint[1], mint[2], mint[3])
        cairo_new_path(context)
        cairo_arc(context, 0, 0, 57, math.pi, math.pi + fraction*math.pi)
        cairo_stroke(context)
    end
    cairo_restore(context)
    if fraction and now >= rise and now <= setting then
        local angle = math.pi + fraction*math.pi
        cairo_set_source_rgb(context, cream[1], cream[2], cream[3])
        cairo_new_path(context)
        cairo_arc(context, 382 + 57*math.cos(angle), 83 + 27.36*math.sin(angle), 3, 0, 2*math.pi)
        cairo_fill(context)
    end
    text(context, clock(state[9]), 325, 104, 8, muted, true)
    text(context, clock(state[10]), 439, 104, 8, muted, true)
    local event, label
    if rise and now < rise then event, label = rise, 'Sunrise'
    elseif setting and now < setting then event, label = setting, 'Sunset'
    elseif next_rise then event, label = next_rise, 'Sunrise' end
    local remaining = event and math.ceil((event - now)/60)
    local status = remaining and string.format('%s in %dh %02dm', label, math.floor(remaining/60), remaining%60)
                              or 'Times unavailable'
    text(context, status, 382, 126, 8, cream, true)
end

function conky_draw_weather()
    if not conky_window then return end
    local window = conky_window
    local surface = cairo_xlib_surface_create(window.display, window.drawable, window.visual,
                                              window.width, window.height)
    local context = cairo_create(surface)
    -- Same Xft scale and padding as the existing system panel.
    cairo_scale(context, window.width/466, window.width/466)
    cairo_set_line_cap(context, CAIRO_LINE_CAP_ROUND)
    text(context, 'Calgary', 12, 24, 12, mint, false, true)
    text(context, 'Next hours', 155, 24, 9, muted)
    text(context, 'Daylight', 382, 24, 9, muted, true)
    text(context, temperature(state[1]), 12, 75, 36, cream, false, true)
    text(context, 'Feels like ' .. temperature(state[2]), 12, 99, 9, muted)
    text(context, condition(state[3]), 12, 122, 9, cream)
    text(context, 'Precip.', 121, 122, 7, muted)
    for index = 0, 3 do
        local start, x = 11 + index*5, 165 + index*42
        local hour = state[start]
        text(context, hour and string.format('%02d', hour) or '--', x, 50, 8, muted, true)
        icon(context, state[start + 2], state[start + 4], x, 70)
        text(context, temperature(state[start + 1]), x, 99, 10, cream, true)
        local probability = state[start + 3]
        text(context, probability and string.format('%.0f%%', probability) or '--', x, 122, 8, muted, true)
    end
    daylight(context, os.time())
    local footer = state[4] and ((state[5] == 1 and 'Cached ' or 'Updated ') .. clock(state[4]))
                             or 'Weather unavailable'
    text(context, footer .. ' / Open-Meteo', 233, 151, 8, muted, true)
    cairo_destroy(context)
    cairo_surface_destroy(surface)
end
