(this doc needs to be a bit cleaned up, the installation steps were originally written just for my own reference)

[Rsnapshot](http://rsnapshot.org/) is a large perl script that orchestrates backups using tools like rsync. You might be thinking, rsync isn't that hard, why would I use rsnapshot? Well, because rsnapshot can keep snapshots of the previous backups as well instead of overwriting them like rsync does.  Imagine this scenario: the primary server loses a lot of information or gets corrupted late evening. No one notices, and the sync takes place at night. Next thing you know, you have two servers having the same corrupt information. With this method, you'd have the ability to almost instantly restore the backup as it were for any day of the past week or so. So if things go awry in the weekend and no one notices, you can restore the backup 3 days ago. 

Rsnapshot's backup strategy is difficult to describe quickly until you see it, but this is how the end result looks like when you see the resulting backup, where daily.0 is the latest backup, and the previous day's is daily.1, and so on:
```
[root@storage snapshots]$ ls
daily.0  daily.1  daily.2  daily.3  daily.4  daily.5 daily.6
[root@storage snapshots]$ cd daily.0/ # Yesterday's backup
[root@storage daily.0]$ ls
chat.test.com  web.test.com  server2.dev.local
[root@storage daily.0]$ cd chat.test.com/
[root@storage chat.test.com]$ ls
bin  boot  dev  etc  home  lib  lib64  lost+found  media  mnt  opt  proc  root  run  sbin  srv  sys  tmp  usr  var
[root@storage chat.test.com]$ cd ../../
[root@storage snapshots]$ cd daily.6/chat.test.com/  # Last week's backup
[root@storage chat.test.com]$ ls
bin  boot  dev  etc  home  lib  lib64  lost+found  media  mnt  opt  proc  root  run  sbin  srv  sys  tmp  usr  var
[root@storage chat.test.com]$ 
```

As you can see, as far as you're concerned, you just have lots of days (or even hours _and_ days) of full backups of, in this case, the root filesystem. But before you cry about the space usage, realize that the actual space it uses is only marginally higher than a single full backup, because it _hard-links identical files across backups_. 

So you end up with these advantages:

- It's much better than using rsync directly
- Browsing backups of different days is instantaneous; just like any other directory
- Nothing unusual needed for recovering files; they're just files
- You end up having very well tested core binaries like rsync, cp, ln, etc. handling your backups, with rsnapshot just orchestrating things (it can show you the commands it plans to run if you want)
- If you are good with Linux, you can use this filesystem copy to recover from bare metal if ever needed
- It's those few backup tools that can be make to work efficiently with hard-links or sparse files.
- Crucially, depending on your application, if you can prepare the backup server in advance to act as a standby, you can initiate a disaster recovery by just soft-linking the required directories (eg. /var/lib/mysql) and files to the rsnapshot backup directory, say (/mnt/backups/daily.0/myserver.com/var/lib/mysql), and just start your services to end your downtime. Brings a whole new meaning to the phrase "get up and running in no time". 
You cannot do this with almost any other backup tool, because you need the time to uncompress and extract your backups to a machine first, which can take a very long time for a full system recovery, and, with tape backups, always has a chance of failing.

Of course, it's not all roses, as one major disadvantage is that backups are not compressed (unless your filesystem is [ZFS/BTRFS]). In addition, it's poorly suited in situations where you have very large single files that change by a bit (like virtual machine images); because rsnapshot would copy and store the entire file over; it cannot keep the differences of a single file between backups. Also, the place where you keep your backups has to support permissions, possibly ACLs, etc, making it often not work well with some NASs, or FAT32/NTFS mount points (if you use a USB, format the USB with ext3/4/xfs)

Rsnapshot by itself is fairly easy to set up, and there are loads of rsnapshot tutorials on the internet. However, most of them end up resulting in a situation where you can log into the primary server from the backup as root without a password. That's not ideal. So we'll take the much longer route to prevent this. 


### Pre-installation

Create a new system user on the main server called say "backupuser". We'll be needing to transfer keys later, so you can optionally set a random long password and benefit from ssh-copy-id, or just do it manually without setting a temporary password.:

```bash
adduser backupuser
passwd backupuser
<long random password>

mkdir -p /home/backupuser ; chown backupuser:root /home/backupuser ; chmod 700 /home/backupuser
```

You can use the numerous scripts available online to restrict the commands that can be run when backupuser logs in via a key. For this example, we'll be using a script taken from [troy.jdmz.net](http://troy.jdmz.net/rsync/#validate-rsync) , call it **/home/backupuser/validate.sh** :

```bash
#!/bin/sh
FAIL_MESSAGE="Not allowed"
case "$SSH_ORIGINAL_COMMAND" in
  *\&*)
    echo "$FAIL_MESSAGE"
    ;;
  *\;*)
    echo "$FAIL_MESSAGE"
    ;;
  *\(*)
    echo "$FAIL_MESSAGE"
    ;;
  *\{*)  
    echo "$FAIL_MESSAGE"
    ;;
  *\<*)
    echo "$FAIL_MESSAGE"
    ;;
  *\`*)
    echo "$FAIL_MESSAGE"
    ;;
  *\|*)
    echo "$FAIL_MESSAGE"
    ;;
  rsync*)
    $SSH_ORIGINAL_COMMAND
    ;;
  /usr/local/bin/rsync_wrapper.sh*)
    $SSH_ORIGINAL_COMMAND
    ;;
  "sudo /home/backupuser/prepare-backup-start.sh")
    $SSH_ORIGINAL_COMMAND
    ;;
  "sudo /home/backupuser/prepare-backup-finish.sh")
    $SSH_ORIGINAL_COMMAND
    ;;
  true*)
    echo true
    ;;
  *)
    echo "$FAIL_MESSAGE"
    ;;
esac
```

Set up some permissions for that script:
```bash
chown backupuser:root /home/backupuser/validate.sh; chmod 550 /home/backupuser/validate.sh 
```

Then type:
```
visudo
```
And add this line:
```
backupuser ALL=NOPASSWD:/usr/bin/rsync
```

You will also need to comment out:
`#Defaults    requiretty`

If you plan to use LVM snapshots, add:
```
backupuser ALL=NOPASSWD:/home/backupuser/prepare-backup-start.sh
backupuser ALL=NOPASSWD:/home/backupuser/prepare-backup-finish.sh
```

Create a file called **/usr/local/bin/rsync_wrapper.sh** containing:
```bash
#!/bin/sh
/usr/bin/sudo /usr/bin/rsync "$@";
```

Then type:
```
chown backupuser:root /usr/local/bin/rsync_wrapper.sh
chmod 550 /usr/local/bin/rsync_wrapper.sh
```

Enable passwordless logins for backupuser. If you set a password for backupuser, you can do it the easy way by typing this on the rsnapshot server:
```
[in your backup backup] ssh-keygen -t rsa
[in your backup backup] ssh-copy-id backupuser@your-main-server.domainip.com
```

Now, on the primary server, edit /home/backupuser/.ssh/authorized_keys and prepend:
```
from="1.2.3.4",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,command="/home/backupuser/validate.sh" 
```
just before the just before the ssh-rsa AAAAB3Nza... text, modifying 1.2.3.4 with your rsnapshot/backup server's IP.

If the server supports LVM snapshots (all you need is a few gigabytes of free space in your VolumeGroup), go to your main server and create the scripts /home/backupuser/prepare-backup-start.sh & /home/backupuser/prepare-backup-finish.sh as required. An example:
**/home/backupuser/prepare-backup-start.sh**
```bash
#!/bin/bash
set -e
# Change the path of lvcreate to /usr/sbin/lvcreate for RHEL5
/sbin/lvcreate -L 2G --snapshot -n RootSnapshot /dev/VolGroup00/root
/sbin/lvcreate -L 3G --snapshot -n OptSnapshot /dev/VolGroup00/opt
mount -o ro /dev/VolGroup00/RootSnapshot /mnt/snapshot_root
mount -o ro /dev/VolGroup00/OptSnapshot /mnt/snapshot_opt
```


**/home/backupuser/prepare-backup-finish.sh**
```bash
#!/bin/bash
umount /mnt/snapshot_root
umount /mnt/snapshot_opt
# Change the path of lvremove to /usr/sbin/lvremove for RHEL5
/sbin/lvremove -f /dev/VolGroup00/RootSnapshot
/sbin/lvremove -f /dev/VolGroup00/OptSnapshot
```

Edit the above according to your LVM setup, and create the snapshot directories (eg. /mnt/snapshot_root), and run both those scripts to make sure they work, then:
```
chmod 550 /home/backupuser/prepare-backup-*
```


### Installation

It's much more complicated than the pre-installation:

1. Install [EPEL](https://fedoraproject.org/wiki/EPEL/FAQ#How_can_I_install_the_packages_from_the_EPEL_software_repository.3F)

2. yum install rsnapshot


### Configuration

Edit **/etc/rsnapshot.conf**, and remember that **you need TABS between the configuration name and value**, so you can't copy and paste the following. So to be clear, if I mentioned a line like:
```
ssh_args        -p 22 -c arcfour
```
it actually means:
```
ssh_args<TAB>-p<SPACE>22<SPACE>-c<SPACE>arcfour
```

Here are the recommended configuration changes; with the changes highlighted:
```hl_lines="11 12 17 22 30 44 45 47"
#                                             
# This file requires tabs between elements
#
# Directories require a trailing slash:
#   right: /home/
#   wrong: /home

config_version  1.2

# All snapshots will be stored under this root directory.
snapshot_root   /opt/snapshots/
no_create_root  1

cmd_cp          /bin/cp
cmd_rm          /bin/rm
cmd_rsync       /usr/bin/rsync
cmd_ssh /usr/bin/ssh
cmd_logger      /bin/logger
cmd_du          /usr/bin/du
#cmd_rsnapshot_diff      /usr/local/bin/rsnapshot-diff

interval        daily   7

# Verbose level, 1 through 5.
# 1     Quiet           Print fatal errors only
# 2     Default         Print errors and warnings only
# 3     Verbose         Show equivalent shell commands being executed
# 4     Extra Verbose   Show extra verbose information
# 5     Debug mode      Everything
verbose         4

# Same as "verbose" above, but controls the amount of data sent to the
# logfile, if one is being used. The default is 3.
#
loglevel        3

logfile /var/log/rsnapshot

lockfile        /var/run/rsnapshot.pid

#exclude /mnt/snapshot_root/root/apps/

#rsync_short_args        -a
rsync_long_args --sparse --hard-links --delete --numeric-ids --relative --delete-excluded --rsync-path=rsync_wrapper.sh
ssh_args        -p 22 -c arcfour

one_fs         1
```

I'll quickly go through what the changes mean:

- `snapshot_root`: Where the backups are kept. If this is in a mount point, I suggest you use a subdirectory in the mount point, so if /opt/ is a separate mount point, keep the backups in say /opt/snapshots instead of /opt. BTW: I had bad luck with samba and even some NAS's NFS implementations. Stick to ext3/4/xfs, esp. if you expect to do bare-metal recovery.
- `no_create_root 1`: This means that it will not create the `snapshot_root` directory, you will have to do that yourself, and if it can't find it, it will refuse to backup. Why is this a good idea? Because imagine you keep your backups on a USB, but the USB isn't mounted or attached. With the default, it will happily start creating the missing mount point and doing the backup on your root filesystem. So in most cases, it's best for it to fail than write the backups on the wrong disk.
- `cmd_ssh`: Needed for remote backups
- `interval daily 7`: This is difficult to explain; rsnapshot does not do any scheduling, so the 'daily' keyword here is just a name. The actual backup schedule is handled by you with cron, so if you set cron to run "rsnapshot daily" hourly, your daily actually means hourly.
To make things simple, you could just stick to this recommendation, 'daily 7' or 'daily X', and think of X as representing the number of old backups you want to keep. You can then set up cron to back up hourly, or daily, or twice a day, etc. 
_(Once you're comfortable with rsnapshot, you can read up on it a bit more, and then realize you can have say 3 hourly backups, 7 daily backups and 2 monthly backups, which means, if you don't mess up setting the cronjob, that it'd keep the latest 3 hours of backups, as well as the latest 7 days of daily backups, and two directories having the backups from a month ago and 2 months ago respectively; with all of them hard-links to share identical files between them_
- `verbose`: I like increasing the verbosity of a manual run, so that you can see what's going on. 
- `logfile`: where the logs are kept; this has a separate verbosity level which is fine at it's default of 3
- `rsync_long_args`
	- `--sparse`: Some apps like Zimbra 8/OpenLDAP's MDB backend, or some KVM virtual machine images, are kept as sparse files, which means that they seem to take up a lot of space (31 GB here):
[root@main images]# ls -lh centos7.qcow2 
-rw-r--r--. 1 qemu qemu 31G Feb 27 12:29 centos7.qcow2
but actually take up relatively little space:
[root@main images]# du -hs centos7.qcow2 
2.3G	centos7.qcow2
If I backed this directory up with the default rsnapshot options, my backup server would use up 31GB on it's disk. But with `--sparse`, it would use the same space on disk as the original, 2.3GB. This makes it easier to recover as well without taking up more space than before.
	- `--hard-links`: Some apps like Cyrus and Zimbra 8 use hard-links a lot, and by default, rsync does not retain the hard-link information, so you end up with a much much larger backup than the original (along with problems during restoration). So adding `--hard-links` would fix this (at the expense of extra memory usage).
	- `--rsync-path=rsync_wrapper.sh`: this calls the script we made to run rsync with sudo.
- `ssh_args -p 2251 -c arcfour`: Change 22 to your SSH port, and the `-c arcfour` uses a less-secure but less-CPU intensive encryption algorithm useful in LANs. Remove `-c arcfour` when doing WAN backups.
- `one_fs 1` - Stick to one filesystem when backing up a mount point. I prefer this, as otherwise backing up / would back up unnecessary things like /dev and /proc, or mount points you don't need. However, the downside is that you have to remember to manually include every mountpoint in the what-to-backup settings below.


Then at the end of the config file, there should be a list of things that should be backed up. Remove the defaults, and add your own lines like:
```
###############################
### BACKUP POINTS / SCRIPTS ###
###############################

# No LVM snapshots:
backup  backupuser@1.2.3.4:/ some.server.com/
backup  backupuser@1.2.3.4:/boot some.server.com/

backup  backupuser@another.server.com:/ another.server.com/
backup  backupuser@another.server.com:/opt another.server.com/
backup  backupuser@another.server.com:/boot another.server.com/

# or with LVM snapshots with your prepare-* scripts:
backup  backupuser@1.2.3.4:/mnt/snapshot_root some.server.com/
backup  backupuser@1.2.3.4:/mnt/snapshot_opt some.server.com/
backup  backupuser@1.2.3.4:/boot some.server.com/

# You can customize options per server. So say one of your servers has the SSH port 6824 instead of 22:
backup  backupuser@1.2.3.4:/something/      web.domain.com/     ssh_args=-p 6824

# Or you want to enable rsync stream compression on WAN clients to reduce bandwidth:
backup  backupuser@web.server.com:/  web.server.com/        +rsync_long_args=--compress

```

### Backup script

You can just run `rsnapshot daily` to see if the backup works (it will most probably complain about errors in your config, fix them as it suggests). If you use LVM snapshots, you can temporarily manually run the /home/backupuser/prepare-backup-start.sh script on your main server before running "rsnapshot daily", and remember to run prepare-backup-finish.sh after you are done testing.

If everything works fine, you can use a simple backup script like:
```bash
#!/bin/bash

MAIN_SERVER="1.2.3.4"
USER="backupuser"
RSNAPSHOT="/usr/bin/rsnapshot"

# uncomment if you have LVM
#ssh $USER@$MAIN_SERVER "sudo /home/$USER/prepare-backup-start.sh"
$RSNAPSHOT daily
#ssh $USER@$MAIN_SERVER "sudo /home/$USER/prepare-backup-finish.sh"
```


or you could use a more paranoid one; modify it to make it integrate with your monitoring system (edit the top variables and function):

```bash
#!/bin/bash
MAIN_SERVER="1.2.3.4"

MAIN_SERVER_PORT="22"
USER="backupuser"
RSNAPSHOT="/usr/bin/rsnapshot"
LOG="/var/log/rsnapshot"
TIMEOUT=4

# Edit this:
fail_action)()
{
	# Fill this in with how to notify you if the backup fails. 
	# Input ($1) : string with a message about what failed
}


#---------------
#---------------

# input: none
# output: 0 is success, 1 if not pingable
try_ping ()
{
        pingcount=$(ping -c 1 -W $TIMEOUT $1 | grep 'received' | awk -F',' '{ print $2 }' | awk '{ print $1 }');
        if [ $pingcount -eq 1 ] ; then
                return 0;
        fi
        return 1;
}

# input: message
# output: nothing (writes message to $LOG with rsnapshot like date)
write_log()
{
        echo `date +"[%d/%b/%Y:%k:%M:%S]"` $1 | tee -a $LOG
}

# input: return_code message_string
# output: if ok, write to log, otherwise write to log and exit with status 1
check_status()
{
        RETURN=$1
        MESSAGE=$2
        if [ $RETURN == 0 ]; then
                write_log "$MESSAGE OK"
        else
                write_log "$MESSAGE FAILED!"
                write_log "Cleaning up & aborting backup"

				fail_action "$MESSAGE failed."
                ssh -p $MAIN_SERVER_PORT $USER@$MAIN_SERVER "sudo /home/$USER/prepare-backup-finish.sh"

                exit 1
        fi

}

try_ping $MAIN_SERVER
check_status $? "ping $MAIN_SERVER"

ssh -p $MAIN_SERVER_PORT $USER@$MAIN_SERVER "sudo /home/$USER/prepare-backup-start.sh"
check_status $? "prepare-backup-start.sh"

$RSNAPSHOT daily
check_status $? "rsnapshot daily"

sleep 2
ssh -p $MAIN_SERVER_PORT $USER@$MAIN_SERVER "sudo /home/$USER/prepare-backup-finish.sh"
check_status $? "prepare-backup-finish.sh"

exit 0
```

If the server is not pingable; use this instead for the try_ping () function (make sure nc is installed): 

```bash
# input: none
# output: 0 is success, 1 if not pingable
try_ping ()
{
        nc -w $TIMEOUT -z $MAIN_SERVER $MAIN_SERVER_PORT
        RETURN=$?
        if [ $RETURN -eq 0 ] ; then
                return 0;
        fi
        return 1;
}
```

If you do not have LVM snapshots, remove the prepare-backup-*.sh lines above, and then replace the lines after $RSNAPSHOT with this:

```bash
$RSNAPSHOT daily
RETURN=$?
# note that rsnapshot returns 2 as a warning if a file changed
# which will be the case if there are no snapshots
if [[ $RETURN == 0 || $RETURN == 2 ]]; then
        write_log "Backup OK"
        exit 0
else
        write_log "rsnapshot returned $RETURN, backup FAILED"
		check_status 1 "rsnapshot return code $RETURN"
fi
```

Test it. If it's fine, make a cron job:

```
45 23 * * * /root/scripts/rsnapshot-backup.sh
```

Don't just rely on the script telling you if there is a bad return code; find a way to get notified if the script doesn't run at all for some reason. If you have a Nagios plugin compatible monitoring system, you can use something like [check_newest_file_age](https://exchange.nagios.org/directory/Plugins/System-Metrics/File-System/check_newest_file_age/details) on a directory in daily.0 for each of your hosts that you expect should change every day (eg. var/log); so you get notified if the backup seems stale. 








