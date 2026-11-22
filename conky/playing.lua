-- Now playing card: the first MPRIS player's track and how far through it is, from playerctl.
local ui = dofile(os.getenv('HOME') .. '/thomas_config/conky/panel.lua')
local c = ui.colors

-- 264 units wide, as sized in deck.lua.
local WIDTH, LEFT, RIGHT = 264, 16, 248
local track, loaded

-- Only Cairo draws these fields, so a track's text never becomes Conky commands.
local function load()
    local pipe = io.popen("playerctl metadata --format "
                          .. "'{{status}}\t{{position}}\t{{mpris:length}}\t{{artist}}\t{{title}}' 2>/dev/null")
    local output = pipe and pipe:read('*l') or ''
    if pipe then pipe:close() end
    local status, position, length, artist, title = output:match('^(%a*)\t(%d*)\t(%d*)\t([^\t]*)\t(.*)$')
    -- Position and length are microseconds; a live stream has no length.
    track = title and title ~= '' and {status = status, position = tonumber(position), length = tonumber(length),
                                       artist = artist, title = title} or nil
end

local function clock(microseconds)
    local seconds = math.floor(microseconds / 1e6)
    return string.format('%d:%02d', seconds // 60, seconds % 60)
end

function conky_draw_playing()
    if not conky_window then return end
    -- Expose events redraw without new data; ask the player once per update.
    local update = conky_parse('${updates}')
    if loaded ~= update then
        loaded = update
        load()
    end
    local context, surface = ui.open(WIDTH)
    local playing = track and track.status == 'Playing'
    local timed = track and track.position and track.length and track.length > 0
    local state = not track and '' or not playing and 'Paused'
                  or timed and clock(track.position) .. ' / ' .. clock(track.length) or 'Live'
    ui.section(context, 'Now playing', LEFT, 28, RIGHT - ui.text(context, state, RIGHT, 28, 10, c.muted, 1) - 8)
    if track then
        -- Long titles are cut at the card's padding.
        cairo_save(context)
        cairo_rectangle(context, LEFT, 34, RIGHT - LEFT, 36)
        cairo_clip(context)
        ui.text(context, track.title, LEFT, 50, 11.5, playing and c.text or c.muted, 0, true, ui.family(track.title))
        ui.text(context, track.artist, LEFT, 65, 10, c.muted, 0, false, ui.family(track.artist))
        cairo_restore(context)
    else
        ui.text(context, 'Nothing playing', LEFT, 50, 10.5, c.muted)
    end

    cairo_set_line_width(context, 2)
    ui.color(context, c.border, 0.6)
    ui.line(context, LEFT, 76, RIGHT, 76)
    if timed then
        local tip = LEFT + (RIGHT - LEFT) * math.min(1, track.position / track.length)
        ui.color(context, c.primary, playing and 1 or 0.5)
        ui.line(context, LEFT, 76, tip, 76)
        if playing then
            ui.glow(context, tip, 76, 7, c.primary)
            ui.color(context, c.text)
            cairo_new_path(context)
            cairo_arc(context, tip, 76, 2, 0, 2*math.pi)
            cairo_fill(context)
        end
    end
    ui.close(context, surface)
end
