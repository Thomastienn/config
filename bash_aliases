alias rm='trash'
alias nnn='nnn -Pp'
alias tmux-warp='WARP_IS_LOCAL_SHELL_SESSION=1 tmux'
alias tw='taskwarrior-tui'
alias python='python3'

open_nvim(){
	if [ "$1" = "y" ]; then
	    nvim
	  else
	    echo "Done."
	  fi
}
kcom(){
	cd ~/kaggle/competition
}
base(){
	cd ~/CodeBase
	nvim
}
repo(){
	cd ~/repos
	open_nvim "$1"
}
bot(){
	repo	
	cd my_bot
	nvim
}
unihelp(){
	cd ~/repos
	cd uni-assistant
	open_nvim "y"
}
vconfig(){
	cd ~/.config/nvim
	nvim
}
stuff(){
	cd ~/random_stuff/
	nvim
}
uofc(){
	cd ~/ucalgary/
	nvim
}
solve(){
	cd ~/solve
	nvim
}
mtest(){
	cd ~/test
	nvim
}
