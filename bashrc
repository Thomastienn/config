export COLORTERM=truecolor
export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export TERMINAL=kitty


# Load centralized theme
source ~/thomas_config/theme.sh

# Tokens ENV
# Load environment variables from ~/.my_env if it exists
# Too risky
# if [ -f "$HOME/.my-env" ]; then
#     export $(grep -v '^#' "$HOME/.my-env" | xargs)
# fi

# ~/.bashrc: executed by bash(1) for non-login shells.
# see /usr/share/doc/bash/examples/startup-files (in the package bash-doc)
# for examples

# If not running interactively, don't do anything
case $- in
    *i*) ;;
      *) return;;
esac

# don't put duplicate lines or lines starting with space in the history.
# See bash(1) for more options
HISTCONTROL=ignoreboth

# append to the history file, don't overwrite it
shopt -s histappend

# Enhanced history settings
HISTSIZE=10000
HISTFILESIZE=20000
HISTTIMEFORMAT="%F %T "
HISTCONTROL=ignoreboth:erasedups
# Save and reload history after each command
PROMPT_COMMAND="history -a; history -c; history -r; $PROMPT_COMMAND"

# check the window size after each command and, if necessary,
# update the values of LINES and COLUMNS.
shopt -s checkwinsize

# If set, the pattern "**" used in a pathname expansion context will
# match all files and zero or more directories and subdirectories.
#shopt -s globstar

# make less more friendly for non-text input files, see lesspipe(1)
[ -x /usr/bin/lesspipe ] && eval "$(SHELL=/bin/sh lesspipe)"

# set variable identifying the chroot you work in (used in the prompt below)
if [ -z "${debian_chroot:-}" ] && [ -r /etc/debian_chroot ]; then
    debian_chroot=$(cat /etc/debian_chroot)
fi

# set a fancy prompt (non-color, unless we know we "want" color)
case "$TERM" in
    xterm-color|*-256color) color_prompt=yes;;
esac

# uncomment for a colored prompt, if the terminal has the capability; turned
# off by default to not distract the user: the focus in a terminal window
# should be on the output of commands, not on the prompt
force_color_prompt=yes

if [ -n "$force_color_prompt" ]; then
    if [ -x /usr/bin/tput ] && tput setaf 1 >&/dev/null; then
	# We have color support; assume it's compliant with Ecma-48
	# (ISO/IEC-6429). (Lack of such support is extremely rare, and such
	# a case would tend to support setf rather than setaf.)
	color_prompt=yes
    else
	color_prompt=
    fi
fi

# Git prompt: branch plus * unstaged, + staged, % untracked, ↑ unpushed, ↓ unpulled
[ -f /usr/lib/git-core/git-sh-prompt ] && . /usr/lib/git-core/git-sh-prompt
GIT_PS1_SHOWDIRTYSTATE=1
GIT_PS1_SHOWUNTRACKEDFILES=1
git_prompt() {
    local s ahead behind
    s=$(__git_ps1 '%s' 2>/dev/null)
    [ -n "$s" ] || return
    read -r behind ahead < <(git rev-list --left-right --count '@{upstream}...HEAD' 2>/dev/null)
    ((ahead)) && s+=" ↑$ahead"
    ((behind)) && s+=" ↓$behind"
    echo " ($s)"
}

# ❯ is mint, rose after a failed command; prompt_status is set by the ble.sh PRECMD hook below.
prompt_marks=("${THEME_COLOR4@E}" "${THEME_COLOR5@E}")

# Disable default virtual environment prompt modification
export VIRTUAL_ENV_DISABLE_PROMPT=1

# Custom function to show venv name
show_virtual_env() {
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "($(basename $VIRTUAL_ENV)) "
    fi
}

if [ "$color_prompt" = yes ]; then
	# Cozy Mint prompt; clock and system status live in the desktop bar/widgets
	PS1="\[${THEME_COLOR1}\]\$(show_virtual_env)\[${THEME_COLOR2}\]\u\[${THEME_COLOR4}\]@\[${THEME_COLOR3}\]\h\[${THEME_RESET}\] \[${THEME_COLOR6}\]\w\[${THEME_COLOR1}\]\$(git_prompt)\[${THEME_RESET}\]\n\[\${prompt_marks[prompt_status > 0]}\]❯ \[${THEME_RESET}\]"
else
    PS1='$(show_virtual_env)\u@\h:\w$(git_prompt)\n> '
fi
unset color_prompt force_color_prompt

#If this is an xterm set the title to user@host:dir
case "$TERM" in
xterm*|rxvt*)
    PS1="\[\e]0;${debian_chroot:+($debian_chroot)}\u@\h: \w\a\]$PS1"
    ;;
*)
    ;;
esac

