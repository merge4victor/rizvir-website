On CentOS 7


### Data machine setup

On the machine you want to back up:
yum install epel-release
yum install fuse-encfs

First do a test backup/restore so that you are confident of this working. Do a:
`mkdir -p /mnt/crashplan/etctest`

And then:
```
cp -av etc/ /tmp/etctest
encfs --reverse /tmp/etctest/ /mnt/crashplan/etctest/
```

Press enter to use the standard mode (paranoia mode isn't supported with --reverse), and then enter the encryption password. 

Have a look at /mnt/crashplan/testetc ; the filenames are random, and this is what would be visible to crashplan. Also look at the file **/tmp/etctest/.encfs6.xml**, this file is *essential* to be able to restore the backup; without it, your password is of NO use. 

Because of how important the .encfs6.xml file is, it would make sense for you to keep that in Crashplan as well. The file by itself is not enough to decrypt your data; you need the password as well. However, just to be extra cautious, you can use GPG to encrypt it (preferably with a *different* password):

```
mkdir -p /mnt/crashplan/xml/
gpg -c /tmp/etctest/.encfs6.xml
<enter a password>
mv /tmp/etctest/.encfs6.xml.gpg /mnt/crashplan/xml/etctest.xml.gpg
```

Now add those to your exports, mentioning the IP address of the Crashplan machine, and a unique fsid for each export:
```
/mnt/crashplan/etctest     192.168.122.5(ro,fsid=1,all_squash,anonuid=0,anongid=0)
/mnt/crashplan/xml     192.168.122.5(ro,fsid=2,all_squash,anonuid=0,anongid=0)
```

Modify your iptables firewall to allow Crashplan to mount the volume. 


### Crashplan setup

There's nothing special about installing crashplan. I created a KVM/virt-manager VM on the machine having the data, and chose CentOS 7 with the Desktop option. 

Add the exports to your /etc/fstab:

```
storage:/mnt/crashplan/xml     /mnt/crashplan/xml     nfs defaults,ro  0 0
storage:/mnt/crashplan/etctest     /mnt/crashplan/etctest     nfs defaults,ro  0 0
```

Do a `mkdir -p /mnt/crashplan/{conf,etctest}`, and mount them. Make sure it's accessible.

Simply download Crashplan, and run it. It will download it's preferred Java version. 

If your backup is going to be more than a terabyte, then Crashplan recommends you increase the java memory allocation from the default of 1GB to XGB, where X is the amount of terabytes you have (assuming you have enough RAM). You can do this by double clicking on the crashplan logo on the top right corner, and typing `java mx 2048, restart` . After some time, it should have restarted the crashplan service in the background, and you can try starting crashplan again.

In Crashplan, select the /mnt/crashplan directories. 

You can disable de-duplication and compression from Settings->Backup->Advanced Settings. You can also choose to disable crashplan encryption if you want though it's fine having it. You will also want to disable "Watch file system in real time".

Then start a backup. 


### Restore

To do/test a restore, use the crashplan GUI -> Restore to select the /mnt/crashplan folder, and click on Restore.

Then once you verify that you can see ~/Desktop/crashplan directory with the files, install encfs, decrypt the configuration file, and use it to decrypt the contents:
```
yum install epel-release
yum install encfs
cd ~/crashplan/xml
gpg test.xml.gpg
mkdir -p /mnt/decrypted
ENCFS6_CONFIG=~/Desktop/crashplan/xml/etctest.xml encfs ~/Destkop/crashplan/etctest /mnt/decrypted
<enter your password>
cd /mnt/decrypted
ls
```



#put details of automount/encrypted key at boot with systemctl




