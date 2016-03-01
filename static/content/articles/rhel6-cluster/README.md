Nothing here applies to RHEL7 clusters.

### Installation and setup

Be sure to plan for and test all sorts of failures (complete power failure such that iLO fencing does not work), long term private/public network failure, temporary private/public network failure, NIC failure, SAN connectivity failure, and software resource failure etc).

\- Install RHEL 6 64-bit according to the [standard guidelines](/articles/el6-standard-installation/)

\- Yum could be faster to update if you set keepcache=1 on the first server before an update, and then copy the cache /var/cache/yum/x86_64/6Server/thechannel-name/packages to the other machines

\- You will want to disable "acpid" from starting up as well if you use Dell DRAC or similar fencing that sends a soft power off when ACPI is enabled. If it still soft power offs, then try adding "acpi=off" to grub although I didn't require it with a dell server.

\- It is recommended that you set up bonding and multipathing straight away. I recommend mode=active-backup as that causes the least headaches with the widest switch compatibility.

\- - If you will enable iptables; be sure to allow UDP ports 5404, 5405 (corosync/cman), and TCP ports 11111 (ricci), 21064 (dlm), 16851 (modclusted), 8084 (luci). You can add these in between iptables sysconfig:
```bash
-A INPUT -p udp -m state --state NEW -m multiport --dports 5404,5405 -j ACCEPT
-A INPUT -p tcp -m state --state NEW -m multiport --dports 11111 -j ACCEPT
-A INPUT -p tcp -m state --state NEW -m multiport --dports 16851 -j ACCEPT
-A INPUT -p tcp -m state --state NEW -m multiport --dports 8084 -j ACCEPT
-A INPUT -p tcp -m state --state NEW -m multiport --dports 21064 -j ACCEPT
```

If you use firehol allow outgoing connections to those ports as well:
```bash
server_cluster_ports="udp/5404 udp/5405 udp/5406 tcp/11111 tcp/16851 tcp/8084 tcp/21064"
client_cluster_ports="any"
...
   server cluster accept
   server multicast accept
   client cluster accept
   client multicast accept
# multicast above only takes care of UDP & IGMP, not ICMP, so manually specify it here
iptables -I INPUT -d 224.0.0.0/4 -p icmp -j ACCEPT
iptables -I OUTPUT -d 224.0.0.0/4 -p icmp -j ACCEPT
```

