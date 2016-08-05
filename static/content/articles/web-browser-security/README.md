After reading this [article](http://arstechnica.com/security/2015/08/0-day-attack-on-firefox-users-stole-password-and-key-data-patch-now/)

> The exploit code targeting Linux users uploaded cryptographically protected system passwords, bash command histories, secure shell (SSH) configurations and keys ... text files that contained the strings "pass" and "access" in the names. Any shell scripts were also grabbed.


I vowed to never ever run Firefox or Chromium as my current user. Browser and PDF read vulnerabilities show up relatively often, and the thought that a site could potentially override my $PATH variable to replace the SSH command to sniff for passwords, or have access to all my personal files, is ridiculous.

The mitigation is really simple; just run your browser as a different user. This way, the browser would not be able to see your personal home directory, but you can set it up so that you can read the browser's home directory (eg. access downloads) without restrictions. 
(This isn't going to be perfect security, because your system may have local privilege escalation vulnerabilities, so continue having your system update-to-date as often as possible.)

The process of running the browser as a different user should be straight-forward, but the main complications is having audio working with PulseAudio.


### Setting up the basics

Create a user that the browser would run under as (assuming ACLs is enabled in your filesystem):

```
useradd -s /sbin/nologin browser
MAINUSER=rizvir
BROWSERUSER=browser
setfacl --recursive --modify "u:$MAINUSER:rwx" /home/$BROWSERUSER
setfacl --recursive --modify "u:$BROWSERUSER:rwx" /home/$BROWSERUSER
setfacl --recursive --default --modify "u:$MAINUSER:rwx" /home/$BROWSERUSER
setfacl --recursive --default --modify "u:$BROWSERUSER:rwx" /home/$BROWSERUSER
```

Add a sudo rule as root to allow your current user to run your browser as your user, by appending this using visudo (replace rizvi with your username):

```
Defaults!/usr/bin/firefox always_set_home, env_keep += "PULSE_SERVER"
rizvi ALL=(browser) NOPASSWD: /usr/bin/firefox
````

That's it. Close your browser, and run:

```bash
xhost "+si:localuser:browser"
sudo -u browser firefox
````

Whatever files you save in the browser should be accessible by your main account, and to upload/access your files from the browser, just copy the files into the browser's home directory.

If it works, you can create shortcuts to this command. In KDE, right click the KDE menu launcher, and click Edit Applications. Then right click Internet and click on New Item, with the name Firefox DMZ" and the above sudo command. You will also have to add the `xhost "+si:localuser:browser"` command to your X startup using the GNOME/KDE/XFCE/whatever startup editor.

That should be it for the basics in Fedora, but in Ubuntu, it seems users can read other user's files by default, so change that with:

`chmod 750 /home/youruser/`






