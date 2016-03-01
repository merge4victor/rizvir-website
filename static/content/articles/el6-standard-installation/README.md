If you're running RHEL or CentOS 7, see the updated guide here.

### Before the install

- Set up an iLO/iDRAC/IPMI cable & IP

- Note that if you are installing CentOS/RHEL on an HP server with software RAID (eg. Bxxxi RAID controller), and you want to avoid the proprietary RAID drivers, go to the BIOS options -> System Options -> SATA controler options -> Enable SATA AHCI support (this is [suggested by Red Hat](https://access.redhat.com/site/articles/118133)). If you don't do this, the installation will proceed as usual, but the BIOS will not boot into GRUB (because it will try booting from a non-existent HP RAID volume)

- Make sure your servers come with flash-backed or battery backed write cache. This can lead to a _huge_ increase in performance.

- Set up the partitions depending upon the scenario. Do NOT use ridiculous names for logical volumes like LogVol00, use something that makes sense. The following is generally recommended:
	- /boot - 500MB
	- LVM PV - the rest of the space
		- LV for swap: Depends on the application, but don't make it too high as ideally it should never be actively used. Don't make it too small either as you wouldn't want to face the wrath of the dreaded OOM killer (since slow service could be better than no service). But don't listen to folks who talk about swap always being double the RAM; that's really ridiculous now.
		- LV for root: This depends as well, but if you are completely unfamiliar with the app and the people handling the app aren't sure what mount points are, just have this take up everything minus the 5-15GB empty space below.
		- LVs for your app: Don't go mountpoint-happy; I've seen too many people, esp. those with UNIX backgrounds, insist on a ridiculous number of mount points (for /etc, /usr/, /home, /u009 (?), etc). Over the years, I see this as making less and less sense, because it's an enormous waste of space, and you will inevitably have one mount point desparately in need of space, and the rest of the mount points wasting hundreds of gigabytes sitting idle. They argue about limited damage from filesystem corruption, but in actuality, even just one mount point dies, the app is likely to be unusable anyway, making this point moot. 
		On the other hand, it does make sense to separate the operating system from the main application space, so if most of your app is on a particular directory (like /opt/zimbra, or /var/www, or /var/lib/mysql), it can make sense to separate it because the root filesystem is unlikely to grow, but the app will, and it's easy getting an idea of the space used with df. Also, in the rare chance that your filesystem does get corrupt because of a UPS failure, it's more likely affect your larger heavily used app mountpoint, allowing for at least the OS to boot for you to investigate. Also, you can add security features like noexec,nodev to mount points like /var/www or /tmp.
		- LV for /tmp: Useful in heavily secured servers.
		- Some have a separate partition for /var/log "to prevent excess logs from filling the filesystem", but really, it ends up either being a waste of space, or a hard limit on the logs you can keep, and if you are doing things right, you'd be warned of the filesystem getting full weeks before anyway. But on very heavily secured servers, this is usually a stated requirement.
		- Empty space in the VG: 5-15 GB. This is important for LVM snapshots, as without some empty space in your VG it won't work. The amount depends on the level of changes you expect during a snapshot life/backup.
	- IF you are using software RAID, be sure to not use the whole space on your physical drive, leave around 100MB free or so. This is because a replacement drive with a different model, even though it's the same stated capacity, may not be the exact same size, and md will refuse to add such a replacement to the array even if it's off by a kilobyte. So you're better off making sure everything is ~500MB smaller so that any replacement would work.
	- Again, do not forget to keep some free space in your volume group for snapshots.
	- Install these packages that are not selected by default:
		- Base System 
			- Base -> dos2unix, unix2dos, yum-plugin-security, yum-plugin-changelog
			- Uncheck Java if you don't need it
			- Networking Tools -> iptraf, nc, nmap
			- Performance Tools (defaults)
			- Uncheck printing support if not needed
			- Compatibility libraries is useful for some apps
		- Servers
			- System administration tools -> lsscsi, screen
		- Anything else that may be required. Development & dev tools is useful to have sometimes for compiling tools or drivers if needed.
	

### RHEL subscription

If this is RHEL, assuming you purchased a subscription, you should register the system. If your account is new or does not have a lot of subscription, the auto-attach should be fine:
```
subscription-manager register --username someone@somewhere.com --servicelevel=None|Standard|Premium --auto-attach
```
(if you purchased EUS, you can set a specific release with --release)
That should be it, and you should be done.


But on the other hand, if you had your account for a while, you will most likely want to choose which subscription from your account you'd want to attach to this server, so do a simple registration without an auto-attach:
```
subscription-manager register
```
Then see the available subscriptions and guess which one's yours (it crazily multiplies the purchased subsciptions by 2, all because it doesn't support floating point numbers for virtual subscriptions (which would otherwise be 0.5 subscriptions)):
```
subscription-manager  list --available
```
Note the Pool ID of the one you want, and attach to it using:
```
subscription-manager attach --pool=abc1234935
```

It may have automatically set up some unnecessary yum repositories, find out what's enabled with:
```
subscription-manager repos --list | grep -B 3  '^Enabled:   1'
```
And disable what you don't need with:
```
subscription-manager repos --disable rhel-server-dts-6-rpms --disable rhel-server-dts2-6-rpms
```
Or just select what you need with (the * needs a new subscription-manager, yum update it):
```
subscription-manager repos --list
subscription-manager repos --disable='*' --enable rhel-what-you-need --enable rhel-more-stuff
```


If you need to use a proxy to register, use:
```
subscription-manager config --server.proxy_hostname=1.2.3.4 --server.proxy_port=8080 --server.proxy_user=yourUserIfNeeded --server.proxy_password=yourPass
```
The settings above get saved to the rhsm.conf file. To remove the proxy after setting it; just set the proxy_hostname with the same command to an empty string.

If you've used the auto-attach and discovered that it attached the wrong subscription, type in:
```
subscription-manager  list --consumed
```
and remove that subscription using the serial (not the pool ID) it mentions:
```
subscription-manager remove --serial=123456789
```

### After the installation

- Clean up your root directory: `cd /root && mkdir apps backups bin temp scripts && mv anaconda* install* temp`

- `yum install telnet screen dnsmasq`

- Add this to the end of "/etc/screenrc" to enable scrolling in screen:
`termcapinfo xterm* ti@:te@`
You should use screen whenever you run a long running foreground process, like a yum update, because if you lose your SSH session (laptop battery dies or network disconnects), the process gets killed, and a half-update can easily corrupt your system state. The basics of screen is easy, just run 'screen', and then use it normally. To detach manually, press in Control+a, and then press d. To rejoin, type screen -r. It will take a bit more explaining, perhaps in a different article.

- Do a `yum update` in screen

- If your app doesn't support SELinux, disable it by editing /etc/selinux/config, but if this is a webserver, it's HIGHLY recommend you learn SELinux and keep it enforcing.

- Unless it is going to be used by someone who needs to change the IP address easily; disable NetworkManager and configure the network by hand via /etc/sysconfig/network-scripts/...

- Install the [nload](http://apt.sw.be/redhat/el6/en/x86_64/rpmforge/RPMS/nload-0.7.4-1.el6.rf.x86_64.rpm) RPM, and create a file `/root/bin/bandwidth` with the contents `nload -u K -U K eth0`, and chmod +x it.

- If this is a web server or a server that needs to be highly secured, edit the /tmp mount point to add these options: `nosuid,noexec,nodev,noatime`. It would also make sense to public-writable mount points, if any, like /var/www. 

- Add noatime to the other mount points including root (no need for /boot though). You can consider disabling fsck (0 0 at the end) for non root mount points; as otherwise you may not be able to SSH to a server if a non-root filesystem got corrupt, since it will prompt for admin intervention in the physical console.

- Make sure the server boots in text mode (/etc/inittab - id:3:initdefault:)

- Disable unnecessary services at startup. Get a list of services with `chkconfig --list | grep 3:on`, and disable the ones you don't need with chkconfig theservice off. For example, if you have no plans to use NFS, you can disable the rpc\*, portmap and nfs\* services. Use a loop to make things faster:
```bash
for i in NetworkManager autofs avahi-daemon bluetooth etc; do
	chkconfig $i off
done
```

- It's good to have dnsmasq as a super-quick local caching DNS proxy. Make sure the dnsmasq service is enabled and running. Set /etc/resolv.conf to have nameserver 127.0.0.1 in the top (or set it as DNS1= in your network config). I usually modify the config to set a larger cache size (9000), use "listen-address=127.0.0.1", and uncomment "bind-interfaces" (otherwise netstat will show dnsmasq listening on 0.0.0.0). 

- Set the FQDN & short hostname in /etc/hosts with the IP address

- `ntpdate asia.pool.ntp.org` and `chkconfig ntpd on`. You can also set your own NTP servers at this stage in the ntp conf.

- To speed up SSH logins, edit the /etc/ssh/sshd_config file and change `GSSAPIAuthentication yes` to `no`, and add `UseDNS no`

- Don't forget to configure iptables to allow your needed ports, or better yet use FireHOL (see my article list)

- If this will be a public server, you shouldn't have your SSH daemon listen on port 22, choose a random port instead and set that in /etc/ssh/sshd_config. Some apps like Zimbra can mess up unless SSH listens on 22, so you have have SSH listen on multiple ports just by multiple Port lines. If you have SELinux enabled, make it aware of your new port with `semanage port -a -t ssh_port_t -p tcp 1234`. At the risk of getting locked out, you may optionally stop it allowing port 22 if you are really sure: `semanage port -d -t ssh_port_t -p tcp 22`

- Install the server vendor tools (but NOT drivers, if possible); eg. hp-health and hpssacli for HP from:
[http://downloads.linux.hp.com/SDR/repo/mcp/EnterpriseEnterpriseServer/6/x86_64/current/](http://downloads.linux.hp.com/SDR/repo/mcp/EnterpriseEnterpriseServer/6/x86_64/current/)
For Dell, use the instructions:
[http://linux.dell.com/repo/hardware/latest/](http://linux.dell.com/repo/hardware/latest/)
Install OpenIPMI as well, start it up (or reboot), and then run:
`srvadmin-services.sh start`
and check `srvadmin-services.sh status` to make sure the services are running. You can check the temperature with `/opt/dell/srvadmin/bin/omreport chassis temps`. Add "srvadmin-services.sh start &" to /etc/rc.local if you can't find a cleaner way.

- Update the board & raid controller firmware

- Set up multipathing; unless you have custom needs or use PowerPath, it's much easier in RHEL6 vs 5, just type: `yum install device-mapper-multipath ; mpathconf --enable --with_multipathd y --find_multipaths y --user_friendly_names y`
 

- (not sure if this is still needed in newer releases of RHEL6) If the server will have multipathing with LVM; you can specifically allow only the root/local device & the multipath virtual device by editing /etc/lvm/lvm.conf, and entering something like (remember to change the device list, and double check if sda is actually your root volume group):
`filter = [  "a|^/dev/sda$|", "a|^/dev/sda2$|", "a|^/dev/mapper/.*|", "r|.*|" ] `
Backup the existing initramfs (very important, as a tiny syntax error can make the system unbootable), and then regenerate the initrd with:
`dracut -f /boot/initramfs-$(uname -r).img $(uname -r)`
There is a chance that sda may not be your root device, esp. if you are connected to a SAN. If that's the case, add this to your kernel boot arguments (replacing hpsa with whatever is handling the local drives) to make sure your root is always /dev/sda:  `rdloaddriver=hpsa`

- If it's a production machine, edit the /root/.bashrc to make the prompt red so that you minimize making the all-too-common mistake of entering a command on the wrong terminal:
`export PS1="[\u@\[\e[1;31m\]\h\[\e[0m\] \W]\\$ "`
Make non-prod servers green:
`export PS1="[\u@\[\e[1;32m\]\h\[\e[0m\] \W]\\$ "`
or blue if it's development:
`export PS1="[\u@\[\e[1;34m\]\h\[\e[0m\] \W]\\$ "`


- Add this to .bashrc to prevent accidental reboots by giving you a chance to change your mind:
```
alias reboot='echo "Rebooting `hostname` in 5 secs. Press Ctrl+C to cancel";sleep 5 && reboot'
alias poweroff='echo "Shutting down `hostname` in 5 secs. Press Ctrl+C to cancel";sleep 5 && poweroff'
```

- If MySQL is going to be used; add this to the my.cnf before inserting any data (without this; the ibdata1 file will be huge & contain data of all databases; this will separate them):
```
[mysqld]
innodb_file_per_table
```

- If you are using software RAID; be sure to install GRUB on the secondary drive as well. Something like:
```
grub
root (hd1,0)
setup (hd1)
quit
```

- Set up [command logging](/articles/command-logging/)

- rsyslog by default will limit the logs from a daemon if it logs too much, but that can easily lead to lost log entries (note that this is different from preventing duplicate log lines, it actually stops logging anything from that daemon for some time). You can want to disable that by creating a file called **/etc/rsyslog.d/disable_ratelimiting.conf** with the following contents:
```
$SystemLogRateLimitInterval 0
$SystemLogRateLimitBurst 0
```

- To set up bonding, create a file called **/etc/modprobe.d/bonding.conf**
```
   alias bond0 bonding
```

Then set up **/etc/sysconfig/network-scripts/ifcfg-bond0** as you would with a normal interface:
```
   DEVICE=bond0
   IPADDR=1.2.3.4
   NETMASK=255.255.255.0
   USERCTL=no
   BOOTPROTO=none
   ONBOOT=yes
   BONDING_OPTS="miimon=100 mode=active-backup"
   #BONDING_OPTS="arp_interval=500 arp_ip_target=10.113.0.1,10.113.0.2 mode=active-backup"
```

And modify the **/etc/sysconfig/network-scripts/ifcfg-eth0** and **eth1** interfaces to look like this:
```
   DEVICE=eth0
   MASTER=bond0
   SLAVE=yes
   ONBOOT=yes
   USERCTL=no
   BOOTPROTO=none
```
Restart the network, and check `cat /proc/net/bonding/bond`

- iptraf is really useful when trying to figure out what's taking up the bandwidth, but it wastes a lot of bandwidth trying to show the byte usage of the SSH session (which causes it to update, and use more SSH traffic).
Ignoring SSH is quite tricky unless you know how; the key is that by default applying an empty filter will make it show nothing; so you need to have an explicit rule to show all traffic in the end :
Go to Filters -> IP -> Make sure there aren't any filters already in Edit filter.
Define a new filter-> Ignore SSH.
Press A to add to list. Make the IP address & widcard mask 0.0.0.0 on both destination & source. Source port is 0 to 0, destination port is 22 (or 2251) to 0. Then make sure you put a 'Y' in All IP and TCP. Then put 'E' in Include/Exclude. Enter to accept.
Press A to add to list again. Make everything 0.0.0.0 or 'Y', and make sure it's the default 'I' for include.
You then need to apply the filter.
If you ever edit the filter, it won't apply automatically. You have to detch and apply the filter again.


*[OOM]: Out of Memory