# enable color support of ls and also add handy aliases
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    #alias dir='dir --color=auto'
    #alias vdir='vdir --color=auto'

    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# colored GCC warnings and errors
#export GCC_COLORS='error=01;31:warning=01;35:note=01;36:caret=01;32:locus=01:quote=01'

# Enhanced ls aliases with colors and icons
alias ls='eza --color=auto --icons'
alias ll='ls -alF --group-directories-first'
alias la='eza -la --icons --color=auto'
alias l='ls -CF --group-directories-first'
alias lt='ls -alFtr'  # Sort by time, newest last
alias lh='ls -alFh'   # Human readable sizes

# Cool utility aliases
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias ~='cd ~'
alias c='clear'
alias h='history'
alias hg='history | grep'
alias psg='ps aux | grep'
alias mkdir='mkdir -pv'
alias path='echo -e ${PATH//:/\\n}'
alias now='date +"%T"'
alias nowtime=now
alias nowdate='date +"%d-%m-%Y"'

# Git aliases
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline --graph --decorate --all'
alias gd='git diff'
alias gb='git branch'
alias gco='git checkout'

# Add an "alert" alias for long running commands.  Use like so:
#   sleep 10; alert
alias alert='notify-send --urgency=low -i "$([ $? = 0 ] && echo terminal || echo error)" "$(history|tail -n1|sed -e '\''s/^\s*[0-9]\+\s*//;s/[;&|]\s*alert$//'\'')"'

# Alias definitions.
# You may want to put all your additions into a separate file like
# ~/.bash_aliases, instead of adding them here directly.
# See /usr/share/doc/bash-doc/examples in the bash-doc package.

if [ -f ~/.bash_aliases ]; then
    . ~/.bash_aliases
fi

# enable programmable completion features (you don't need to enable
# this, if it's already enabled in /etc/bash.bashrc and /etc/profile
# sources /etc/bash.bashrc).
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

export EDITOR=nvim
export VISUAL=nvim
[ -d "$HOME/my_bin" ] && export PATH="$HOME/my_bin:$PATH"
[ -d "$HOME/my_bin/vcpkg" ] && export PATH="$HOME/my_bin/vcpkg:$PATH"
[ -d "$HOME/my_bin/cmake-4.1.1-linux-x86_64/bin" ] && export PATH="$HOME/my_bin/cmake-4.1.1-linux-x86_64/bin:$PATH"
[ -d "$HOME/my_bin/mongodb-linux-x86_64-ubuntu2204-7.0.5/bin" ] && export PATH="$HOME/my_bin/mongodb-linux-x86_64-ubuntu2204-7.0.5/bin:$PATH"
[ -d "$HOME/.local/bin/typst" ] && export PATH="$HOME/.local/bin/typst:$PATH"
[ -d "$HOME/.local/kitty.app/bin" ] && export PATH="$HOME/.local/kitty.app/bin:$PATH"
[ -d "/opt/nvim-linux-x86_64/bin" ] && export PATH="/opt/nvim-linux-x86_64/bin:$PATH"

