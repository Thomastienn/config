# !/bin/bash
# Copy my-env file to ~/.my-env before run
# Assume we have github token
DEFAULT_PACKAGE_MANAGER="apt"
cd ~

# Install this setup first
# git clone git@github.com:Thomastienn/config.git
# mv ~/config ~/thomas_config

# Set up bash, tmux
rm -f ~/.bashrc
rm -f ~/.bash_aliases
rm -f ~/.tmux.conf
ln -s ~/thomas_config/bashrc ~/.bashrc
ln -s ~/thomas_config/bash_aliases ~/.bash_aliases
ln -s ~/thomas_config/tmux.conf ~/.tmux.conf

# Set up i3wm
sudo ${DEFAULT_PACKAGE_MANAGER} install i3 i3status i3lock dmenu suckless-tools picom feh polybar -y
rm -f ~/.config/i3/config
mkdir -p ~/.config/i3
ln -s ~/thomas_config/i3/config ~/.config/i3/config
# Scaling global
rm -f ~/.Xresources
rm -f ~/.xinitrc
ln -s ~/thomas_config/Xresources ~/.Xresources
ln -s ~/thomas_config/xinitrc ~/.xinitrc
# Polybar
# Default
rm -rf ~/.config/polybar
mkdir -p ~/.config/polybar
ln -s ~/thomas_config/polybar/config ~/.config/polybar/config
# Preconfigured
git clone --depth=1 https://github.com/adi1090x/polybar-themes.git
cd polybar-themes && chmod +x setup.sh && ./setup.sh && cd -

# Set up picom
rm -f ~/.config/picom/picom.conf
mkdir -p ~/.config/picom
ln -s ~/thomas_config/picom/picom.conf ~/.config/picom/picom.conf

# Set up kitty
curl -L https://sw.kovidgoyal.net/kitty/installer.sh | sh /dev/stdin
mkdir -p ~/.config/kitty
[ -f ~/.config/kitty/kitty.conf ] && rm -f ~/.config/kitty/kitty.conf
ln -s ~/thomas_config/kitty/kitty.conf ~/.config/kitty/kitty.conf
ln -s ~/thomas_config/kitty/current-theme.conf ~/.config/kitty/current-theme.conf

# Set up lsp 
for f in ~/thomas_config/lsp/*.toml; do
    basename=$(basename "$f" .toml)
    mkdir -p ~/.config/"$basename"
    ln -sf "$f" ~/.config/"$basename"/"$(basename "$f")"
done

# Set up brew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
source ~/.bashrc
brew bundle install --file=~/thomas_config/Brewfile

# Set up neovim
cd ~/.config
git clone git@github.com:Thomastienn/astronvimconfig.git
mv astronvimconfig nvim

# Set up virtual venv (python)
# Plugins: molten, minimap
mkvenv neovim
venv neovim
pip install pynvim jupyter_client cairosvg plotly kaleido pnglatex pyperclip ipykernel
deactivate

cargo install code-minimap

# Set up requirements for nvim lsp
# Java
sudo ${DEFAULT_PACKAGE_MANAGER} openjdk-21-jdk maven -y

# Arm64 if needed
# sudo apt install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu binutils-aarch64-linux-gnu qemu-user -y
