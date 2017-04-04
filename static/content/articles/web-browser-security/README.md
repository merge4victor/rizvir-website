After reading this [article](http://arstechnica.com/security/2015/08/0-day-attack-on-firefox-users-stole-password-and-key-data-patch-now/)

> The exploit code targeting Linux users uploaded cryptographically protected system passwords, bash command histories, secure shell (SSH) configurations and keys ... text files that contained the strings "pass" and "access" in the names. Any shell scripts were also grabbed.


I vowed to never ever run Firefox or Chromium as my current user. Browser and javascript PDF reader vulnerabilities show up relatively often, and the thought that a site could potentially override my $PATH variable to replace the SSH command to sniff for passwords, or have access to all my personal files, is ridiculous.

The mitigation is really simple; just run your browser as a different user. This way, the browser would not be able to see your personal home directory, but you can set it up so that you can read the browser's home directory (eg. access downloads) without restrictions. 
(This isn't going to be perfect security, because your system may have local privilege escalation vulnerabilities, so continue having your system update-to-date as often as possible.)

The process of running the browser as a different user should be straight-forward, but the main complications is having audio working with PulseAudio.


### Setting up the basics

Create a user that the browser would run under as (assuming ACLs is enabled in your filesystem, which is the default in most distros) by running these commands (replace MAINUSER=rizvir with your actual linux username):

```
MAINUSER=rizvir
BROWSERUSER=browser
useradd -s /sbin/nologin $BROWSERUSER
setfacl --recursive --modify "u:$MAINUSER:rwx" /home/$BROWSERUSER
setfacl --recursive --modify "u:$BROWSERUSER:rwx" /home/$BROWSERUSER
setfacl --recursive --default --modify "u:$MAINUSER:rwx" /home/$BROWSERUSER
setfacl --recursive --default --modify "u:$BROWSERUSER:rwx" /home/$BROWSERUSER
```

Add a sudo rule as root to allow your current user to run your browser as your user, by appending this using visudo (replace rizvir with your username):

```
Defaults!/usr/bin/firefox always_set_home, env_keep += "PULSE_SERVER"
rizvir ALL=(browser) NOPASSWD: /usr/bin/firefox
```

That's it. Close your browser, and run:

```bash
xhost "+si:localuser:browser"
sudo -u browser firefox
```

Whatever files you save in the browser should be accessible by your main account, and to upload/access your files from the browser, just copy the files into the browser's home directory.

If it works, you can create shortcuts to this command. In KDE, right click the KDE menu launcher, and click Edit Applications. Then right click Internet and click on New Item, with some name, say "Firefox DMZ", and the launch command `sh -c "xhost +si:localuser:browser ; sudo -u browser firefox"`.

That should be it for the basics in Fedora, but in Ubuntu, it seems users can read other user's files by default, so change that with:

`chmod 750 /home/youruser/`


### Getting audio working

Once you try watching a youtube video, you will soon discover that it'd have no audio in your new extra-secure browser setup. The problem is that PulseAudio only allows sound from the same user the daemon was launched as; so the 'browser' user has no permissions to talk to PulseAudio.
The most straight forward option might be to enable PulseAudio's system daemon, but that seems to be not recommended at all. So instead, we'll just make PulseAudio's normal user daemon listen on a TCP port on the localhost, and then have the browser's pulseaudio client connect to that network port via localhost.

Before anything, you should backup your existing working PulseAudio configuration somewhere, as it's trivial to mess it up and can be [extremely difficult](https://www.reddit.com/r/archlinux/comments/2htnr2/so_i_accidentally_deleted_my_configpulse_folder/) to fix. So just backup `/etc/pulse`, `~/.config/pulse` and `~/.pulse` if they exist.

Then copy the configuration file to your real user's home directory, unless you did this before, append this configuration line to enable it to listen on the network, and restart pulseaudio:
```bash
mkdir -p ~/.config/pulse
cp -iv /etc/pulse/default.pa ~/.config/pulse 
echo "load-module module-native-protocol-tcp auth-ip-acl=127.0.0.1 listen=127.0.0.1 auth-cookie-enabled=true" >> ~/.config/pulse/default.pa
pulseaudio --kill
pulseaudio --start --log-target=syslog
```

You should now see pulseaudio listening on 127.0.0.1 if you do a `sudo netstat -lptun | grep pulseaudio`. Hopefully, you didn't break your normal audio at this stage, so run a non-secure-browser audio test, such as firefox as your normal/main user, to verify that your audio is A-OK as usual.

Now to set it up for the browser user:
```bash
sudo -u browser bash  # or, as root, su -m browser
mkdir -p ~browser/.config/pulse
cat << EOF > ~browser/.config/pulse/client.conf
autospawn = no
default-server = tcp4:127.0.0.1
EOF
```

Stop your secured browser if it's running, and start it up via the sudo command above. If all goes well, you should have audio in your isolated browser.


