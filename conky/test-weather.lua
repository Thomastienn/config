-- Run with: lua conky/test-weather.lua
package.preload.cairo = function() return {} end
CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL, CAIRO_FONT_WEIGHT_BOLD, CAIRO_LINE_CAP_ROUND = 0, 0, 1, 1
cairo_text_extents_t = {create = function() return {} end}
local labels, circles = {}, {}
for _, name in ipairs({'xlib_surface_create', 'create', 'set_source_rgb', 'select_font_face', 'set_font_size',
                      'move_to', 'line_to', 'curve_to', 'save', 'restore', 'translate', 'scale',
                      'set_line_width', 'new_path', 'stroke', 'fill', 'close_path', 'set_line_cap',
                      'destroy', 'surface_destroy'}) do
    _G['cairo_' .. name] = function() return {} end
end
cairo_text_extents = function(_, value, extents) extents.width, extents.x_bearing = #value*4, 0 end
cairo_show_text = function(_, value) labels[#labels + 1] = value end
cairo_arc = function(_, x, y, radius) circles[#circles + 1] = {x, y, radius} end
conky_window = {width = 466, height = 172}
dofile('conky/weather.lua')

local now = 5000
os.time = function() return now end
local function draw(...)
    labels, circles = {}, {}
    conky_weather(...)
    conky_draw_weather()
    local markers = {}
    for _, circle in ipairs(circles) do
        if circle[3] == 3 then markers[#markers + 1] = circle end
    end
    return table.concat(labels, '\n'), markers
end

local label, markers = draw(12, 10, 3, 1110, 0, 1000, 9000, 95000, 468, 1138,
                            19, 12, 3, 10, 0, 20, 11, 61, 30, 0,
                            21, 10, 71, 40, 0, 22, 9, 95, 50, 0)
assert(label:find('Calgary') and label:find('Overcast') and label:find('Updated 18:30'))
assert(label:find('10%%') and label:find('50%%'))
assert(#markers == 1 and math.abs(markers[1][1] - 382) < 0.001)
assert(math.abs(markers[1][2] - 55.64) < 0.001, 'Midday sun should sit at top of arc')
now, circles = 6000, {}
conky_draw_weather()
local moved = false
for _, circle in ipairs(circles) do
    if circle[3] == 3 and circle[1] > 382 then moved = true end
end
assert(moved, 'Sun should move using local time without receiving new weather data')
now = 9500
label, markers = draw(12, 10, 0, 1110, 1, 1000, 9000, 95000, 468, 1138)
assert(label:find('Sunrise in') and label:find('Cached 18:30'))
assert(#markers == 0, 'Do not show sun still moving after sunset')
label, markers = draw()
assert(label:find('Weather unavailable') and label:find('Times unavailable') and label:find('%-%-°'))
assert(#markers == 0, 'Missing daylight data must not create a sun marker')
conky_window = nil
conky_draw_weather()
print('Weather drawing, local sun progress, night, cached readings, and missing data passed')
