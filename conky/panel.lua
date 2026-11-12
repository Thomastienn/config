-- Shared Cairo drawing for the Conky panels: theme palette, text, and the panel backdrop.
local theme = dofile(os.getenv('HOME') .. '/thomas_config/themes/.generated/palette.lua')
require('cairo')

local ui = {colors = theme.colors}
-- Reused: Conky's Lua binding never frees extents, so one per call leaked ~180 MB in a day and a half.
local extents = cairo_text_extents_t:create()

function ui.color(context, color, alpha)
    cairo_set_source_rgba(context, color[1], color[2], color[3], alpha or 1)
end

-- align: 0 left (default), 0.5 centered, 1 right. Returns the advance width.
function ui.text(context, value, x, y, size, color, align, bold)
    ui.color(context, color)
    cairo_select_font_face(context, theme.fonts.ui, CAIRO_FONT_SLANT_NORMAL,
                           bold and CAIRO_FONT_WEIGHT_BOLD or CAIRO_FONT_WEIGHT_NORMAL)
    cairo_set_font_size(context, size)
    cairo_text_extents(context, value, extents)
    cairo_move_to(context, x - (align or 0) * extents.x_advance, y)
    cairo_show_text(context, value)
    return extents.x_advance
end

function ui.rounded(context, x, y, width, height, radius)
    cairo_new_path(context)
    cairo_arc(context, x + width - radius, y + radius, radius, -math.pi/2, 0)
    cairo_arc(context, x + width - radius, y + height - radius, radius, 0, math.pi/2)
    cairo_arc(context, x + radius, y + height - radius, radius, math.pi/2, math.pi)
    cairo_arc(context, x + radius, y + radius, radius, math.pi, 3*math.pi/2)
    cairo_close_path(context)
end

-- Line from (x1, y1) to (x2, y2) that fades out toward its end.
function ui.fade(context, x1, y1, x2, y2, color, alpha)
    local line = cairo_pattern_create_linear(x1, y1, x2, y2)
    cairo_pattern_add_color_stop_rgba(line, 0, color[1], color[2], color[3], alpha or 1)
    cairo_pattern_add_color_stop_rgba(line, 1, color[1], color[2], color[3], 0)
    cairo_set_source(context, line)
    cairo_new_path(context)
    cairo_move_to(context, x1, y1)
    cairo_line_to(context, x2, y2)
    cairo_stroke(context)
    cairo_pattern_destroy(line)
end

function ui.glow(context, x, y, radius, color)
    local halo = cairo_pattern_create_radial(x, y, 0, x, y, radius)
    cairo_pattern_add_color_stop_rgba(halo, 0, color[1], color[2], color[3], 0.5)
    cairo_pattern_add_color_stop_rgba(halo, 1, color[1], color[2], color[3], 0)
    cairo_set_source(context, halo)
    cairo_new_path(context)
    cairo_arc(context, x, y, radius, 0, 2*math.pi)
    cairo_fill(context)
    cairo_pattern_destroy(halo)
end

-- Section heading with a hairline fading toward the right edge.
function ui.section(context, label, x, y, right)
    local width = ui.text(context, label:upper(), x, y, 10, ui.colors.primary, 0, true)
    cairo_set_line_width(context, 1)
    ui.fade(context, x + width + 8, y - 3.5, right, y - 3.5, ui.colors.separator)
end

-- Context scaled so the panel is `width` units wide; also returns the height in those units.
function ui.open(width)
    local window = conky_window
    local surface = cairo_xlib_surface_create(window.display, window.drawable, window.visual,
                                              window.width, window.height)
    local context = cairo_create(surface)
    cairo_scale(context, window.width / width, window.width / width)
    cairo_set_line_cap(context, CAIRO_LINE_CAP_ROUND)
    return context, surface, window.height * width / window.width
end

function ui.close(context, surface)
    cairo_destroy(context)
    cairo_surface_destroy(surface)
end

-- Pre-draw hook: a soft glow from the top and a hairline edge, in device pixels.
function conky_backdrop()
    if not conky_window or conky_window.width == 0 then return end
    local width, height = conky_window.width, conky_window.height
    local context, surface = ui.open(width)
    local c = ui.colors
    local wash = cairo_pattern_create_linear(0, 0, 0, height)
    cairo_pattern_add_color_stop_rgba(wash, 0, c.gradient_start[1], c.gradient_start[2], c.gradient_start[3], 0.7)
    cairo_pattern_add_color_stop_rgba(wash, 0.45, c.gradient_end[1], c.gradient_end[2], c.gradient_end[3], 0)
    -- Radius matches corner-radius in picom/picom.conf, which clips these windows.
    ui.rounded(context, 0.5, 0.5, width - 1, height - 1, 14)
    cairo_set_source(context, wash)
    cairo_fill_preserve(context)
    cairo_pattern_destroy(wash)
    cairo_set_line_width(context, 1)
    ui.color(context, c.border, 0.7)
    cairo_stroke(context)
    ui.close(context, surface)
end

return ui