\- If you have more than 2 nodes in a cluster, make sure multicast communication works (it's usually disabled by default in managed switches). You can use [omping](https://access.redhat.com/articles/22304) to test it. If you just have 2 nodes, I find it easier not to use multicast, as it saves you from having to deal with potentially incompetent network admins.

\- Use subscription-manager to subscribe to the ha or rs (resilient storage) repos; you need to make sure you attached to the correct subscription to have access to those. 

\- `yum groupinstall "High Availability" 
<<make sure EPEL is not enabled>
\- `yum install luci`
\- If you are using GFS2: `yum install lvm2-cluster gfs2-utils`


\- `passwd ricci` # Set some temporary long random password, 

```
/etc/init.d/ricci start &&  chkconfig --levels=35 ricci on

/etc/init.d/luci start && chkconfig --levels=35 luci on
```

\- You can change the web interface daemon settings (eg. port or which IP to bind) by editing /etc/sysconfig/luci & restarting luci

\- Make sure the permissions of /tmp is set up correctly (chmod 1777), otherwise you'd get an error after adding the nodes to luci (something about error receiving headers from host:11111)

\- It is recommended to stop the cluster from starting at boot; both for testing as well as in production for two node clusters (unless it is not monitored by admins); because if there is a communication issue, both servers would try to restart each other forever.
```
chkconfig rgmanager off
chkconfig cman off
```

\- Go to the URL https://node1:8084 , and log in as root

\- Click on Manage clusters -> Create. Enter a cluster name (15 char max, and can never be changed in the future), the hostnames mentioned in /etc/hosts with the ricci password (if you have a private IP for cluster, enter the private hostname under "Ricci hostname"). Keep the "Use locally installed packages", check "Reboot Nodes before joining cluster", keep "Enable shared storage support" unchecked (unless you need GFS2 or CLVM; if you do make sure you either have internet access & subscribed to rhel-x86_64-server-rs-6, or have lvm2-cluster & gfs2-utils installed), and click Create Cluster.

\- Once the cluster is OK, click on the cluster on the left bar, then on Configure on the top. In the Fence Daemon tab, configure Post Join delay to be 60 seconds (see man fenced), and click Apply.

\- If you don't have more than 2 nodes, on the Network tab, and select UDP Unicast.

\- Disable rgmanager, gfs, clvmd & cman from starting again (as it would be enabled by ricci)

\- It's best to test the fencing on the command line first. As root, type "fence_<tab>", and select the fencing script that makes sense and check the help (be sure to set the action to "status" first; it is reboot by default).

\- For HP iLO fencing, if it's a recent server (G6 onwards); use IPMI fencing with LANPLUS. First test it on the command line; eg. for a BL460c G7, this worked:
fence_ipmilan -A md5 -a 1.2.3.4 -P -p yourpassword -l yourusername -o status -L OPERATOR 

If you are using firehol; you will also need to open the outgoing IPMI port:
`client ipmi accept`

Find the privilege level of the user through the admin (it will appear as you select/deselect the permissions on the iLO user administration page). If the priv level is not "administrator" then after creating the IPMI fencing in the web interface, edit the /etc/cluster/cluster.conf to add the privilege level to the fencing tag, eg:
```xml
<fencedevice agent="fence_ipmilan" ipaddr="1.2.3.4" lanplus="on" login="someuser" name="HP-iLO-Fencing-node1" passwd="..." privlvl="OPERATOR"/>
```

\- Click on Fence Devices on the top, and add a fencing device. If you use SCSI reservation fencing, the device needs to be the actual /dev/sdX device, not the VG name.

\- Click on Nodes on the top, click on a node, and then click Add Fence Method, and put in any name. Then after clicking Submit, click on "Add fence instance".

\- Click on Nodes on the top, click on a node, and then click Add Fence Method, and put in any name. Then after clicking Submit, click on "Add fence instance".

\- SCSI reservation fencing is buggy on the GUI when using LVM (thus not mentioning the device name); you can configure it manually on the command line:
```
ccs -h localhost --addfencedev SCSI-fence agent=fence_scsi
ccs -h localhost --addmethod SCSI-method rh-ha-samba1.rizvir.com
ccs -h localhost --addmethod SCSI-method rh-ha-samba2.rizvir.com
ccs -h localhost --addfenceinst SCSI-fence rh-ha-samba1.rizvir.com SCSI-method devices=/dev/sda
ccs -h localhost --addfenceinst SCSI-fence rh-ha-samba2.rizvir.com SCSI-method devices=/dev/sda
ccs -h localhost --addunfence SCSI-fence rh-ha-samba1.rizvir.com devices=/dev/sda action=on
ccs -h localhost --addunfence SCSI-fence rh-ha-samba2.rizvir.com devices=/dev/sda action=on
ccs -h localhost --sync --activate
ccs -h localhost --checkconf
```

For dm multipath devices, there is no need to enter each sdX device, just enter the /dev/mapper/mpathX device. If there are multiple devices, the syntax is a comma and a space between them, eg:
```xml
<device devices="/dev/mapper/mpathb, /dev/mapper/mpathc" name="SCSI-fence"/>
```

You can add the logfile variable to the SCSI fencing device like so:
```xml
<fencedevice agent="fence_scsi" logfile="/tmp/fence_scsi.log" name="SCSI-fence"/>
```

Make sure you don't fence the quorum disk. If you have a quorum disk, you should make sure that all cluster nodes see the same multipath device names. To do that, stop multipath on ALL nodes:
```bash
vgchange -a n yourVGname
/etc/init.d/multipathd stop
multipath -F
```
Then copy the /etc/multipath/bindings file from the first node to the other nodes. Then start multipath on all the nodes:
```
/etc/init.d/multipathd start
```

\- If you have multipathing and use Brocade fencing, add another fence instance with the secondary port.

\- You ideally should have more than one fencing method (eg. if you rely only on iLO, the cluster will not fail over if you yank all the power cables from the first server. So adding SCSI reservation would be useful), unless it's a virtual machine and you have no choice.

\-  If this is a two node cluster, and you are NOT using a quorum disk, make one of the node's fencing devices have a delay, so in a fence race, one of them always wins:
```xml
<fencedevices>
	<fencedevice name="node1-fence" agent="fence_ilo" ipaddr="node1-ilo" login="user" passwd="passwd" delay="30" action="off"/>
	<fencedevice name="node2-fence"  agent="fence_ilo" ipaddr="node2-ilo" login="user"  passwd="passwd" />
</fencedevices>
```

\- If this is a two node cluster with nodes close to each other, consider using a cross-cable and the Redundant Ring Protocol for an additional heartbeat link.

\- Failover domains are optional, but recommended as you can have more control on the failover. Click on "Failover domains" on the top in the cluster configuration, and click Add. Note that the lower the number, the higher it's priority (so 1 is preferrable to 100)

\- Set the noauto flag on any filesystems that are to be managed by the cluster; and unmount them. It's useful having them in /etc/fstab as noauto just for documetnation (or starting up without a cluster in an emergency)

\- Then add the resources by clicking on "Service groups". Note that for unknown reasons, Samba cannot be a child on another resource. Also, for IP address, it won't appear in ifconfig; you need to use "ip addr list". Make sure that any file dependencies for the resource (eg. configuration files) are identical across nodes.

\- To change the interval that a check is done for the service, add a child tag to that resource. Eg:
```xml
<fs name="test" device="/dev/sda1">
  <action name="status" depth="*" interval="10" />
  <service ...>
   ...
</fs>
```
The depth is used by some resources such as Filesystem, read their script for more info (eg. for Filesystem, 0 is check if it's mount, 10 is read test and 20 is write test. * is all thoses tests. Avoid read tests as often, because of the cache, it can read and mount the filesystem just fine; but not be able to write to it. So do use write tests.)

\- There are no global timeouts enforced for starting, stopping or moving a resource that does not support timeouts by itself. I feel like that is a bad thing as if a resource start is stuck, it would never fail over. You can enforce a timeout for a resource by having `__enforce_timeouts="1"` in the resource tag, eg:
```xml
<netfs ref="nfstest_data" __enforce_timeouts="1"/>
```

\- Go to https://node2:8084, click on Clusters -> Add, then add the first node with the ricci password. Now you can use either machines to configure the cluster, in case one of them goes down.

\- To configure HA-LVM with tagging, which is essential if your shared disk has LVM (but NOT needed if you are using CLVM with GFS2), create the VGs & LVs as usual, then backup & edit the /etc/lvm/lvm.conf file :
```
volume_list = [ "VolGroup00", "@rh-ha-samba1.rizvir.com" ]
```
(VolGroup00 being the VG of the root (/) LV). Then regenerate the initrd after backing it up:
```
dracut -f /boot/initramfs-$(uname -r).img $(uname -r)
```

You will now need to add tags if you want to mount or make changes to the VGs manually. It's VERY IMPORTANT to remember to remove tags after you are done, otherwise the cluster will fail.

```
pvcreate /dev/sdx
vgcreate vg_san01 /dev/sdx
vgchange --addtag host.name.com vg_san01
vgs -o tags vg_san01
vgchange -ay vg_san01
lvcreate ...
mount ...

umount ...
vgchange -an vg_san01
vgchange --deltag host.name.com vg_san01
```

Be sure to not mention the LV name in the cluster.conf; this way it will use tags for the VG, making it easier to take snapshots. Note that while the snapshot is mounted, the resource will not relocate successfully as it will not be able to deactivate the VG with the snapshot LV mounted.

\- It's recommended that you add another user in Conga, instead of root, if a client has access to the web interface. Log in to luci (https://IP:8084) as root, click on Admin, create a user who is not an administrator, and set only "Can view this Cluster",  "Can Enable, Disable, Relocate & Migrate Service groups", and   "Can stop, start & reboot cluster nodes". That should be enough for most folks.

\- Test the cluster by removing the network cables, removing the power, freezing the system (`echo c > /proc/sysrq-trigger`), etc. 

I also suggest you do an almost blank (just changing the config version) change for /etc/cluster/cluster.conf on the second or other nodes, as it'd ask for the ricci password once. It's better doing it now in a cool head rather than doing it when there is a disaster with the first node and you're in a hurry.

After the cluster install; it is recommended that you write a document specifying exactly how to start the resources without the cluster; so that in the event of a cluster issue during working hours, instead of inflicting downtime on the users as you scratch your head, you can get the service up and running; and worry about it in the night.


### QDisk

QDisk according to Red Hat should only be used for exceptional circumstances. I feel as if it can solve a lot of failure scenarios (eg. bring down a code if a scriptable test eg. a ping fails, SAN access fails, or to properly tie break), but also complicates things sometimes a lot. It's not really needed in most situations, and the lack of SCSI reservation fencing support is a big disadvantage.

\- The CMAN membership timeout value (the time a node needs to be unresponsive before CMAN considers that node to be dead, and not a member) should be at least two times that of the qdiskd membership timeout value. The default value for CMAN membership timeout is 10 seconds, so the qdiskd membership timeout should be 4 seconds or so.

\- Using fibre or SCSI reservation fencing may not be supported with qdisk.

\- You need a 10 (or greater, say 50 MB) LUN for the qdisk. If it's virtualized, make sure it's preallocated.

\- It may take several minutes for the qdisk to register to the cluster, this is normal.

\- Make a qdisk with:

`mkqdisk -c /dev/vdc -l theqdisk`

Make sure you can see it with "`mkqdisk -L`" on the other node.

Then use the GUI to use the qdisk (by label).

Be sure to test the qdisk to see how it responds to a path failure in a multipathed setup. If it fails; increase the timeouts to better tolerate a path failure.


### CLVM

Note that if this is an active/passive setup, stick to HA-LVM, even if you purchased the Resilient storage add-on. This is because, quote from Red Hat: "You cannot create a snapshot volume in a clustered volume group". pvmove may require some extra work too.

Make sure that you have NOT configured LVM tagging described above.

```
chkconfig clvmd on
/etc/init.d/clvmd start
```

Make sure the locking_type in /etc/lvm/lvm.conf is set to 3. This may have already been done for you by ricci/luci.

Then create the LV as usual on ONE of the nodes, not both:

```
pvcreate /dev/vdb1
vgcreate VolClustered /dev/vdb1
(it should say "Clustered volume group ... successfully created")
lvcreate --extents 100%FREE --name LogGFSTest VolClustered
```
Now when you run `lvm lvs` on the other node, you should be able to see your LV.

Keep in mind that any new disks, even local disks, would be set with clustering in mind. So if you need to create a volume group locally only (that's not shared with any other node), use:
`vgcreate --clustered n ...`

Don't try creating snapshots; if you do expect hung filesystems.


### GFS2

First set up CLVM, you should not use a raw device directly. (this is [required](https://access.redhat.com/site/solutions/46637) by Red Hat, which is a polar opposite to OCFS).

Note that if you're using GFS2, all nodes in the cluster must have access to the SAN (though not necessarily need to mount it), so you can't combine subclusters to have a large cluster unless they all have access to the same LUN. There's a maximum of 16 nodes that can mount a GFS2 filesystem at a time.

You also need to make sure you have enough memory, as GFS takes up more memory than local filesystems during an fsck. You can calculate the amount using the formula:
(Filesystem size in bytes / 4096 ) * (5/8)
So a 16TB filesystem would take around 2.6GB or 3GB of memory, plus the memory needs of the OS, during an fsck.

First set up the cluster as described above (with fencing and everything). NTP is particularly important in GFS2 clusters. You then need these pieces of information:

CLUSTERNAME:- The cluster name: this has to be the output in clustat or grep config_version /etc/cluster/cluster.conf
FSLABEL:- A name/label you want for the filesystem, without spaces & less than 16 characters. It has to be unique to this filesystem (not even a local filesystem should have the same name)
NUMNODES:- The number of nodes you have in the cluster. This can be increased later on.
DEVICE:- the shared block device

Then format the shared block device on ONE of the nodes:
```
mkfs.gfs2 -p lock_dlm -t CLUSTERNAME:FSLABEL -j NUMNODES DEVICE`
```

for example:

`mkfs.gfs2 -p lock_dlm -t GFSTest:sharedtest -j 2 /dev/VolClustered/LogGFSTest`

You can then mount it on both nodes:

mkdir /mnt/shared
mount -t gfs2 -o noatime /dev/VolClustered/LogGFSTest /mnt/shared/

Play with it to make sure it's working. And then UNMOUNT it. This is very important, because the system will kill cman before it tries unmounting your GFS2 volume, but GFS2 cannot survive without cman; resulting in a system hang.

`umount /mnt/shared`

And instead have an entry in /etc/fstab:
```
/dev/VolClustered/LogGFSTest    /mnt/shared     gfs2    defaults,noatime,nodiratime        0 0
```

Do NOT make it check the filesystem at bootup (hence the 0 0 at the end). noatime nodiratime would improve GFS2's performance considerable, because clustered filesystems in general are MUCH slower in writes than reads, so it makes no sense requireing a write for every read.

You can then do the usual cluster tests (power off, freeze, etc). The filesystem is expected to freeze (even typing cd /mnt/c<TAB> would freeze) until the other node is fenced. If fencing fails you are out of luck; so make sure fencing is tested & use a secondary fencing method if the servers are physical.

You can possibly get some write performance improvements by removing the artifically imposed 100 locks/second limit done to limit network traffic. This is not a weird tweak, it's recommended by Red Hat:
>If plock_ratelimit= is set to 0, the rate at which fcntl POSIX locks may be granted is unlimited (this is the recommended setting). Otherwise, the number sets the maximum number of fcntl POSIX locks granted per second. The default value for plock_ratelimit= is 100 locks/sec so most users of POSIX locks will want to change this setting." 
[https://access.redhat.com/site/articles/48659](https://access.redhat.com/site/articles/48659)

In RHEL6 in particular, this can be configured by changing the cluster.conf:

<cluster config_version="42"
...
<dlm plock_ownership="1" plock_rate_limit="0"/>
</cluster>

#### Handling fucked up GFS2 filesystems

See the note on memory usage at the start of this section. First (very critical) unmount the GFS volumes from ALL nodes. Then run fsck on that node:

```
fsck.gfs2 -n /dev/LogClustered/LogGFSTtest  # see whether the filesystem is OK without writing to it
fsck.gfs2 -y /dev/LogClustered/LogGFSTtest  # Auto fix the filesystem
```
If your cluster is messed up, you will be unable to mount the filesystem using the usual method. So, making sure that the cluster is indeed broken (cman is not running) & the filesystem is not mounted anywhere, type from one machine:

```
echo this can seriously corrupt everything if more than one node has access to the FS
vgchange -ay VolClustered --config 'global { locking_type = 0 }'
mount -t gfs2 -o lockproto=lock_nolock /dev/VolClustered/LogGFSTest /mnt/shared/
```

After you are done, unmount the volume and make it inaccessible, and then reboot to be sure:

```
umount /mnt/shared/
vgchange -an VolClustered --config 'global { locking_type = 0 }'
reboot
```

#### Adding more nodes later

You need to have as many journals as there are nodes. Suppose you have a new node later. You first verify the number of journals you have (make sure you don't have a trailing slash in the mount point):

```
gfs2_tool journals /mnt/shared
```

You then add 1 more journal (there has to be around 1% free space in the FS for this to work):

```
gfs2_jadd -j1 /mnt/shared
#  (make sure to exclude the trailing slash/)
```

#### Special notes for 3 or more node GFS2 clusters

In a three or more node setup, unless you have a qdisk, the documentation says that more than half the nodes needs to be up for the resources to function. This isn't strictly true if the nodes were cleanly shutdown for GFS2, here's how it actually works: take an example of a three node setup. Assume the first node fails. It doesn't matter whether it was cleanly shut down or forcefully fenced. Now when it comes to the second node, everything depends on how it was offline; if it was cleanly shutdown, the GFS2 partition would still function in read-write mode just fine, even though you'd get an inquorate warning, and rgmanager would stop (see below for more info on preventing that). However, if the second node failed and was fenced, then the remaining node's GFS2 partition would block, until either 1) one more node joins it's cluster 2) you run drastic measures below.

**Drastic measure: forcing a single node to work on it's own**
If the cluster is inquorate, and the other two were shut down improperly, and you want to get the services up and running on the remaining node, you need to:
\- Make sure that the other two are really down
\- Run: `cman_tool expected -e 1`
This will cause it to fence the other nodes (it won't proceed until it succeeds), and then will start rgmanager and unblock GFS2 if it was stuck. You can see the expected votes with `cman_tool status`.
Once one of the other nodes joins the cluster, the expected_votes should automatically increase to the number of total nodes (dead + alive), and things should be back to normal.


**Cleanly shut down two nodes such that one of them still works properly in a three node cluster**

Normally, shutting down two nodes usual way should do what you want if GFS2 is all that matters to you, but if need the rgmanager services (eg. virtual IPs), or if you just want to be extra clean, you can stop the first node as usual, and for the second node:
```
/etc/init.d/rgmanager stop
/etc/init.d/gfs2 stop
/etc/init.d/clvmd stop
fence_tool leave
cman_tool leave remove
/etc/init.d/cman stop
```
You will find that the remaining node would still be Quorate (yay!), and thus rgmanager would still work fine.

#### Shutting down a three node cluster

You may quicky find out that you if do a cluster_stop on the three nodes, the cman stop part would get stuck indefinitely, and you won't be even able to reboot without that getting stuck as well. This issue isn't documented, which is strange as it must be extremely common. So here's how you can shut down a three node cluster completely:
For the first and second nodes: stop it as usual. For the last node:
```
/etc/init.d/rgmanager stop
/etc/init.d/gfs2 stop
# Now the key here is that clvmd is stuck. So run:
killall clvmd
fence_tool leave
cman_tool services # Should be empty
/etc/init.d/cman stop
```

Taa daa!


### NFS

First, don't set NFS on GFS2, or you'd be having a bad time. Stick to ext4 (or xfs I guess).

If you're setting up a highly available NFS share, just remember that it won't be very highly available, as there'd be a noticeable delay (~60-90 seconds) in a failover. See [https://access.redhat.com/solutions/42868](https://access.redhat.com/solutions/42868)

Read the Cluster Administration docs, and then edit /etc/sysconfig/nfs and make the `NFSD_V4_GRACE` variable 10 (not lower), and edit /etc/init.d/nfs and add these before the `echo "$NFSD_V4_GRACE" > /proc/fs/nfsd/nfsv4leasetime"` :
```
echo "$NFSD_V4_GRACE" > /proc/sys/fs/nfs/nlm_grace_period
echo "$NFSD_V4_GRACE" > /proc/fs/nfsd/nfsv4gracetime
```

Then `chkconfig nfs off` and `chkconfig nfslock off`. Do not put any `nfslock="1"` thing in the cluster.conf <service> definition. Having something like this in the <service> section (add LVM if you're using HA-LVM instead of CLVM):
```xml
<service domain="DefaultFailoverDomain" max_restarts="1" name="nfstest" recovery="restart" restart_expire_time="600">
		<fs device="/dev/VolGroupSAN/nfstest" force_unmount="1" fsid="1" mountpoint="/mnt/nfs/" name="nfstest" options="noatime" self_fence="1" use_findmnt="off">
				<nfsserver name="nfsserver">
						<nfsclient name="allowall" options="rw,no_root_squash" target="*"/>
						<ip address="1.2.3.4" sleeptime="1"/>
				</nfsserver>
		</fs>
</service>
```

Then mount your clients with NFS4, like this in /etc/fstab:
```
1.1.2.2:/mnt/nfs /asd/asd/  nfs4      intr,bg,timeo=100,retrans=3 0 0
```


### Commands

- Start cluster manually (order matters): 
```
/etc/init.d/cman start
/etc/init.d/clvmd start # if used
/etc/init.d/gfs2 start # if used
/etc/init.d/rgmanager start
```

- Stop cluster services (order matters):
```
/etc/init.d/rgmanager stop
/etc/init.d/gfs2 stop  # if used
umount -at gfs2  # if used
/etc/init.d/clvmd stop  #if used
/etc/init.d/cman stop
```

- Cluster stauts: `clustat`

- Relocate: `clusvadm -r <resource-name> -m <node-hostname>`

- Freeze: `clusvcadm -Z <resource-name>`

- Unfreeze: `clusvcadm -U <resource-name>`

- Restart service: `clusvcadm -R <resource-name>`

- Disable service: `clusvcadm -d <resource-name>`

- Enable service: `clusvcadm -e <resource-name>`

- Cluster status: `cman_tool status`

- Validate cluster config: `ccs_config_validate`

- Fence/kill a node: `cman_tool kill -n node.name.com` or `fence_node node.name.com`

- Propagate the cluster.conf file after incrementing the `config_version` of the cluster.conf manually: `cman_tool version -r`

- Verify that all hosts have the same cluster conf: ccs -h localhost --checkconf

- Manually add LVM tag: `vgchange --addtag <hostname> <VG>`

- Check LVM tags: `vgs -o tags <VG>`


### Troubleshooting

- One of the best ways to troubleshoot a cluster issue is to stop the cluster and manually start the services as specified in the cluster.conf file in order. This often leads to finding out the problem.

- If the fencing device fails; it will retry indefinitely and your resource will be stuck. You can manually reset the node (this is important, don't keep it hanging), and then type `fence_ack_manual the.nodename.com`

- If you are facing unusual issues (each cluster thinks the other is dead although they can ping each other); try using UDP unicast instead.

- Be sure to set the dependencies correctly, eg. VG before the filesystem.

- If there are issues with the cluster; increase the logging levels. For service issues, set loglevel="7" in the <rm> tag of cluster.conf



### Pacemaker

From RHEL 6.5+ onwards, you have the option to use Pacemaker as the cluster management software, which is what RHEL7 uses, but note that it's not completely like RHEL7, in the sense that cman is _still_ used with Pacemaker in RHEL6, whereas in RHEL7 it's openais only, so it's more like a frankenstein combination of RHEL6 and RHEL7 clustering, though more towards the RHEL 7 end.

Why would you use Pacemaker? Well, it could be for one-off cases, like for-example some resource agents being only available in Pacemaker in RHEL 6. Or perhaps you'd want a more robust cluster, something that actually fucking fences the node when a resource fails to stop, rather than putting it on a permanent "failed" state. Or perhaps you are reading this in the future, where you are more comfortable with RHEL 7 clustering, but are faced with clustering a RHEL6 setup because of compatibility reasons.

This doc is just pretty brief BTW:

Install pacemaker:
```
<all nodes> yum -y install pacemaker cman pcs
<all nodes> chkconfig corosync off
```

Make sure all cluster nodes are in /etc/hosts. Set a password (preferably the same on all nodes) for hacluster, and start pscd:
```
<all nodes> passwd hacluster
<all nodes> service pcsd start && chkconfig pcsd on
```

Put in the username 'hacluster' and it's password in the following command that runs on the first node:
<node1> `pcs cluster auth node01 node02`
<node1> `pcs cluster setup --start --name cluster node1 node2`
<node1> optional, not recommended unless you expect the cluster to work without sysadmins> `pcs cluster enable --all`
<node1> `pcs cluster status`

Configure fencing by listing all the available fencing devices (`pcs stonith list`) and then getting details on it's parameters with `stonith describe fence_rhevm` Then you can either create a fencing device per node:
```
pcs stonith create RHEV-fence-node01 fence_rhevm params pcmk_host_list="node01" ipaddr="rhev.rizvir.com" ipport=443 login="admin@internal" passwd="thepass" ssl_insecure="1" plug="node01"
pcs stonith create RHEV-fence-node02 fence_rhevm params pcmk_host_list="node02" ipaddr="rhev.rizvir.com" ipport=443 login="admin@internal" passwd="thepass" ssl_insecure="1" plug="node02"
```

or better yet, create a hostmap in the format of "hostname:plug;nexthost:nextplug", working example:
```
pcs stonith create RHEV-Fencing fence_rhevm params pcmk_host_map="r-pacemaker-el6-01:r-pacemaker-el6-01;r-pacemaker-el6-02:r-pacemaker-el6-02" ipaddr="rhev.rizvir.com" ipport=443 login="admin@internal" passwd="thepass" ssl_insecure="1"
```

and test whether fencing works with:
```
pcs stonith fence node01
```

See the stuff about stonith/fencing under Common commands if you want to change or delete the fencing device.

Then you can add your resources, get a list of resources with:
```
pcs resource list
```
(incidentally, lsb resources are in /etc/init.d/, and ocf:heartbeat: are in /usr/lib/ocf/resource.d/heartbeat/)
 and after you find what you want, type:
```
pcs resource describe ocf:heartbeat:IPaddr2
```
for more info, and then add the resource with:
```
pcs resource create TestIP ocf:heartbeat:IPaddr2 ip=1.2.3.4 cidr_netmask=24 op monitor interval=30s
```
(you can omit the ocs:heartbeat: part, it's the default)

Though really, you'd probably want to use resource groups instead of individual resources independent of each other. So create a group called something and add the virtual IP to it:
```
pcs resource group add Apache TestIP
```

Then add more stuff as you see fit :
```
pcs resource create Something ... --group Apache
```

#### Common commands:

- Check cluster status: `pcs cluster status`
- Check resource status: `pcs status resources`
- Stopping the cluster service on a node: `pcs cluster stop` (use --all to stop it on all nodes)
- Putting a node on standby: `pcs cluster standby node01`
- Undo the above: `pcs cluster unstandby node01`
- Disable cluster service from starting up: `pcs cluster disable --all`
- Write cluster config to a file: `pcs cluster cib filename.xml`
- Load a cluster config from a filename: `pcs cluster cib-push filename.xml`
- Preview a change as it'd appear in the config: `pcs -f filename.xml resource create ....`
- You can view fencing devices with:
`pcs stonith show`
and details with:
`pcs stonith show TheName`
and change stuff with:
`pcs stonith update TheName thekey=thevalue`
or just delete it with:
`pcs stonith delete TheName`





