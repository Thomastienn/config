-- Time and weather, week forecast and next 24 hours cards, drawn entirely in Cairo; weather.py passes in the numbers.
local ui = dofile(os.getenv('HOME') .. '/thomas_config/conky/panel.lua')
local c = ui.colors
-- 320 units wide, as sized in deck.lua.
local WIDTH, LEFT, RIGHT = 320, 16, 304
local state, week, hours, rain, wind = {}, {}, {}, {}, {}

-- A missing value arrives as '-' and stays nil.
local function numbers(...)
    local list = {}
    for index, value in ipairs({...}) do list[index] = tonumber(value) end
    return list
end

function conky_weather(...) state = numbers(...) return '' end
-- Per day: weekday (Monday is 0), high, low, weather code.
function conky_forecast(...) week = numbers(...) return '' end
-- The first hour's clock hour, then 24 hourly temperatures.
function conky_hours(...) hours = numbers(...) return '' end
-- Precipitation chance for the same 24 hours.
function conky_rain(...) rain = numbers(...) return '' end
-- Wind speed in km/h for the same 24 hours.
function conky_wind(...) wind = numbers(...) return '' end

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
local function hour(context, x, y, start)
    local middle, probability = x + 20.5, state[start + 3]
    ui.rounded(context, x, y, 41, 96, 9)
    ui.color(context, c.surface, 0.6)
    cairo_fill(context)
    ui.text(context, state[start] and string.format('%02d', state[start]) or '--', middle, y + 15, 10, c.muted, 0.5)
    icon(context, state[start + 2], state[start + 4], middle, y + 34)
    ui.text(context, temperature(state[start + 1]), middle, y + 66, 11.5, c.text, 0.5, true)
    ui.text(context, probability and string.format('%.0f%%', probability) or '--', middle, y + 81, 9.5, c.muted, 0.5)
    cairo_set_line_width(context, 2.5)
    ui.color(context, c.border, 0.8)
    ui.line(context, x + 9, y + 88, x + 32, y + 88)
    if probability and probability > 0 then
        ui.color(context, c.secondary)
        ui.line(context, x + 9, y + 88, x + 9 + 23 * probability/100, y + 88)
    end
end

-- Clock and date above a midnight-to-midnight line; its warm span is today's daylight.
local function today(context)
    local width = ui.text(context, os.date('%H'), LEFT, 66, 54, c.primary, 0, true)
    width = width + ui.text(context, ':', LEFT + width, 62, 54, c.separator, 0, true)
    ui.text(context, os.date('%M'), LEFT + width, 66, 54, c.text, 0, true)
    ui.text(context, os.date('%A'), RIGHT, 36, 11, c.primary, 1, true)
    ui.text(context, tonumber(os.date('%d')) .. ' ' .. os.date('%B'), RIGHT, 51, 11, c.text, 1)
    ui.text(context, os.date('%Y'), RIGHT, 65, 10, c.muted, 1)
    local function at(minute) return LEFT + (RIGHT - LEFT) * minute / 1440 end
    local now = os.date('*t')
    local tip = at(now.hour * 60 + now.min + now.sec / 60)
    cairo_set_line_width(context, 2)
    ui.color(context, c.border, 0.6)
    ui.line(context, LEFT, 86, RIGHT, 86)
    if state[9] and state[10] then
        ui.color(context, c.warning, 0.5)
        ui.line(context, at(state[9]), 86, at(state[10]), 86)
        ui.text(context, clock(state[9]), at(state[9]), 102, 9.5, c.muted, 0.5)
        ui.text(context, clock(state[10]), at(state[10]), 102, 9.5, c.muted, 0.5)
    end
    ui.fade(context, tip, 86, math.max(LEFT, tip - 80), 86, c.primary)
    ui.glow(context, tip, 86, 8, c.primary)
    ui.color(context, c.text)
    cairo_new_path(context)
    cairo_arc(context, tip, 86, 2.2, 0, 2*math.pi)
    cairo_fill(context)
end

-- Time until the next sunrise or sunset, or nothing while the times are unknown.
local function countdown(now)
    local rise, setting, next_rise = state[6], state[7], state[8]
    local event, label
    if rise and now < rise then event, label = rise, 'Sunrise'
    elseif setting and now < setting then event, label = setting, 'Sunset'
    elseif next_rise then event, label = next_rise, 'Sunrise' end
    local remaining = event and math.ceil((event - now)/60)
    return remaining and string.format('%s in %dh %02dm', label, math.floor(remaining/60), remaining%60) or ''
end

