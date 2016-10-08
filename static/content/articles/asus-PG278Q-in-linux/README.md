It was pretty frustrating ending up with a tiny 800x600 resolution with this 27" monitor, with no option to increase it to 2560x1440 using the GUI when using Intel graphics, though with the nVidia proprietary Linux driver it worked great.

I managed to sniff what EDID values the nVidia drivers were getting, and it works fine with Intel graphics if fed it manually; so just do a:

```
xrandr --newmode "2560x1440" 241.5 2560 2608 2640 2720 1440 1443 1448 1481 -hsync +vsync
xrandr --addmode DP1 2560x1440
xrandr --output DP1 --mode 2560x1440
```

and you should be able to see glorious 2560x1400. The intel graphics doesn't seem to be able to push out 120Hz+ though, so it's going to be stuck at 60Hz. 

Instead of running those commands after you start X all the time, you can put it in your /etc/X11/xorg.conf file, here's a sample of mine with dual monitors, though note that the dual monitor setup broke after kernel 4.7, so I had to stick to 4.6.4-201.fc23.x86_64

```
Section "ServerLayout"
    Identifier     "Layout0"
    Screen      0  "Screen0" 0 0
    InputDevice    "Keyboard0" "CoreKeyboard"
    InputDevice    "Mouse0" "CorePointer"
    Option         "Xinerama" "0"
EndSection

Section "Files"
    FontPath        "/usr/share/fonts/default/Type1"
EndSection

Section "InputDevice"
    # generated from default
    Identifier     "Mouse0"
    Driver         "mouse"
    Option         "Protocol" "auto"
    Option         "Device" "/dev/input/mice"
    Option         "Emulate3Buttons" "no"
    Option         "ZAxisMapping" "4 5"
EndSection

Section "InputDevice"
    # generated from default
    Identifier     "Keyboard0"
    Driver         "kbd"
    Option         "XkbOptions" "terminate:ctrl_alt_bksp"
EndSection

# The beef:
***
Section "Monitor"
    Identifier     "DP1"
    VendorName     "Unknown"
    ModelName      "Ancor Communications Inc ROG PG278Q"
    Modeline "2560x1440" 241.5 2560 2608 2640 2720 1440 1443 1448 1481 -hsync +vsync
    Option         "DPMS" "true"
    Option          "RightOf" "HDMI3"
EndSection
***

Section "Monitor"
    Identifier     "HDMI3"
    Option         "LeftOf" "DP1"
    Option         "Primary" "true"
    Option         "DPMS" "true"
EndSection

Section "Device"
    Identifier  "Intel"
    Option      "Monitor-HDMI3" "HDMI3"
    Option      "Monitor-DP1" "DP1"
    Driver         "intel"
EndSection

Section "Screen"
    Identifier     "Screen0"
    Device         "Intel"
    Monitor        "HDMI3"
    DefaultDepth    24
    SubSection     "Display"
        Depth       24
    EndSubSection
EndSection

```