[ -d "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
[ -d "$HOME/.cargo/bin" ] && export PATH="$HOME/.cargo/bin:$PATH"
[ -d "/home/linuxbrew/.linuxbrew/bin" ] && export PATH="$PATH:/home/linuxbrew/.linuxbrew/bin"

[ -d "/home/linuxbrew/.linuxbrew/opt/imagemagick/lib/pkgconfig" ] && export PKG_CONFIG_PATH="/home/linuxbrew/.linuxbrew/opt/imagemagick/lib/pkgconfig:$PKG_CONFIG_PATH"

[ -d "$HOME/eww/target/release" ] && export PATH="$HOME/eww/target/release:$PATH"

[ -d "$HOME/typst/" ] && export PATH="$HOME/typst/:$PATH"

export WARP_ENABLE_WAYLAND=1
export BROWSER=brave-browser

export NNN_TERMINAL=tmux
export NNN_PLUG='p:preview-tui'
export NNN_FIFO="/tmp/nnn.fifo"
export NNN_PREVIEWIMGPROG="ueberzug"

LS_COLORS=$LS_COLORS:'ow=1;34:' ; export LS_COLORS

[ -s "$HOME/.nvm/nvm.sh" ] && \. "$HOME/.nvm/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# ================================================================
# AUTO-START TMUX (After full initialization)
# ================================================================

# Function to auto-start tmux with intelligent session management
auto_start_tmux() {
    # Only run if:
    # 1. We're in an interactive shell
    # 2. Not already inside tmux
    # 3. Not in VS Code integrated terminal
    # 4. Not in a nested SSH session
    # 5. Not in Warp terminal
    # 6. tmux is available
    
    if [[ $- == *i* ]] && \
       [[ -z "$TMUX" ]] && \
       [[ -z "$VSCODE_INJECTION" ]] && \
       [[ -z "$SSH_TTY" ]] && \
       [[ "$TERM_PROGRAM" != "WarpTerminal" ]] && \
       [[ -z "$WARP_IS_LOCAL_SHELL_SESSION" ]] && \
       command -v tmux >/dev/null 2>&1; then
        # Attach to the most recent session if one exists
        if tmux list-sessions >/dev/null 2>&1; then
            tmux attach-session
        else
            # Create a new session named after the current directory or 'main'
            local session_name=$(basename "$PWD" | tr '.' '_')
            [[ -z "$session_name" ]] && session_name="main"
            tmux new-session -s "$session_name"
        fi
    fi
}

# Auto-start tmux after shell initialization is complete
# This runs at the very end of .bashrc when everything is loaded
auto_start_tmux

# Cool functions
weather() {
    curl -s "http://wttr.in/$1?format=3"
}

sysinfo() {
    echo -e "\e[1;36m╔══════════════════════════════════════╗\e[0m"
    echo -e "\e[1;36m║           SYSTEM INFORMATION         ║\e[0m"
    echo -e "\e[1;36m╠══════════════════════════════════════╣\e[0m"
    echo -e "\e[1;32m║ OS:       \e[0m$(lsb_release -d | cut -f2)"
    echo -e "\e[1;32m║ Kernel:   \e[0m$(uname -r)"
    echo -e "\e[1;32m║ Uptime:   \e[0m$(uptime -p)"
    echo -e "\e[1;32m║ Load:     \e[0m$(uptime | awk '{print $10,$11,$12}')"
    echo -e "\e[1;32m║ Memory:   \e[0m$(free -h | awk 'NR==2{printf "%.1f/%.1fGB (%.2f%%)\n", $3/1024/1024,$2/1024/1024,$3*100/$2 }')"
    echo -e "\e[1;32m║ Disk:     \e[0m$(df -h $HOME | awk 'NR==2{printf "%s/%s (%s)\n", $3,$2,$5}')"
    echo -e "\e[1;36m╚══════════════════════════════════════╝\e[0m"
}

# Extract function for various archive types
extract() {
    if [ -f $1 ]; then
        case $1 in
            *.tar.bz2)   tar xjf $1     ;;
            *.tar.gz)    tar xzf $1     ;;
            *.bz2)       bunzip2 $1     ;;
            *.rar)       unrar e $1     ;;
            *.gz)        gunzip $1      ;;
            *.tar)       tar xf $1      ;;
            *.tbz2)      tar xjf $1     ;;
            *.tgz)       tar xzf $1     ;;
            *.zip)       unzip $1       ;;
            *.Z)         uncompress $1  ;;
            *.7z)        7z x $1        ;;
            *)     echo "'$1' cannot be extracted via extract()" ;;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}

# Cozy Mint greeting and name artwork

# Dynamic greeting based on time of day
HOUR=$(date +%H)
if [ $HOUR -ge 5 ] && [ $HOUR -lt 12 ]; then
    GREETING="Good Morning, Thomas"
elif [ $HOUR -ge 12 ] && [ $HOUR -lt 17 ]; then
    GREETING="Good Afternoon, Thomas"
elif [ $HOUR -ge 17 ] && [ $HOUR -lt 21 ]; then
    GREETING="Good Evening, Thomas"
else
    GREETING="Good Night, Thomas"
fi

# Neovim terminals set $NVIM; keep the banner to real shells.
if [ -z "$NVIM" ]; then
    echo
    echo -e "  ${THEME_COLOR3}${THEME_BOLD}${GREETING}${THEME_RESET}"
    echo
    echo -e "${THEME_COLOR1}      ████████ ██   ██  ██████  ███    ███  █████  ███████${THEME_RESET}"
    echo -e "${THEME_COLOR1}         ██    ██   ██ ██    ██ ████  ████ ██   ██ ██     ${THEME_RESET}"
    echo -e "${THEME_COLOR1}         ██    ███████ ██    ██ ██ ████ ██ ███████ ███████${THEME_RESET}"
    echo -e "${THEME_COLOR1}         ██    ██   ██ ██    ██ ██  ██  ██ ██   ██      ██${THEME_RESET}"
    echo -e "${THEME_COLOR1}         ██    ██   ██  ██████  ██      ██ ██   ██ ███████${THEME_RESET}"
    echo
fi


# MY CUSTOM FUNCTIONS AND ALIASES
code2pdf() {
    # Sample
    # → enscript -Ec -o - exercises/bubblesort.c | ps2pdf - bubblesort.pdf
    # Usage: code2pdf <language> <source_file> <output_pdf_name>
    if [ "$#" -ne 3 ]; then
        echo "Usage: code2pdf <language> <source_file> <output_pdf_name>"
        return 1
    fi

    local language=$1
    local source_file=$2
    local output_pdf=$3

    enscript -E"$language" -o - "$source_file" | ps2pdf - "$output_pdf"
}