function conky_draw_weather()
    if not conky_window then return end
    local context, surface, height = ui.open(WIDTH)
    today(context)
    local next_event = ui.text(context, countdown(os.time()), RIGHT, 128, 10, c.muted, 1)
    ui.section(context, 'Calgary', LEFT, 128, RIGHT - next_event - 8)
    ui.text(context, temperature(state[1]), LEFT, 182, 40, c.text, 0, true)
    ui.text(context, 'Feels like ' .. temperature(state[2]), LEFT, 202, 10, c.muted)
    icon(context, state[3], 1, LEFT + 11, 222, 0.8)
    ui.text(context, (condition(state[3])), state[3] and LEFT + 28 or LEFT, 226, 10.5, c.text)
    for index = 0, 3 do hour(context, RIGHT - 179 + index * 46, 140, 11 + index * 5) end
    local footer = state[4] and ((state[5] == 1 and 'Cached ' or 'Updated ') .. clock(state[4]))
                             or 'Weather unavailable'
    ui.text(context, footer .. ' / Open-Meteo', LEFT, height - 13, 9.5, c.muted)
    ui.close(context, surface)
end

-- Week forecast card, 172 units wide as sized in deck.lua: each day's low-to-high span on the week's range.
function conky_draw_forecast()
    if not conky_window then return end
    local WIDTH, RIGHT, START, END = 172, 156, 96, 126
    local context, surface = ui.open(WIDTH)
    ui.section(context, 'Week', LEFT, 28, RIGHT)
    local coldest, warmest
    for index = 1, #week, 4 do
        local high, low = week[index + 1], week[index + 2]
        if high and low then
            coldest, warmest = math.min(coldest or low, low), math.max(warmest or high, high)
        end
    end
    if not coldest then ui.text(context, 'Forecast unavailable', LEFT, 52, 10, c.muted) end
    -- Cold end lavender, warm end amber; a day's span shows its slice of that gradient.
    local range = cairo_pattern_create_linear(START, 0, END, 0)
    cairo_pattern_add_color_stop_rgb(range, 0, c.secondary[1], c.secondary[2], c.secondary[3])
    cairo_pattern_add_color_stop_rgb(range, 1, c.warning[1], c.warning[2], c.warning[3])
    local function at(value) return START + (END - START) * (value - coldest) / math.max(1, warmest - coldest) end
    local weekday = (tonumber(os.date('%w')) + 6) % 7
    for row = 0, coldest and #week / 4 - 1 or -1 do
        local day, high, low, code = week[row*4 + 1], week[row*4 + 2], week[row*4 + 3], week[row*4 + 4]
        local y, now = 51 + row * 18.5, row == 0 and day == weekday
        ui.text(context, ({'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'})[day + 1] or '', LEFT, y, 10.5,
                now and c.primary or c.text, 0, now)
        icon(context, code, 1, LEFT + 34, y - 3.5, 0.6)
        ui.text(context, temperature(low), START - 7, y, 10, c.muted, 1)
        ui.text(context, temperature(high), RIGHT, y, 10, c.text, 1, true)
        cairo_set_line_width(context, 3)
        ui.color(context, c.border, 0.6)
        ui.line(context, START, y - 3.5, END, y - 3.5)
        if high and low then
            cairo_set_source(context, range)
            ui.line(context, at(low), y - 3.5, at(high), y - 3.5)
        end
    end
    cairo_pattern_destroy(range)
    ui.close(context, surface)
end

