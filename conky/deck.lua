-- Geometry of the cards, placed down both sides where the wallpaper's character leaves room.
-- Loaded by the *.conf files; a unit is 1/1440 of the primary monitor's width (1.33 px on 1920).
local function output(command)
    local pipe = io.popen(command .. ' 2>/dev/null')
    local text = pipe and pipe:read('*a') or ''
    if pipe then pipe:close() end
    return text
end

-- shortcut: Conky aligns to its first head; set xinerama_head when the primary monitor is not that one.
local monitors = output('xrandr --current')
local screen = tonumber(monitors:match('primary (%d+)x') or monitors:match(' connected (%d+)x')) or 1920
-- Conky multiplies sizes by Xft.dpi/96; dividing it out keeps the cards in place at any zoom.
local dpi = tonumber(output('xrdb -query'):match('Xft%.dpi:%s*([%d.]+)')) or 96
local factor = screen / 1440 / (dpi / 96)
-- Polybar is 36 px plus two 8 px borders (polybar/shapes/config.ini), whatever the zoom.
local bar = 52 / (dpi / 96)

-- y counts from the bar for top cards and from the screen edge for bottom ones, x from the side (16 unless given);
-- each card's Lua file uses the same width.
-- shortcut: the places suit wallpapers/hoppers.png, which every theme uses; move the cards when one differs.
local function card(alignment, y, width, height, x)
    local function size(units) return math.floor(units * factor + 0.5) end
    local top = alignment:find('top') and math.floor(bar + 0.5) or 0
    return {alignment = alignment, x = size(x or 16), y = size(y) + top, width = size(width), height = size(height)}
end

-- 16 units from the screen edges and 10 between cards: a second card starts at 16 + 268 + 10.
return {
    weather = card('top_left', 16, 320, 268),
    -- Above the head, from weather's right edge (16 + 320 + 10) to system's left.
    year = card('top_left', 16, 660, 70, 346),
    forecast = card('top_left', 294, 172, 175),
    -- In the gap between week and hours, short of the hand.
    playing = card('top_left', 479, 264, 86),
    -- Over the tail, short of the arm above and the body to its right.
    hours = card('bottom_left', 16, 344, 180),
    system = card('top_right', 16, 408, 268),
    momentum = card('bottom_right', 294, 408, 183),
    calendar = card('bottom_right', 16, 592, 268),
}
