alias rm='trash'
alias nnn='nnn -Pp'
alias tmux-warp='WARP_IS_LOCAL_SHELL_SESSION=1 tmux'
alias ex='explorer.exe'
alias tw='taskwarrior-tui'
labtest=/home/thomastien/lab/test_microservices

open_nvim(){
	if [ "$1" = "y" ]; then
	    nvim
	  else
	    echo "Done."
	  fi
}
go_d(){
	cd /mnt/d/
}
kcom(){
	cd ~/kaggle/competition
}
download(){
	cd /mnt/c/Users/thoma/Downloads
}
diary(){
	go_d
	cd May\ MSI/DiaryProgram
	open_nvim "$1"
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
aov24(){
	go_d
	cd AventOfCode/2024
	open_nvim "$1"
}
cod25(){
	go_d
	cd codyssi/2025
	open_nvim "$1"
}
cpfiles(){
	go_d
	cd cpFiles
	open_nvim "$1"
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
