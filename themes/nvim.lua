-- Setup links this additive spec after the editor's own theme specs.
local path = (vim.env.XDG_STATE_HOME or vim.env.HOME .. "/.local/state")
  .. "/thomas-config/theme/generated/palette.json"
local revision, baseline

local function read()
  local ok, data = pcall(function() return vim.json.decode(table.concat(vim.fn.readfile(path), "\n")) end)
  if ok and type(data) == "table" and type(data.colors) == "table" then return data end
end

local function options(opts, data)
  local c = data.colors
  -- AstroTheme inverts its palette when 'background' disagrees with the scheme.
  vim.o.background = data.mode
  local scheme = data.mode == "light" and "astrolight" or "astrodark"
  local syntax = {
    text = c.text, comment = c.muted, mute = c.muted,
    green = c.primary, cyan = c.primary, blue = c.secondary, purple = c.secondary,
    yellow = c.warning, orange = c.warning, red = c.error,
  }
  local ui = vim.tbl_extend("force", syntax, {
    base = c.background, inactive_base = c.background, tabline = c.background,
    statusline = c.surface, float = c.surface, tool = c.surface, prompt = c.surface,
    current_line = c.surface, highlight = c.surface,
    selection = c.selection, menu_selection = c.selection,
    accent = c.primary, title = c.primary, scrollbar = c.primary,
    border = c.border, split = c.border, winbar = c.muted, none_text = c.muted,
    text_active = c.text, text_inactive = c.muted, text_match = c.primary,
  })
  return vim.tbl_deep_extend("force", vim.deepcopy(opts), {
    style = { title_invert = false }, terminal_colors = false,
    palettes = { [scheme] = { ui = ui, syntax = syntax } },
  }), scheme
end

local function refresh(force)
  local data = read()
  if not data or not baseline or (data.revision == revision and not force) then return end
  local ok, err = pcall(function()
    local opts, scheme = options(baseline, data)
    require("astrotheme").setup(opts)
    vim.cmd.colorscheme(scheme)
    revision = data.revision
  end)
  if not ok then vim.notify("Desktop theme: " .. tostring(err), vim.log.levels.ERROR) end
end

return {
  {
    "AstroNvim/astrotheme",
    opts = function(_, opts)
      baseline = vim.deepcopy(opts)
      local data = read()
      if data then
        revision = data.revision
        return (options(opts, data))
      end
    end,
    init = function()
      vim.api.nvim_create_autocmd("FocusGained", {
        group = vim.api.nvim_create_augroup("DesktopTheme", { clear = true }),
        callback = function() refresh(false) end,
      })
      vim.api.nvim_create_user_command("DesktopThemeReload", function() refresh(true) end, { force = true })
    end,
  },
  {
    "AstroNvim/astroui",
    opts = function(_, opts)
      local data = read()
      if data then opts.colorscheme = data.mode == "light" and "astrolight" or "astrodark" end
    end,
  },
}
