export TERM=xterm-kitty
export COLORTERM=truecolor
export LANG=C.UTF-8
export LC_ALL=C.UTF-8

# Tokens ENV
# Load environment variables from ~/.my_env if it exists
if [ -f "$HOME/.my-env" ]; then
    export $(grep -v '^#' "$HOME/.my-env" | xargs)
fi

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
shopt -s histappend
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

# Enhanced Git-aware prompt function
parse_git_branch() {
    git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/ (\1)/'
}

parse_git_status() {
    if git rev-parse --git-dir > /dev/null 2>&1; then
        local status=$(git status --porcelain 2>/dev/null | wc -l)
        if [ $status -gt 0 ]; then
            echo " ⚡$status"
        fi
    fi
}

# Disable default virtual environment prompt modification
export VIRTUAL_ENV_DISABLE_PROMPT=1

# Custom function to show venv name
show_virtual_env() {
    if [ -n "$VIRTUAL_ENV" ]; then
        echo "($(basename $VIRTUAL_ENV)) "
    fi
}

if [ "$color_prompt" = yes ]; then
	# Solarized Light compatible prompt
	# Time: cyan, User: green, Host: blue, Dir: violet, Git: cyan, Git status: orange, Arrow: base01
	PS1='\[\033[38;5;14m\]$(show_virtual_env)\[\033[38;5;6m\][\t]\[\033[00m\] \[\033[38;5;2m\]\u\[\033[38;5;11m\]@\[\033[38;5;4m\]\h\[\033[00m\] \[\033[38;5;13m\]\w\[\033[38;5;6m\]$(parse_git_branch)\[\033[38;5;9m\]$(parse_git_status)\[\033[00m\]\n\[\033[38;5;10m\]→ \[\033[00m\]'
else
    PS1='$(show_virtual_env)[\t] \u@\h:\w$(parse_git_branch)$(parse_git_status)\n> '
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
[ -d "$HOME/.local/bin" ] && export PATH="$HOME/.local/bin:$PATH"
[ -d "$HOME/.local/bin/typst" ] && export PATH="$HOME/.local/bin/typst:$PATH"
[ -d "$HOME/.local/kitty.app/bin" ] && export PATH="$HOME/.local/kitty.app/bin:$PATH"
[ -d "/opt/nvim-linux-x86_64/bin" ] && export PATH="/opt/nvim-linux-x86_64/bin:$PATH"

[ -f "$HOME/.cargo/env" ] && . "$HOME/.cargo/env"
[ -d "$HOME/.cargo/bin" ] && export PATH="$HOME/.cargo/bin:$PATH"

# Only add Windows paths if they exist (WSL)
[ -d "/mnt/c/Windows" ] && export PATH="$PATH:/mnt/c/Windows:/mnt/c/Windows/System32"
[ -d "/mnt/c/Users/thoma/AppData/Local/Microsoft/WindowsApps" ] && export PATH="$PATH:/mnt/c/Users/thoma/AppData/Local/Microsoft/WindowsApps"

[ -d "/home/linuxbrew/.linuxbrew/bin" ] && export PATH="$PATH:/home/linuxbrew/.linuxbrew/bin"

[ -d "/home/linuxbrew/.linuxbrew/opt/imagemagick/lib/pkgconfig" ] && export PKG_CONFIG_PATH="/home/linuxbrew/.linuxbrew/opt/imagemagick/lib/pkgconfig:$PKG_CONFIG_PATH"

export WARP_ENABLE_WAYLAND=1
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
export BROWSER=google-chrome

export NNN_TERMINAL=tmux
export NNN_PLUG='p:preview-tui'
export NNN_FIFO="/tmp/nnn.fifo"
export NNN_PREVIEWIMGPROG="ueberzug"

LS_COLORS=$LS_COLORS:'ow=1;34:' ; export LS_COLORS

[ -s "$HOME/.nvm/nvm.sh" ] && \. "$HOME/.nvm/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# ================================================================
# AUTO-START TMUX ON WSL LOAD (After full initialization)
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
        
        # Wait a moment to ensure WSL is fully loaded
        #sleep 0.5
        
        # Check if there are any existing tmux sessions
        if tmux list-sessions >/dev/null 2>&1; then
            echo "🚀 Found existing tmux sessions:"
            tmux list-sessions
            echo ""
            echo "✨ Attaching to the most recent session..."
            # Attach to the most recent session
            tmux attach-session
        else
            echo "🎯 Starting new tmux session with glassmorphism theme..."
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

# Show enhanced intro with live system info
# Minimalist Terminal Intro
# Uses Windows Terminal theme colors

