You can use a normal DHCP server for cross-cable installations, or a proxyDHCP if you connect to a switch to work with the existing DHCP server (this way, it'll get the IPs from the normal DHCP server, and will only provide addition PXE related information). We'll use DNSmasq to make it easier as proxyDHCP support on DHCPd seems a bit fuzzy. DNSmasq also has the added advantage of acting as a TFTP server without a separate daemon running.

### Installation 

* yum install dnsmasq syslinux
     
* Set up a directory to keep the TFTP images & PXE configuration. In my example, I kept it in /home/pxe
     
* You will have the pxelinux.0 file somewhere in your hard drive (eg. /usr/share/syslinux/). Copy the following files from that directory to your TFTP root:
```
cd /usr/share/syslinux/ && cp pxelinux.0 vesamenu.c32 menu.c32 memdisk /home/pxe/tftp-root/
```     

* Set up the dnsmasq.conf configuration:
```
	# proxyDHCP mode, if there is another DHCP server running. Put your own IP address or network here
	dhcp-range=10.113.0.2,proxy

	# Cross cable mode:
	#dhcp-range=10.113.0.200,10.113.0.220,8h
	#dhcp-option=option:dns-server,10.113.0.1
	#address=/pxe.local/10.113.0.1

	interface=eth0
	enable-tftp
	tftp-root=/home/pxe/tftp-root
	pxe-prompt="Loading", 0
	pxe-service=x86PC, "PXE", pxelinux
	log-dhcp
```

* Make the config directory: `mkdir /home/pxe/tftp-root/pxelinux.cfg`
     
* Create the default configuration as `/home/pxe/tftp-root/pxelinux.cfg/default`
```
DEFAULT vesamenu.c32
PROMPT 0
MENU TITLE Network boot
MENU INCLUDE pxelinux.cfg/graphics.conf
MENU AUTOBOOT Starting Local System in # seconds

LABEL local
		MENU LABEL ^Boot local OS
		MENU DEFAULT
		LOCALBOOT 0
		timeout 600
		TOTALTIMEOUT 9000

LABEL memtest
		MENU LABEL ^Memtest86+
		kernel images/Memtest/memtest86+-4.20
```         
* Also create a file called /home/pxe/tftp-root/pxelinux.cfg/graphics.conf with just one line:
```
    MENU BACKGROUND background.png
```
and copy any 640x480 PNG (or JPG) file to /home/pxe/tftp-root/background.png

Now, all the PXE boot files will be kept in `/home/pxe/tftp-root/images`. We'll start off with just Memtest86+. Create the directory `tftp-root/images/Memtest/` , and gunzip the Memtest binary to it, but rename the binary to remove the '.bin' extenstion, otherwise PXE would treat it specially. In the above menu, it is refererenced as images/Memtest/memtest86+-4.20

The final directory structure should be something like this:
```
.
`-- tftp-root
    |-- background.png
    |-- images
    |   `-- Memtest
    |       `-- memtest86+-4.20
    |-- memdisk
    |-- menu.c32
    |-- pxelinux.0
    |-- pxelinux.cfg
    |   |-- default
    |   `-- graphics.conf
    `-- vesamenu.c32
```

Restart dnsmasq and watch the logs as you boot a machine off the network. If all goes well, you should see the boot local option, and the Memory test option. Test the Memtest option to make sure it's working.

Instead of hard coding the IP address into each menu entry, we'll just use the domain "pxe.local" to reference the server IP. If you're in a LAN mode, add pxe.local to your DNS. If you're with a cross cable, then uncomment the "Cross-cable mode" lines above.

Note: I also enabled "tftp-secure" mode in dnsmasq.conf; just chmod the /home/pxe/tftp-root directory to the dnsmasq user and you can be sure an attacker using TFTP can't see your other files. However, enable this after you get things working.

### RHEL/CentOS 6

Create the directory structure similar to /.../tftp-root/images/CentOS/6.2/x86_64. Mount the CentOS ISO somewhere and copy the images/pxeboot/{vmlinuz,initrd.img} files to it. Also, copy the images/ directory to it as well. Unmount the ISO, and copy (or create a hardlink of) the ISO to /.../tftp-root/images/CentOS/6.2/x86_64. The final directory structure should be something like this:

```
tftp-root/images/
|-- CentOS
    `-- 6.2
        `-- x86_64
            |-- CentOS-6.2-x86_64-bin-DVD1.iso
            |-- images
            |   |-- TRANS.TBL
            |   |-- efiboot.img
            |   |-- efidisk.img
            |   |-- install.img
            |   `-- pxeboot
            |       |-- TRANS.TBL
            |       |-- initrd.img
            |       `-- vmlinuz
            |-- initrd.img
            `-- vmlinuz
```

Then add /.../tftp-root/images/CentOS/6.2/x86_64 to your /etc/exports file.

The menu entry in pxelinux.cfg/default would look like  this:

```
LABEL centos
        MENU LABEL ^CentOS 6.2 64-bit
        kernel images/CentOS/6.2/x86_64/vmlinuz
        append initrd=images/CentOS/6.2/x86_64/initrd.img ramdisk_size=8262 method=nfs:pxe.local:/home/pxe/tftp-root/images/CentOS/6.2/x86_64 ip=dhcp ksdevice=link lang=en keymap=us
```

 
### Clonezilla

* Download the ZIP version of any variant of clonezilla (debian or ubuntu)

* Make a directory called /.../tftp-root/images/Clonezilla/20120127-oneiric  (or whatever your version of clonezilla is). I find the debian version to start up much faster than the alternative/ubuntu version, but the debian version misses some proprietary blobs that makes the network not work for many HP or bnx2 based servers.

* Copy all the files in the ZIPs /live/* directory to the above TFTP directory

* I repeated the above procedure for the debian version of clonezilla

* Add this to the pxelinux.cfg/default:
```
LABEL clonezilla-live-20120127-oneiric
        MENU LABEL ^Clonezilla live 20120127-oneiric
        kernel images/Clonezilla/20120127-oneiric/vmlinuz
        append initrd=images/Clonezilla/20120127-oneiric/initrd.img boot=live live-config noswap nolocales edd=on nomodeset ocs_live_run="ocs-live-general" ocs_live_extra_param="" ocs_live_keymap="NONE" ocs_live_batch="no" ocs_lang="en_US.UTF-8" vga=788 nosplash fetch=tftp://pxe.local/images/Clonezilla/20120127-oneiric/filesystem.squashfs

LABEL clonezilla-live-1.2.12-10-amd64
        MENU LABEL ^Clonezilla live 1.2.12-10-amd64
        kernel images/Clonezilla/1.2.12-10-amd64/vmlinuz
        append initrd=images/Clonezilla/1.2.12-10-amd64/initrd.img boot=live config noswap nolocales edd=on nomodeset ocs_live_run="ocs-live-general" ocs_live_extra_param="" ocs_live_keymap="NONE" ocs_live_batch="no" ocs_lang="en_US.UTF-8" vga=788 nosplash fetch=tftp://pxe.local/images/Clonezilla/1.2.12-10-amd64/filesystem.squashfs
```

If this is a clonezilla used in a lab, it's also convenient to have SSH start up with a password assigned automatically (with your DHCP/DNS server set up to provide a consistent way of accessing the machine). You need access to an ubuntu machine or live setup, and run mkpasswd which is provided by the 'whois' package (this is not the same mkpasswd provded by EL). Type:
echo 'yourpassword' | mkpasswd -s
(it will output a different hash every time)

Then add this to the initrd line:
```
usercrypted=abcJ9Icscxyz ocs_daemonon="ssh"
```