# include following in .bashrc / .bash_profile / .zshrc
# usage
# $ mkvenv myvirtualenv # creates venv under ~/.virtualenvs/
# $ venv myvirtualenv   # activates venv
# $ deactivate          # deactivates venv
# $ rmvenv myvirtualenv # removes venv

export VENV_HOME="$HOME/.virtualenvs"
[[ -d $VENV_HOME ]] || mkdir $VENV_HOME

lsvenv() {
  ls -1 $VENV_HOME
}

venv() {
  if [ $# -eq 0 ]
    then
      echo "Please provide venv name"
    else
      source "$VENV_HOME/$1/bin/activate"
  fi
}

mkvenv() {
  if [ $# -eq 0 ]
    then
      echo "Please provide venv name"
    else
      python3 -m venv $VENV_HOME/$1
  fi
}

rmvenv() {
  if [ $# -eq 0 ]
    then
      echo "Please provide venv name"
    else
      rm -r $VENV_HOME/$1
  fi
}

# bat (cat)
export BAT_THEME="Monokai Extended"

# fzf in Cozy Mint; key bindings come from blerc
export FZF_DEFAULT_OPTS="--height=40% --layout=reverse --border=rounded --info=inline \
--color=fg:#EEE8DC,bg:-1,hl:#A7CCAE,fg+:#EEE8DC,bg+:#272C27,hl+:#A7CCAE \
--color=info:#ABAFA4,prompt:#A7CCAE,pointer:#C0AFD5,marker:#C0AFD5,spinner:#C0AFD5,header:#ABAFA4,border:#5D6D5E,gutter:-1"

# zoxide
eval "$(zoxide init bash)"

# SSH agent: reuse a live one (inherited, GNOME gcr, or one fixed socket) instead of one per shell.
ssh-add -l >/dev/null 2>&1
if [ $? -eq 2 ]; then
    if [ -S "$XDG_RUNTIME_DIR/gcr/ssh" ]; then
        export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/gcr/ssh"
    else
        export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.sock"
        ssh-add -l >/dev/null 2>&1
        [ $? -eq 2 ] && rm -f "$SSH_AUTH_SOCK" && eval "$(ssh-agent -s -a "$SSH_AUTH_SOCK")" >/dev/null
    fi
fi
ssh-add -l >/dev/null 2>&1 || ssh-add -q ~/.ssh/id_ed25519 ~/.ssh/id_ed25519_github ~/.ssh/id_ed25519_gitlab 2>/dev/null

# Task calendar and next tasks are visible in Conky; use task for details.

# Unbind Ctrl-S and Ctrl-Q to avoid terminal freeze
stty -ixon

[ -d "$HOME/.virtualenvs/neovim" ] && venv neovim

# Ble.sh
if [[ -f "$HOME/.local/share/blesh/ble.sh" ]]; then
    # ble.sh loads ~/.blerc (-> thomas_config/blerc) itself.
    source -- ~/.local/share/blesh/ble.sh
    # $(...) in PS1 clobbers $?, and wakatime's PROMPT_COMMAND runs first; PRECMD still sees the real status.
    blehook PRECMD+='prompt_status=$?'
    bleopt default_keymap=vi
    ble-bind -m vi_imap -f 'j j' vi_imap/normal-mode
    ble-bind -m vi_imap -T j 200
else
    set -o vi
    bind 'set keyseq-timeout 200'
    bind -m vi-insert '"jj": vi-movement-mode'
fi


# Has to be at the end
export SDKMAN_DIR="/home/thomas/.sdkman"
[[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]] && source "/home/thomas/.sdkman/bin/sdkman-init.sh"

[[ -d "$HOME/CodeBase/grindstone/" ]] && alias grind="~/CodeBase/grindstone/main.py"

[[ -d "$HOME/go" ]] && export PATH="$PATH:$HOME/go/bin"
[ -f "$HOME/.deno/env" ] && source "$HOME/.deno/env"

# terminal-wakatime setup
if [ -d "$HOME/.wakatime" ]; then
    export PATH="$HOME/.wakatime:$PATH"
    eval "$(terminal-wakatime init)"
fi
export QT_QPA_PLATFORMTHEME=gtk3

# Added by codebase-memory-mcp install
export PATH="/home/thomas/.local/bin:$PATH"

eval "$(thefuck --alias)"
. "$HOME/.rokit/env"

[ -f "/home/thomas/.ghcup/env" ] && . "/home/thomas/.ghcup/env" # ghcup-env