# Windows Terminal standard colors
COLOR1="\e[34m"      # Blue
COLOR2="\e[35m"      # Magenta
COLOR3="\e[31m"      # Red
COLOR4="\e[33m"      # Yellow
COLOR5="\e[32m"      # Green
COLOR6="\e[36m"      # Cyan
GRAY="\e[90m"        # Bright Black (Gray)
DIM="\e[2m"          # Dim text
RESET="\e[0m"

# Clear terminal with fade effect
clear
echo

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

# Minimalist header
echo -e "${GRAY}─────────────────────────────────────────────────────────────${RESET}"
echo -e "  ${COLOR1}${GREETING}${RESET}"
echo -e "${GRAY}─────────────────────────────────────────────────────────────${RESET}"
echo

# ASCII name
echo -e "${COLOR1}      ████████ ██   ██  ██████  ███    ███  █████  ███████${RESET}"
echo -e "${COLOR1}         ██    ██   ██ ██    ██ ████  ████ ██   ██ ██     ${RESET}"
echo -e "${COLOR1}         ██    ███████ ██    ██ ██ ████ ██ ███████ ███████${RESET}"
echo -e "${COLOR1}         ██    ██   ██ ██    ██ ██  ██  ██ ██   ██      ██${RESET}"
echo -e "${COLOR1}         ██    ██   ██  ██████  ██      ██ ██   ██ ███████${RESET}"
echo

# System info
DATE_TIME=$(date '+%A, %B %d, %Y at %I:%M %p')
echo -e "  ${GRAY}Today:${RESET}    ${DATE_TIME}"

UPTIME=$(uptime -p | sed 's/up //')
echo -e "  ${GRAY}Uptime:${RESET}   ${UPTIME}"

MEMORY=$(free -h | awk 'NR==2{printf "%.1fGB / %.1fGB", $3/1024,$2/1024}')
echo -e "  ${GRAY}Memory:${RESET}   ${MEMORY}"

DISK=$(df -h $HOME | awk 'NR==2{printf "%s / %s", $3,$2}')
echo -e "  ${GRAY}Storage:${RESET}  ${DISK}"

PWD_DISPLAY=$(pwd | sed "s|$HOME|~|")
echo -e "  ${GRAY}Location:${RESET} ${COLOR6}${PWD_DISPLAY}${RESET}"

LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
echo -e "  ${GRAY}Load:${RESET}     ${LOAD}"

echo

# Git status if in a git repository
if git rev-parse --git-dir > /dev/null 2>&1; then
    BRANCH=$(git branch --show-current 2>/dev/null || echo "detached")
    STATUS=$(git status --porcelain 2>/dev/null | wc -l)
    if [ "$STATUS" -eq 0 ]; then
        GIT_STATUS="${COLOR5}clean${RESET}"
    else
        GIT_STATUS="${COLOR4}${STATUS} changes${RESET}"
    fi
    echo -e "  ${GRAY}Git:${RESET}      ${COLOR2}${BRANCH}${RESET} (${GIT_STATUS})"
fi

# Network connectivity test
# ping -c 1 8.8.8.8 > /dev/null 2>&1
# if [ $? -eq 0 ]; then
#     NETWORK="${COLOR5}online${RESET}"
# else
#     NETWORK="${COLOR3}offline${RESET}"
# fi
# echo -e "  ${DIM}Network:${RESET}  ${NETWORK}"

echo

# Ready indicator
echo -e "${GRAY}─────────────────────────────────────────────────────────────${RESET}"
echo -e "  ${COLOR5}Ready${RESET}"
echo

# ================================================================
# Windows Terminal Fix - Auto-applied settings
# ================================================================


#THIS MUST BE AT THE END OF THE FILE FOR SDKMAN TO WORK!!!
export SDKMAN_DIR="$HOME/.sdkman"
[[ -s "$HOME/.sdkman/bin/sdkman-init.sh" ]] && source "$HOME/.sdkman/bin/sdkman-init.sh"


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
export BAT_THEME="Solarized (light)"

# zoxide
eval "$(zoxide init bash)"

# SSH agent
eval "$(ssh-agent -s)"

[ -f ~/.ssh/id_ed25519 ] && ssh-add ~/.ssh/id_ed25519
[ -f ~/.ssh/id_ed25519_github ] && ssh-add ~/.ssh/id_ed25519_github

# taskwarrior display all
[ -f "$HOME/.taskrc" ] && task

# Unbind Ctrl-S and Ctrl-Q to avoid terminal freeze
stty -ixon
