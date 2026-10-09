-- Run with lua conky/test-gauges.lua; Cairo is mocked, no desktop changes.
package.preload.cairo = function() return {} end
CAIRO_FONT_SLANT_NORMAL, CAIRO_FONT_WEIGHT_NORMAL = 0, 0
CAIRO_FONT_WEIGHT_BOLD, CAIRO_LINE_CAP_ROUND = 1, 1
local arcs, labels, destroyed, scale = {}, {}, 0, nil
local path, curves = {}, {}
local cells, alpha = {}, 1
local has_point = false
local values = {['${updates}'] = '2', ['${cpu cpu0}'] = '5', ['${memperc}'] = '50'}
function conky_parse(variable) return values[variable] end
function cairo_xlib_surface_create() return {} end
function cairo_create() return {} end
function cairo_scale(_, x, y) assert(x == y); scale = x end
function cairo_set_line_width() end
function cairo_set_line_cap() end
function cairo_set_source_rgb() alpha = 1 end
function cairo_set_source_rgba(_, _, _, _, opacity) alpha = opacity end
function cairo_rectangle(_, x, y, width, height)
    assert(x == x and y == y and width > 0 and height > 0, 'Heat cells must have finite, positive bounds')
    assert(alpha > 0 and alpha <= 1, 'Heat intensity must be visible and bounded')
    cells[#cells + 1] = {x = x, y = y, width = width, height = height, alpha = alpha}
end
function cairo_stroke() has_point, path = false, {} end
function cairo_new_path() has_point, path = false, {} end
function cairo_stroke_preserve()
    local curve = {}
    for index, point in ipairs(path) do curve[index] = point end
    curves[#curves + 1] = curve
end
function cairo_close_path() end
function cairo_fill() has_point, path = false, {} end
function cairo_select_font_face() end
function cairo_set_font_size() end
function cairo_move_to(_, x, y) has_point, path = true, {{x = x, y = y}} end
function cairo_line_to(_, x, y)
    assert(has_point and x == x and y == y, 'History coordinates must be finite')
    path[#path + 1] = {x = x, y = y}
end
function cairo_arc(_, x, y, radius, start, finish)
    assert(not has_point, 'A new ring must not connect to the previous text position')
    arcs[#arcs + 1] = {x = x, y = y, radius = radius, fraction = (finish - start)/(2*math.pi)}
end
function cairo_show_text(_, text) labels[#labels + 1] = text end
cairo_text_extents_t = {create = function() return {} end}
function cairo_text_extents(_, _, extents)
    extents.width, extents.height, extents.x_bearing, extents.y_bearing = 10, 10, 0, -10
end
function cairo_destroy() destroyed = destroyed + 1 end
function cairo_surface_destroy() destroyed = destroyed + 1 end
dofile('conky/gauges.lua')
conky_gauges()
assert(#arcs == 0, 'No drawing before the Conky window exists')
conky_window = {width = 399, height = 900}
conky_gauges()
assert(scale == 1.5 and destroyed == 2)
assert(#arcs == 4 and math.abs(arcs[2].fraction - 0.05) < 1e-10)
assert(math.abs(arcs[4].fraction - 0.5) < 1e-10)
assert(labels[1] == '5%' and labels[2] == 'CPU' and labels[3] == '50%' and labels[4] == 'Memory')
arcs, labels = {}, {}
values['${cpu cpu0}'], values['${memperc}'] = '0', 'not available'
conky_gauges()
assert(#arcs == 2, 'Zero and missing values show only their track')
assert(labels[1] == '0%' and labels[3] == '--')
arcs, labels = {}, {}
values['${cpu cpu0}'], values['${memperc}'] = '100', '120'
conky_gauges()
assert(#arcs == 4 and math.abs(arcs[2].fraction - 1) < 1e-10)
assert(math.abs(arcs[4].fraction - 1) < 1e-10, 'The arc cannot exceed a full circle')
assert(destroyed == 6, 'Every draw releases its Cairo context and surface')
values['${updates}'] = '0'
conky_gauges()
assert(destroyed == 6, 'Skip the first incomplete rendering cycle')

local function request(name, variable, argument)
    local draw_update = values['${updates}']
    values['${updates}'] = tostring(tonumber(draw_update) - 1)
    conky_history(name, variable, argument)
    local span = conky_history_span()
    values['${updates}'] = draw_update
    return span
end
values['${updates}'], values['${cpu cpu0}'] = '2', '5'
assert(request('cpu', 'cpu', 'cpu0') == 'live')
conky_gauges()
assert(#curves == 0 and #cells == 1, 'Startup shows only its one real CPU reading')
assert(cells[1].x > 248 and cells[1].x + cells[1].width <= 252, 'Newest reading sits at the right edge')
cells = {}
values['${updates}'], values['${cpu cpu0}'] = '3', '1'
assert(request('cpu', 'cpu', 'cpu0') == 'last 1s')
conky_gauges()
assert(#curves == 0 and #cells == 2, 'CPU draws heat cells instead of a curve')
assert(cells[1].x + cells[1].width < cells[2].x, 'Readings have a gap and run oldest to newest')
assert(cells[1].y == cells[2].y and cells[1].height == cells[2].height,
       'CPU activity changes intensity, not cell height')
assert(cells[1].alpha > cells[2].alpha, 'Busier readings look brighter')
local recent_alpha = cells[2].alpha
cells = {}
values['${cpu cpu0}'] = '99'
request('cpu', 'cpu', 'cpu0')
conky_gauges()
assert(#cells == 2 and cells[2].alpha == recent_alpha, 'Redrawing cannot add extra samples')
for update = 4, 63 do
    values['${updates}'], values['${cpu cpu0}'] = tostring(update), tostring(update)
    request('cpu', 'cpu', 'cpu0')
    cells = {}
    conky_gauges()
end
assert(#cells == 61 and cells[1].x == 12 and conky_history_span() == 'last 60s')
assert(cells[1].alpha < 0.22 and cells[61].alpha > 0.85,
       'The oldest reading drops out once the one-minute buffer is full')

curves = {}
values['${updates}'] = '64'
values['${downspeedf wlo1}'], values['${upspeedf wlo1}'] = '4', '0'
request('download', 'downspeedf', 'wlo1')
request('upload', 'upspeedf', 'wlo1')
conky_gauges()
values['${updates}'], values['${downspeedf wlo1}'] = '65', '8'
request('download', 'downspeedf', 'wlo1')
request('upload', 'upspeedf', 'wlo1')
conky_gauges()
assert(#curves == 2)
for _, curve in ipairs(curves) do
    assert(#curve == 2 and curve[1].x == 12 and curve[2].x == 252)
    assert(curve[1].y >= 370 and curve[1].y <= 449, 'Network curves stay in their reserved slots')
end
curves = {}
values['${updates}'], values['${downspeedf enp55s0}'] = '66', '100'
request('download', 'downspeedf', 'enp55s0')
conky_gauges()
assert(#curves == 0, 'Switching interfaces cannot show the old interface history')
values['${updates}'] = '67'
conky_gauges()
assert(#curves == 0, 'Offline sections do not draw stale network curves')
values['${updates}'] = '68'
request('download', 'downspeedf', 'enp55s0')
conky_gauges()
assert(#curves == 0, 'Returning from offline starts a fresh history')

cells = {}
values['${updates}'], values['${cpu cpu0}'] = '69', 'not available'
request('cpu', 'cpu', 'cpu0')
conky_gauges()
assert(#curves == 0 and #cells == 0, 'Unavailable readings do not fabricate data')
for update = 70, 71 do
    values['${updates}'], values['${cpu cpu0}'] = tostring(update), '0'
    request('cpu', 'cpu', 'cpu0')
    cells = {}
    conky_gauges()
end
assert(#curves == 0 and #cells == 2 and cells[1].alpha == cells[2].alpha,
       'Real idle readings remain visible at equal intensity')
print('Rings, CPU heat strip, one-minute history, duplicate redraws, network curves, offline, and missing readings passed')
