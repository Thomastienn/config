# !/bin/bash
# Copy my-env file to ~/.my-env before run
# Assume we have github token
cd ~
git clone git@github.com:Thomastienn/config.git
mv ~/config ~/thomas_config

# Set up bash, tmux
rm -f ~/.bashrc
rm -f ~/.bash_aliases
rm -f ~/.tmux.conf
ln -s ~/thomas_config/bashrc ~/.bashrc
ln -s ~/thomas_config/bash_aliases ~/.bash_aliases
ln -s ~/thomas_config/tmux.conf ~/.tmux.conf

# Set up lsp for f in ~/thomas_config/lsp/*.toml; do
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

# Set up virtual venv
# Plugins: molten, minimap
mkvenv neovim
venv neovim
pip install pynvim jupyter_client cairosvg plotly kaleido pnglatex pyperclip ipykernel
deactivate

cargo install code-minimap

# Set up requirements for nvim lsp
# Java
sudo apt install openjdk-21-jdk maven -y

# Arm64 if needed
# sudo apt install gcc-aarch64-linux-gnu g++-aarch64-linux-gnu binutils-aarch64-linux-gnu qemu-user -y
