# !/bin/bash
# Copy my-env file to ~/.my-env before run
# Assume we have github token
DEFAULT_PACKAGE_MANAGER="apt"
cd ~

# Install this setup first
# git clone git@github.com:Thomastienn/config.git
# mv ~/config ~/thomas_config
# Install font: ComicShannsMono Nerd Font

# Set up bash, tmux
rm -f ~/.bashrc
rm -f ~/.bash_aliases
rm -f ~/.tmux.conf
ln -s ~/thomas_config/bashrc ~/.bashrc
ln -s ~/thomas_config/bash_aliases ~/.bash_aliases
ln -s ~/thomas_config/tmux.conf ~/.tmux.conf

# UPDATE (in a ble.sh session)
#> ble-update
# UPDATE (outside ble.sh sessions)
#> bash /path/to/ble.sh --update
# Ble.sh for bash enhancements
sudo ${DEFAULT_PACKAGE_MANAGER} install gawk
git clone --recursive --depth 1 --shallow-submodules https://github.com/akinomyoga/ble.sh.git
make -C ble.sh install PREFIX=~/.local
ln -s ~/thomas_config/blerc ~/.blerc


# Set up i3wm
sudo ${DEFAULT_PACKAGE_MANAGER} install i3 i3status i3lock dmenu suckless-tools picom feh polybar playerctl conky-all -y
rm -rf ~/.config/i3
ln -s ~/thomas_config/i3 ~/.config/i3
## Scaling global
rm -f ~/.Xresources
rm -f ~/.xinitrc
ln -s ~/thomas_config/Xresources ~/.Xresources
ln -s ~/thomas_config/xinitrc ~/.xinitrc
## Polybar
### Default
# rm -rf ~/.config/polybar
# mkdir -p ~/.config/polybar
# ln -s ~/thomas_config/polybar/config ~/.config/polybar/config
### Preconfigured
git clone --depth=1 https://github.com/adi1090x/polybar-themes.git
cd polybar-themes && chmod +x setup.sh && ./setup.sh && cd -
rm ~/.config/polybar/hack
ln -s ~/thomas_config/polybar/hack ~/.config/polybar/hack
## lxappearance
sudo ${DEFAULT_PACKAGE_MANAGER} install lxappearance -y
## Touch egg
sudo add-apt-repository ppa:touchegg/stable
sudo ${DEFAULT_PACKAGE_MANAGER} install touchegg -y
# Screen shot
sudo ${DEFAULT_PACKAGE_MANAGER} install flameshot -y
# Rofi
rm -rf ~/.config/rofi
ln -s ~/thomas_config/rofi ~/.config/rofi
# End i3wm


# Install screen brightness
sudo apt install brightnessctl

# Install asusctl and supergfxd for Asus laptops
# curl -sSL https://raw.githubusercontent.com/andreas-glaser/asus-linux-mint/main/install-asus-linux.sh | bash

# Install tlp for battery management (and performance)
sudo ${DEFAULT_PACKAGE_MANAGER} install tlp tlp-rdw -y

# Set up picom
rm -rf ~/.config/picom
ln -s ~/thomas_config/picom ~/.config/picom

# Set up kitty
curl -L https://sw.kovidgoyal.net/kitty/installer.sh | sh /dev/stdin
rm -rf ~/.config/kitty
ln -s ~/thomas_config/kitty ~/.config/kitty

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

# Vibe coding
npm install -g @google/gemini-cli
npm install -g @github/copilot

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