-- Smooth line through the points over a fill fading down to `floor`, coloured `upper` at `top` and `lower` further down.
local function area(context, points, top, floor, upper, lower)
    cairo_new_path(context)
    cairo_move_to(context, points[1][1], points[1][2])
    -- Catmull-Rom: the line leaves each hour along the slope between its neighbours, so hours join without corners.
    for index = 1, #points - 1 do
        local from, to = points[index], points[index + 1]
        local before, after = points[index - 1] or from, points[index + 2] or to
        cairo_curve_to(context, from[1] + (to[1] - before[1]) / 6, from[2] + (to[2] - before[2]) / 6,
                       to[1] - (after[1] - from[1]) / 6, to[2] - (after[2] - from[2]) / 6, to[1], to[2])
    end
    local line = cairo_pattern_create_linear(0, top, 0, floor)
    cairo_pattern_add_color_stop_rgba(line, 0, upper[1], upper[2], upper[3], 1)
    cairo_pattern_add_color_stop_rgba(line, 0.75, lower[1], lower[2], lower[3], 1)
    local fill = cairo_pattern_create_linear(0, top, 0, floor)
    cairo_pattern_add_color_stop_rgba(fill, 0, upper[1], upper[2], upper[3], 0.3)
    cairo_pattern_add_color_stop_rgba(fill, 1, lower[1], lower[2], lower[3], 0)
    cairo_set_line_width(context, 1.8)
    cairo_set_source(context, line)
    cairo_stroke_preserve(context)
    cairo_line_to(context, points[#points][1], floor)
    cairo_line_to(context, points[1][1], floor)
    cairo_close_path(context)
    cairo_set_source(context, fill)
    cairo_fill(context)
    cairo_pattern_destroy(line)
    cairo_pattern_destroy(fill)
end

-- Next 24 hours card, 344 units wide as sized in deck.lua: temperature, precipitation chance and wind speed,
-- one lane each on the same hours, each naming its peak.
function conky_draw_hours()
    if not conky_window then return end
    local WIDTH, RIGHT, START = 344, 328, 54
    local context, surface = ui.open(WIDTH)
    ui.section(context, 'Next 24 hours', LEFT, 28, RIGHT)
    if not hours[1] then
        ui.text(context, 'Forecast unavailable', LEFT, 52, 10, c.muted)
        ui.close(context, surface)
        return
    end
    local function at(index) return START + (RIGHT - START) * (index - 1) / 23 end
    -- Hours holding the lowest and highest value; `offset` skips what precedes the 24 values.
    local function extremes(values, offset)
        local lowest, highest
        for index = 1, 24 do
            local value = values[index + offset]
            if value and (not lowest or value < values[lowest + offset]) then lowest = index end
            if value and (not highest or value > values[highest + offset]) then highest = index end
        end
        return lowest, highest
    end
    -- A value's label beside its hour, kept inside the plot; `dot` marks the spot on a line.
    local function mark(index, y, label, offset, color, dot)
        if dot then
            ui.glow(context, at(index), y, 7, dot)
            ui.color(context, c.text)
            cairo_new_path(context)
            cairo_arc(context, at(index), y, 2.2, 0, 2*math.pi)
            cairo_fill(context)
        end
        local half = #label * 3
        ui.text(context, label, math.max(START + half, math.min(RIGHT - half, at(index))), y + offset, 10, color, 0.5,
                color == c.text)
    end

    -- Temperature: warm amber on top and cold lavender below, as on the week card.
    ui.text(context, 'Temp', LEFT, 69, 9, c.muted)
    local coldest, warmest = extremes(hours, 1)
    if coldest then
        local low, high = hours[coldest + 1], hours[warmest + 1]
        local function level(value) return 80 - 30 * (value - low) / math.max(1, high - low) end
        local points = {}
        for index = 1, 24 do
            if hours[index + 1] then points[#points + 1] = {at(index), level(hours[index + 1])} end
        end
        area(context, points, 50, 96, c.warning, c.secondary)
        mark(warmest, level(high), temperature(high), -9, c.text, c.warning)
        if coldest ~= warmest then mark(coldest, level(low), temperature(low), 14, c.muted, c.secondary) end
    end

    -- Precipitation chance: a bar per hour, the tallest one labelled.
    ui.text(context, 'Precip', LEFT, 118, 9, c.muted)
    local _, wettest = extremes(rain, 0)
    for index = 1, 24 do
        local chance = rain[index] or 0
        if chance > 0 then
            cairo_set_line_width(context, 5)
            ui.color(context, c.accent, 0.35 + 0.65 * chance / 100)
            ui.line(context, at(index), 116, at(index), 116 - 11 * chance / 100)
        end
    end
    if wettest and rain[wettest] > 0 then
        mark(wettest, 116 - 11 * rain[wettest] / 100, string.format('%.0f%%', rain[wettest]), -6, c.text)
    end

    -- Wind speed: the lane's top is the peak, or 30 km/h on a calm day so a breeze stays low.
    ui.text(context, 'Wind', LEFT, 149, 9, c.muted)
    local _, windiest = extremes(wind, 0)
    if windiest then
        local function level(value) return 153 - 19 * value / math.max(30, wind[windiest]) end
        local points = {}
        for index = 1, 24 do
            if wind[index] then points[#points + 1] = {at(index), level(wind[index])} end
        end
        area(context, points, 134, 154, c.primary, c.primary)
        mark(windiest, level(wind[windiest]), string.format('%.0f km/h', wind[windiest]), -7, c.text, c.primary)
    end

    cairo_set_line_width(context, 1)
    ui.color(context, c.border, 0.6)
    ui.line(context, START, 120.5, RIGHT, 120.5)
    ui.line(context, START, 154.5, RIGHT, 154.5)
    for index = 1, 24 do
        local hour_of_day = (hours[1] + index - 1) % 24
        if hour_of_day % 3 == 0 then
            ui.text(context, string.format('%02d', hour_of_day), at(index), 168, 9.5,
                    hour_of_day == 0 and c.primary or c.muted, 0.5, hour_of_day == 0)
        end
    end
    ui.close(context, surface)
end
