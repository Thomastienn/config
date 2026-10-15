# Shared by keyboard brightness controls and Eww.
backlight=(brightnessctl -c backlight)
device=${THOMAS_BACKLIGHT:-nvidia_wmi_ec_backlight}
if [[ -d /sys/class/backlight/$device ]]; then
    backlight=(brightnessctl -d "$device")
fi
