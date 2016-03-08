Make sure you do the standard OS ([EL6](/articles/el6-standard-installation/) or [EL7](/articles/el7-standard-installation/) setup, particularly the dnsmasq & NTP bit. 

### DNS

Make sure dnsmasq starts up on boot, and is the primary DNS server. Add an mx-host to **/etc/dnsmasq.conf** (EL6) or **/etc/dnsmasq.d/local.conf** (EL7)
```
mx-host=serversfqdn.domain.com,serversfqdn.domain.com,50
```
and restart dnsmasq.
You'll also want to comment out the `::1 localhost` line in **/etc/hosts**, otherwise zmconfigd would not start (at least in 8.5.1)

The local caching DNS aside, you need to also start the process of setting up the actual internet domain's forward DNS (A record) via your DNS hosting panel, and the reverse DNS (PTR record) for the IP by contacting the ISP, as this may take some time. (You will later need to change the MX records; this takes great planning and thought if you don't want to lose emails. Also considering having an SPF record. For example, if Zimbra is the MX and is the only server allowed to send emails, add the SPF/TXT record `v=spf1 mx -all`)



### Installing Zimbra

When running `install.sh`, make sure that you do NOT install (type n) zimbra-dnscache. Install the rest with the defaults, including the memcache/proxy as according to the wiki future updates will depend on memcached & the proxy heavily even for single node installs (probably for filtering).
 
Just set the admin password, and keep everything else the same, including the FDQN domain name. You can later set the proper default domain name.
 
Install 'unrar' to be able to scan attachments inside .rar files; it's not in EPEL because of some licensing issues, so get it from [here](http://pkgs.repoforge.org/unrar/)



### Certificates

This section should be ignored unless you have commercial certificates, but having a commercial certificate is quite important in a production install (though I suppose you could use the free cert available from [LetsEncrypt](https://letsencrypt.org/), though I haven't tried using that with Zimbra yet).
 
BTW: if you are faced with a downtime that has to do with certificates and zimbra not functioning, and you are sure your server hasn't been compromised, disable certificate checks with, as zimbra: `zmlocalconfig -e ssl_allow_untrusted_certs=true`
 
#### Commercial single server setup

Use a simple certificate if Zimbra will be accessed using one URL (even if you host multiple domains), or a UCC certificate if there'd be access from multiple URL domains.
 
Before anything, create a snapshot if your zimbra logical volume. You can mess zimbra up very easily when playing with certificates.
 
The admin UI, at least for Zimbra 8.0.7, is broken when it comes to generating CSRs ([bug 89662](https://bugzilla.zimbra.com/show_bug.cgi?id=89662)). Use the command line, as root:
 
```
/opt/zimbra/bin/zmcertmgr createcsr comm -new -keysize 2048 -subject '/C=XX/ST=YourState/L=YourCity/O=YourOrg/OU=IT/CN=mail.yourdomain.com'
```

If you have a UCC certificate, you can append `-subjectAltNames 'mail.yourdomain.com,anothername.domain.com'`

The CSR ought to be in /opt/zimbra/ssl/zimbra/commercial, verify the cert details with:
 
```
cd /opt/zimbra/ssl/zimbra/commercial
openssl req -in commercial.csr  -noout -text
``` 

If it seems fine, cat the CSR and paste it in your certificate vendors portal. After they verify everything, you should get your hands on the certificate. GoDaddy (with the Apache format) gives two files: one with a random filename.crt which is your cert and one that starts with gd_ which is the CA (if there are multiple CA files, you need to cat them into one file). Keep these in say /root/certs, and verify it:
 
```
cd /root/apps/certs
unzip /root/apps/GoDaddy_cert_201x.zip
openssl x509 -in abcdeaa1123456.crt -text -noout
/opt/zimbra/bin/zmcertmgr verifycrt comm /opt/zimbra/ssl/zimbra/commercial/commercial.key ./abcdeaa1123456.crt ./gd_bundle-g2-g1.crt
```

It should say that the certificate is valid and OK. Now verify that you have your LVM snapshot, and run:

```
/opt/zimbra/bin/zmcertmgr deploycrt comm ./abcdeaa1123456.crt ./gd_bundle-g2-g1.crt
/opt/zimbra/bin/zmcertmgr viewdeployedcrt
```
 
Stop and start Zimbra. If Zimbra does not start, you are screwed, and would probably want to revert/merge your LVM snapshot and find out what went wrong.
<br>

#### Commercial multiserver

It's _much_ easier taking a wild card certificate if you have a multiserver setup. Take a snapshot of all the servers in case something goes wrong.

You'd need to work on a mailbox server. Generate the CSR and do the steps mentioned above for a single server setup on the mailbox server, up to 'deploycrt'. 

Then copy the /root/apps/certs to every other node (for reference), as well as /opt/zimbra/ssl/zimbra/commercial/commercial.key. Run the previous commands (starting with verifycrt) on each of the nodes. Then stop zimbra on all the nodes (doing the LDAP one last), and start all the nodes (starting with LDAP). Double check via the HTTPS web client that the browser sees the commercial cert and doesn't complain.



### Firewall

Follow the [firehol setup guide](/articles/easy-secure-firewalls-with-firehol/).

It's usually best keeping outgoing connections restrictive on any public-facing server, however this greatly complicates things because of antispam rule updates, virus definition updates, RBL checks, razor, pyzor, dcc, etc. It can get very tedious putting in every IP/hostname of every update server, and even then the IPs may change, and so will be suddenly blocked when this happens (since the IP is only resolved once when iptables/firehol loads the rule). It would have been easier if spam, clamav, and RBL checks where done by different UIDs, but they are all done as the zimbra user, so doing a "client all accept user zimbra" would really add nothing to security and you might as well allow everything (`client all accept`)
However, if restricting outgoing connections for security is really important, you can try restricting some connections as explained below, but since there is a chance of failed updates, make sure nagios/icinga monitors ClamAV and spamassassin to make sure rules aren't too old. If they are, and if you think the firewall is blocked it, restart firehol for it to get new IPs.

_(If you're interested in knowing why the firewall is complex, read this paragraph. ClamAV updates are received via first checking if there is an update by doing a DNS TXT lookup on current.cvd.clamav.net to check the latest definiton version number. If an update is required, it does a round-robin lookup on the "DatabaseMirror" lines in /opt/zimbra/conf/freshclam.conf, so one hostname like db.us.clamav.net may resolve to dozens of IPs, and it then fetches the updates via HTTP. Spamassassin updates are done by first getting a list of mirrors via a text file. The location of this text file is checked via a DNS TXT lookup on mirrors.{update-server}, which by default is mirrors.updates.spamassassin.org. This currently (and probably will for a long time) points to http://spamassassin.apache.org/updates/MIRRORED.BY, which always seems to change, and has comments that start with a #. The actual update is done via HTTP/HTTPS. RBL's are done via DNS lookups to various hostnames, some of which may change with new antispam definitions, so we'd have to allow all outgoing DNS requests.)_
 
The setup below isn't completely locked down; ports like 24441 (pyzor) are still wide open, but at least it's better than allowing everything.
 
For a multiserver setup; it'd be much cleaner if you whitelist all the node IPs, rather than allowing each service that should be used internally (eg. ldap) manually. This way, only the MTA & Proxy would need incoming/outgoing ports opened, the mailbox servers and LDAP server(s) can be closed off entirely.
 
Set up firehol according to the usual guide (testing it with just ssh allowed to make sure firehol works and you aren't locked out), and then use something similar to this config being sure to change the interface names as required:
 
```bash
# Zimbra Firewall
version 5

FIREHOL_LOG_PREFIX="firehol: "
LAN="192.168.98.0/24"

# usage example:
# allow_domain 'domainname.com another.domain.com' 'client http accept dst'
function allow_domain() {
        domains="$1"
        firehol_line="$2"

        for domain in ${domains}; do
                while read ip; do
                        if echo $ip | grep -Eq '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'; then
                                $firehol_line "$ip"
                        fi
                done < <(dig ${domain} +short +tries=1 +time=3)
        done
}

interface eth0 lan
        server ssh accept
        server ping accept

        server "http https" accept
        server "smtp smtps" accept
        server submission accept
        server "imap imaps" accept
        server "pop3 pop3s" accept

        # Port 7071 should not be visible to the internet, allow it for internal IPs only
        server custom zimbraadmin tcp/7071 default accept src "$LAN"
        # LDAP for internal users only too, if you have the OSS edition and want an address book
        server ldap accept src "$LAN"

        # Restrict outgoing connections. To allow everything, use client all accept
        client all accept user "root"
        client ntp accept user "ntp" # change user to chrony for EL7
        client smtp accept
        client dns accept
        client custom pyzor "tcp/24441 udp/24441" any accept
        client custom razor "tcp/2703 tcp/7" any accept
        client custom dcc "udp/6277" any accept

        # ClamAV
        allow_domain "db.us.clamav.net database.clamav.net" 'client http accept dst'
        allow_domain "db.us.clamav.net database.clamav.net" 'client https accept dst'

        # SpamAssassin
        allow_domain "spamassassin.apache.org" 'client http accept dst'
        allow_domain "spamassassin.apache.org" 'client https accept dst'
        allow_domain "yerp.org" 'client http accept dst'
        allow_domain "yerp.org" 'client https accept dst'
        sa_mirror_list=$(dig txt mirrors.updates.spamassassin.org +short +tries=1 +time=3 | tr -d '"')
        sought_mirror_list=$(dig txt mirrors.sought.rules.yerp.org +short +tries=1 +time=3 | tr -d '"')
        while read line; do
                if echo $line | grep -vq '^#\|^$'; then
                        sa_mirror=$(echo $line | sed -e 's/.*:\/\/\([^\/]*\).*/\1/g')
                        allow_domain "$sa_mirror" 'client http accept dst'
                        allow_domain "$sa_mirror" 'client https accept dst'
                fi
        done < <(curl -s $sa_mirror_list $sought_mirror_list)
```



### Changes via the Admin console

- Create the main domain: go to Configure -> Domains, then click on the top right gear account, and select New.

- Go to Configure -> Class of service, and double click on 'default'. In the Preferences, consider: 
	- changing "Group mail by" to "messages" instead of "coversations" if you think the users would be confused by threaded conversations.
	- Check "Highlight the Mail tab when a message arrives" and "Flash the browser title when a message arrives".
	- Change the timezone to your city
	- Click on Save on the top right corner.

- Disable the com_zimbra_phone zimlet in the Zimlets section.

- Go to Configure -> Global Settings, and make these changes: 
	- General Information: set the Default Domain
	- Attachments: Disable "Send blocked extension notification to recipient". Add all the extensions mentioned to the block list. Also add 'cab',  'jar' and 'ace' to the list (some dangerous viruses using that, which can't be decoded by amavis)
	- MTA: Modify the maximum message size as required. Uncheck "Add X-Originating-IP to messages" as some antispam scanners check the client IPs against RBLs (which almost gets a hit). If you need to allow plain text SMTP connections (not recommended, but may be required if you don't have a cert), uncheck "TLS authentication only".
	- IMAP: If it's a large (>1000) setup and you have lots of RAM, increase the IMAP threads. If you need to allow plain text imap (not recommended), enable "Clear text login" here.
	- POP3: Same as IMAP
	- AS/AV: Uncheck "Block encrypted archives" (otherwise it would block password protected ZIPs, which though is a means by malicious senders to bypass AV scanning, is also used legitimately by many users) and uncheck "Send notification to recipient", as otherwise you're users would be flooded with virus alerts that would scare them unnecessarily.

- Create an alias of admin@yourdefaultdomain.com to admin@fqdn.hostname.com, so that you just need to log in as 'admin' rather than 'admin@fqdn..."

- Go to Configure -> Global Settings -> MTA, and enable the Milter service. This is optional but would allow restrictions on distributions lists without unsupported postfix hacks. It also can add the reply-to header from messages sent from DLs.

- Go to Configure->Servers->your (proxy) server->Proxy, and set the web proxy mode to "redirect" (or "both" (not recommended) if you want to allow http, or mixed if you just want the login as https). If you need to allow plain text connections (not recommended): set POP3 & IMAP to allow both cleartext and starttls instead of starttls only, and as zimbra, run "zmtlsctl both" Remember that passwords can very easily be sniffed in plaintext connections, so it's best not doing this.

- If the CPU isn't old or slow, it's best to compress the mail store, this can have significant savings on disk space. Go to Configure -> Servers -> your (mailbox) server -> Volumes , edit the store volume, and CHECK the "Compress Blobs" option, and press OK. This will only compress emails coming in from that point on; older emails will not be compressed.

- If this is a new setup (do not run this on an existing install, or your users can be locked out), and not a migration, or if you have the option of setting/changing everyone's password, and you don't have external authentication, go to Configure->Class of service->default->Advanced and increase the password complexity requirement by increase minimums of various types of characters. 


### Changes via the command line

- (Only if requested) If you want to allow IPs to send email without a password, you can change the mynetworks parameter, but the mynetworks settings is buggy in the web UI (bug [#78681](https://bugzilla.zimbra.com/show_bug.cgi?id=78681)). Use the command line: 
```
zmprov ms $(hostname) zimbraMtaMyNetworks '127.0.0.0/8 [::1]/128 [fe80::]/64 1.2.3.4/32'
```

- Set the disk space warning to something reasonable:
```
zmlocalconfig -e zmdisklog_warn_threshold=95
zmlocalconfig -e zmstat_disk_interval=7200
```

- Enable subject logging. Note that subject logging depends on unchecking the "send blocked extension notification" you did earlier. On the MTA, edit the file **/opt/zimbra/conf/postfix_header_checks.in**, and add the line:
```
/^subject:/      WARN
```

- To log the username of authenticated emails in the header, run:
```
zmprov mcf zimbraMtaSmtpdSaslAuthenticatedHeader yes
```

- As a workaround of a bug in some versions of Outlook that re-uses message-IDs, which results in missing email if the sender edits an older email to send a new one, run (on all the mailbox servers):
```
zmprov mcf zimbraMessageIdDedupeCacheTimeout 60
```

- The GAL by default will only return entries for the same domain that the user is in. If you want all addresses from all domains to appear, enter:
```
 zmprov modifyConfig zimbraGalInternalSearchBase ROOT
```

- Until [this bug](https://bugzilla.zimbra.com/show_bug.cgi?id=80563) is fixed (and perhaps even if it is for performance reasons, unless sniffing on the LAN is possible), run this on the server (or the Proxy node in a multiserver setup):
```
zmprov ms `hostname` zimbraReverseProxySSLToUpstreamEnabled FALSE
```

- If there are a lot of IMAP users, especially thunderbird users (which opens up IMAP connections per folder), increase the amount of threads and connections (repeat for POP3 with zimbraPop3MaxConnections & zimbraPop3NumThreads):
```
zmprov ms `hostname` zimbraImapMaxConnections 500
zmprov ms `hostname` zimbraImapNumThreads 500
```

- The default DoS policy blocks users or zmprov commands doing more than 30 actions a second, this is usually too low for scripts and some heavy thunderbird users (FYI: logs for DoS rejected actions are not kept in mailbox.log but rather zmmailbox.out; search for DoSFilter). Increase it to 300:
```
zmprov mcf zimbraHttpDosFilterMaxRequestsPerSec 300
```

- Zimbra will block an entire IP address if there are more than 10 incorrect login attempts within a period, which is pretty bad as it often blocks an entire office if one person forgot his password. Increase it to 99 if you prefer availability over security:
```
 zmprov mcf zimbraInvalidLoginFilterMaxFailedLogin 99
```

- Increase the log retention period by using `crontab -e -u zimbra` and changing the `+8` in this line:
`30 2 * * * find /opt/zimbra/log/ -type f -name \*.log\* -mtime +8 -exec rm {} \; > /dev/null 2>&1`
to `+31`. Also edit /etc/logrotate.d/zimbra and add `rotate 31` to the /var/log/zimbra.log section under "daily".

- The server would by default send a MAILER-DAEMON message to a sender of a banned attachment, but the problem is that we face a huge number of .exe virus laden emails with spoofed FROM addresses, resulting in the postfix queue piling up with undeliverable messages, not to mention the contribution we'd have to [backscatter](http://en.wikipedia.org/wiki/Backscatter_%28email%29), so to prevent this edit /opt/zimbra/conf/amavisd.conf.in and change:
`$final_banned_destiny = D_BOUNCE;`
to
`$final_banned_destiny = D_DISCARD;`

- Sometimes, you need to find out why an obvious spam was detected as ham in the headers, but the the reason is not kept in the headers for very low scoring emails, so edit /opt/zimbra/conf/amavisd.conf.in and change:
`$sa_tag_level_deflt  = -10.0;`
to
`$sa_tag_level_deflt  = -999.0;`


- You would probably want to increase the briefcase (or IMAP, in case of imapsync) upload limit from 10MB to say 100MB:
```
zmprov mcf zimbraFileUploadMaxSize 104857600
```

- You can have a file where you can add IPs or, importantly, hostnames that postfix would reject; this is documented in the [wiki](http://wiki.zimbra.com/wiki/New_Features_ZCS_8.5). Blacklisting IPs doesn't make a lot of sense as you can easily do that with iptables, but where this is useful is blacklisting hostnames, since you can just put the parent domain, and it will block all subdomains. So if you get a lot of spam from say the hostname 68-233-245-196.static.hvvc.us , you can add 'hvvc.us' to this file, and all IPs from that ISP will be blocked. So run:
```
touch /opt/zimbra/conf/postfix_blacklist
echo "# The file has to be in the format:" >> /opt/zimbra/conf/postfix_blacklist
echo "# .domain.com  REJECT" >> /opt/zimbra/conf/postfix_blacklist
chown zimbra:zimbra /opt/zimbra/conf/postfix_blacklist
su - zimbra
postmap /opt/zimbra/conf/postfix_blacklist
zmprov mcf +zimbraMtaRestriction 'check_client_access lmdb:/opt/zimbra/conf/postfix_blacklist'
```


- If an account gets compromised or if a developer error results in an email receiving tons of email, it's helpful to have a handy easy-to-modify postfix blacklist (note: this is undocumented and so does not stick over through upgrades) :
```
touch /opt/zimbra/postfix/conf/blacklist_email_to /opt/zimbra/postfix/conf/blacklist_email_from
echo "# Put address in the format:" | tee -a /opt/zimbra/postfix/conf/blacklist_email_to /opt/zimbra/postfix/conf/blacklist_email_from
echo "# domain.com REJECT sending spam" | tee -a /opt/zimbra/postfix/conf/blacklist_email_to /opt/zimbra/postfix/conf/blacklist_email_from
echo "# user@somedomain.com REJECT blocked on request of xxx" | tee -a /opt/zimbra/postfix/conf/blacklist_email_to /opt/zimbra/postfix/conf/blacklist_email_from
su - zimbra
postmap /opt/zimbra/postfix/conf/blacklist_email_to
postmap /opt/zimbra/postfix/conf/blacklist_email_from
exit
```

Then back up and edit /opt/zimbra/conf/zmconfigd/smtpd_sender_restrictions.cf , add this right at the top:
```
check_sender_access lmdb:/opt/zimbra/postfix/conf/blacklist_email_from
check_recipient_access lmdb:/opt/zimbra/postfix/conf/blacklist_email_to
```

Then just 'postfix reload' or do an MTA restart. To add addresses, just edit the blacklist file in this format:
```
domain.com REJECT sending spam
user@somedomain.com REJECT blocked on request of xxx
```

and run a postmap as zimbra, and either wait for around a minute or do a postfix reload.


- It's very important to prevent people from being able to use any MAIL FROM spoofing for authenticated senders. This will prevent accounts that have been compromised from sending email as anyone they like (MAIL FROM address only which appears in the logs and headers, different from the body From: which may still be spoofed). I used to have hacks for this but it's now [supported](https://wiki.zimbra.com/wiki/Enforcing_a_match_between_FROM_address_and_sasl_username_8.5) in 8.5. 

`touch /opt/zimbra/conf/slm-exceptions-db`

This file will allow you to add alternative email addresses per user, for example if the user print sends email as printer@xerox.local, you can add:

`printer@xerox.local  print`

But it should at least exist, so touch the file, and then:
```
su - zimbra
postmap /opt/zimbra/conf/slm-exceptions-db
zmprov mcf zimbraMtaSmtpdSenderLoginMaps 'lmdb:/opt/zimbra/conf/slm-exceptions-db, proxy:ldap:/opt/zimbra/conf/ldap-slm.cf' +zimbraMtaSmtpdSenderRestrictions reject_authenticated_sender_login_mismatch
```

- By default, the mailbox.log file with not have the IP address of successful/failed POP3/IMAP logins when having a proxy, so run the following command (replacing 192.168.1.2 with the LAN IP of your server.
```
zmprov mcf +zimbraMailTrustedIP 127.0.0.1 +zimbraMailTrustedIP 192.168.1.2
# (If this is a multiserver setup, you don't need 127.0.0.1, just the LAN IP of the proxy node)
```

- If you enabled the java based milter service to restrict access to distribution lists, you should know that it's not 100% stable. It's getting better with every release, but to be safe, it's best to have postfix send the email as usual if the milter service fails rather than the default "tempfail", which would require the sending party (which may either be a mail server or an annoyed user) to send the email again (it doesn't help that most of the instability shows up with large attachments+slow links). So run, as zimbra:
```
zmprov mcf zimbraMtaMilterDefaultAction accept
```

- Some users sometime can face disconnects when they connect via IMAP ("Server unexpectedly terminated the connection"), with this message in the mailbox.log file "BAD maximum line length exceeded". So preemptively increase the request size from 10240 to:
```
zmprov ms $(hostname) zimbraImapMaxRequestSize 51200
```

- (optional, migration only) If you are migrating from a different server that kept the Sent folder elsewhere, you can use this to set the folder where messages sent via the web interface would be go:
```
zmprov mc default zimbraPrefSentMailFolder "Sent Items"
# You can also set it for some users only :
zmprov ma dude@company.com zimbraPrefSentMailFolder "Sent Items"
```

- (optional) Create a script to have a plain text dump of the SQL/LDAP database just in case, so create a file called /root/scripts/zimbra_mysql_ldap_backup.sh that you can add to cron:
```
#!/bin/bash
export backup_dir="/root/backups/zimbra_db_backups"

mkdir -p $backup_dir

#MYSQL
su - zimbra -c '
source /opt/zimbra/bin/zmshutil;
zmsetvars;
/opt/zimbra/mysql/bin/mysqldump --user=root --password=$mysql_root_password --socket=$mysql_socket --all-databases --single-transaction --flush-logs;
' | gzip > $backup_dir/mysqldump.sql.gz

#LDAP
mkdir /tmp/zmdbb
chown zimbra /tmp/zmdbb
su - zimbra -c "/opt/zimbra/libexec/zmslapcat /tmp/zmdbb"
su - zimbra -c "/opt/zimbra/libexec/zmslapcat -c /tmp/zmdbb"
mv /tmp/zmdbb/*.bak $backup_dir/
rm -rf /tmp/zmdbb
```

- (Optional) If the web interface would be used a lot, you might want to allow people to save passwords, if convenience trumps ultra high security. To allow the browser to save passwords, edit /opt/zimbra/jetty/webapps/zimbra/public/login.jsp and change:
`<td><input id="password" autocomplete="off" class="zLoginField" name="password"`
to
`<td><input id="password" class="zLoginField" name="password"`



### Network edition

- Assuming you have licenses for the Outlook connector and touch client for all users, you may need to manually enable those features in the class of service

- ActiveSync is disabled out of the box, go to the class of service, and click on "Mobile Access" on the _left_, and then check "Enable MobileSync"

- If you do enable ActiveSync, go to the class of service -> Mobile, and increase the "Failed attemps allowed" from 4 to say 99, otherwise eg. a kid playing with a phone can lead to a phone data wipe.

- You can consider having a script to purge files older than 2 weeks in the /opt/zimbra/redolog/archives directory. If you are in production, have a look at how large that directory gets. It's safe to delete old versions of these files (older than a day).

- I find the network edition backups to be extremely wasteful in terms of space (see the size of your /opt/zimbra/backups), so since I use [rsnapshot](/articles/secure-backups-with-rsnapshot/), I disable zimbra backups with `zmschedulebackup -F`, though if you have the space, keep it enabled as it's MUCH easier restoring someones mailbox with zimbra's native backup, vs. starting up zimbra in the standby rsnapshot server and exporting/syncing the emails.



### Improving antispam

- Zimbra 8 has this wonderful feature of automatic spam definition updates (missing in Zimbra 7), but it's disabled by default, so enable it (antispam_enable_restarts will restart amavis in the night if there is a spam definition update):
```
zmlocalconfig -e antispam_enable_rule_updates=true
zmlocalconfig -e antispam_enable_restarts=true
zmlocalconfig -e antispam_enable_rule_compilation=true
```

- Set up Pyzor. Although it's in the EPEL in EL6 (not for EL7), the one in EPEL is way too old and did not trigger with my sample spam message, so let's get the latest version, download the tar.gz from https://pypi.python.org/pypi/pyzor/, and untar & cd into the directory, then:
```
python setup.py build
python setup.py install
# As zimbra:
pyzor --homedir /opt/zimbra/data/amavisd/.pyzor ping # this should show 200 OK
```

Then add this to /opt/zimbra/data/spamassassin/localrules/sauser.cf (create the file if it does not exist):
```
use_pyzor 1
pyzor_path /usr/bin/pyzor
pyzor_options --homedir /opt/zimbra/data/amavisd/.pyzor
pyzor_timeout 5
```

And do a:
```
mkdir -p /opt/zimbra/data/amavisd/.pyzor
chown -R zimbra:zimbra /opt/zimbra/data/amavisd/.pyzor
```
To see if it works, get a sample spammy .eml file somewhere, upload it to /tmp/sample_spam.eml, and then run:
```
/opt/zimbra/zimbramon/bin/spamassassin -t -D pyzor < /tmp/sample_spam.eml
```

You should see no Python exceptions, and the strings "pyzor is available", "got response: public.pyzor.org:24441 (200, 'OK')". Your test message should also trigger the PYZOR_CHECK rule.


- Set up Razor, it's in the EPEL for both EL6 & EL7:
```
yum install perl-Razor-Agent
su - zimbra
razor-admin -home=/opt/zimbra/data/amavisd/.razor -create
razor-admin -home=/opt/zimbra/data/amavisd/.razor -discover
razor-admin -home=/opt/zimbra/data/amavisd/.razor -register
```

Then append:
```
razorhome              = /opt/zimbra/data/amavisd/.razor
```
to /opt/zimbra/data/amavisd/.razor/razor-agent.conf. Then add:
```
use_razor2 1
razor_config /opt/zimbra/data/amavisd/.razor/razor-agent.conf
```
to  /opt/zimbra/data/spamassassin/localrules/sauser.cf. To see if it works, with your sample spam .eml file, run:
```
/opt/zimbra/zimbramon/bin/spamassassin -t -D < /tmp/sample_spam.eml
```
You should see the RAZOR2_CHECK rule hit.


- Set up DCC: [download DCC](http://www.dcc-servers.net/dcc/source/dcc.tar.Z), and then:
```
cd /tmp/
tar xvzf /root/apps/dcc.tar.Z
cd dcc*
chown -R zimbra:zimbra /tmp/dcc-*
mkdir /opt/zimbra/dcc
chown zimbra:zimbra /opt/zimbra/dcc
su - zimbra
cd /tmp/dcc-*
./configure --homedir=/opt/zimbra/dcc --disable-sys-inst --with-uid=zimbra --disable-server --disable-dccifd --disable-dccm --with-updatedcc_pfile=/opt/zimbra/data/dcc --with-rundir=/opt/zimbra/data/dcc/run --bindir=/opt/zimbra/dcc/bin
make -j 4
make install
mkdir -p /opt/zimbra/data/dcc/run
```

Then add this to /opt/zimbra/data/spamassassin/localrules/sauser.cf :
```
use_dcc 1
dcc_path /opt/zimbra/dcc/bin/dccproc
```

To see if it's working with your spam .eml: 
```
/opt/zimbra/zimbramon/bin/spamassassin -t -D < /tmp/sample_spam.eml
```

You should see the DCC_CHECK rule hit.


- Install the SOUGHT rules. Do a:
```
cd /tmp
wget http://yerp.org/rules/GPG.KEY
su - zimbra
/opt/zimbra/zimbramon/bin/sa-update --import /tmp/GPG.KEY
```
Edit the file /opt/zimbra/libexec/zmsaupdate, and change the my $sa variable (~line 58) from: 
```
my $sa="/opt/zimbra/zimbramon/bin/sa-update -v --allowplugins --refreshmirrors >/dev/null 2>&1";
```
to
```
my $sa="/opt/zimbra/zimbramon/bin/sa-update -v --channel sought.rules.yerp.org --channel updates.spamassassin.org --gpgkey 6C6191E3 --allowplugins --refreshmirrors >/dev/null 2>&1";
```

Do a test sa-update as zimbra.

- All spamassassin customizations must be on the (not created by default) file /opt/zimbra/data/spamassassin/localrules/sauser.cf. Add these:
```
# Reduce scores for legitimate emails:
# Some people have a habit of saying "Dear Sir"
score DEAR_SOMETHING 0.001
# Also using all caps
score SUBJ_ALL_CAPS 0.001
# and a lot of spaces for attempted aligning
score TVD_SPACE_RATIO 0.001
# Or 75% to 100% caps
score UPPERCASE_75_100 0.001
# or 50% to 75% caps
score UPPERCASE_50_75 0.001
# or no subjects
score MISSING_SUBJECT 0.001
# Don't punish if the time is 3-12 hours different (eg. timezone without RFC syntax)
score DATE_IN_FUTURE_03_06 0.001
score DATE_IN_FUTURE_06_12 0.001
# Spamassassin often doesn't keep updated with Outlook version/service packs
score FORGED_MUA_OUTLOOK 0.001
# A lot of valid servers are in the PBL, so lower it from 3.3 to 1
score RCVD_IN_PBL 1
# HTML is OK
score MIME_HTML_MOSTLY 0.001
score MIME_HTML_ONLY 0.001
# The following gives a lot of false positives
score MISSING_MIMEOLE 0.001
score SHORT_HELO_AND_INLINE_IMAGE 1
score TVD_RCVD_IP4 0.001
score TVD_RCVD_IP 0.001
score DOS_OUTLOOK_TO_MX 1
score MSGID_NOFQDN1 0.001 
# Practically whitelist e-mails that are from web interface 
score ALL_TRUSTED -20
# The AI claims it's ~0% chance of spam
score BAYES_00 -20
score BAYES_05 -10

# Increase scores:
score URIBL_BLACK 5.5
score URIBL_SBL 5.5
score URIBL_JP_SURBL 5.5
score URIBL_WS_SURBL 5.5
score URIBL_OB_SURBL 5.5
score RAZOR2_CHECK 4.500
score RAZOR2_CF_RANGE_E8_51_100 3
score PYZOR_CHECK 4.500
score DCC_CHECK 4
score HELO_DYNAMIC_IPADDR 5.5
score RDNS_NONE 5 # from 0.793
score BAYES_99 6
score BAYES_95 5.5
score BAYES_90 4.500
score BAYES_80 3
score BAYES_60 2
score GAPPY_SUBJECT 2.8 # from 1.954
score RCVD_IN_BRBL_LASTEXT 3.5 #from 1.449
score RCVD_IN_XBL 1 # from 0.375
score RCVD_IN_BL_SPAMCOP_NET 2 # from 1.347
score RCVD_IN_SBL 2 # from 0.141
score FREEMAIL_FORGED_FROMDOMAIN 3 # from 0.25
score NO_DNS_FOR_FROM 2 # from 0.001
score ADVANCE_FEE_4_NEW 4 # from 2.596
score FREEMAIL_ENVFROM_END_DIGIT 3 # from 0.25
score FREEMAIL_FORGED_REPLYTO 4 # from 2.095
score MALFORMED_FREEMAIL 4 # from 1
score SPF_FAIL 30 # from 0.001

```

- If you are willing to manually train hundreds of emails, enable DSPAM: run this on the MTA:
```
zmlocalconfig -e zimbraAmavisDSPAMEnabled=true  # ? not sure if this affects anything
zmprov ms `zmhostname` zimbraAmavisDSPAMEnabled TRUE  # This definitely works
```

DSPAM is pretty terrible without lots of training and will just add +10 to every email causing most email to end up going to spam (ham messages are -1 BTW). You really should make it 1 for spam, and -0.1 for ham, until you train it, and manually sample email to make sure DSPAM is working OK. So edit /opt/zimbra/conf/amavisd.conf.in and change: 
```
%%uncomment VAR:zimbraAmavisDSPAMEnabled%%         mail_body_size_limit => 64000, score_factor => 1,
```
to
```
%%uncomment VAR:zimbraAmavisDSPAMEnabled%%         mail_body_size_limit => 64000, score_factor => 0.1,
```

Later on (~a month of training when you have 1000+ messages trained), you can change this to 0.5 (or 1 if you have 100% faith on it).


- (optional) In the first few weeks of running the server, you or someone needs to browse emails (perhaps on random mailboxes, or on those who receive a lot of spam emails) and both mark emails as spam (even if it's already in the Junk folder, unless it's there only because you marked it before) as well as forward legitimate emails to the ham account AS AN ATTACHMENT. I repeat, emails have to be forwarded as attachments before sending them (you can make it the default if you want via the zimbra user preferences). You can find the spam/ham account that you need to forward email to (which is random on each server) by a simple `zmprov -l gaa | grep -E '^(sp|h)am\.`
Forward a bit of email to both ham and spam, then run:
```
/opt/zimbra/libexec/sa-learn --dbpath /opt/zimbra/data/amavisd/.spamassassin --dump magic
```
and note down the nspam and nham values.
Then run the actual training (which is done in cron BTW, see crontab -l -u zimbra) :
```
/opt/zimbra/bin/zmtrainsa >> /opt/zimbra/log/spamtrain.log 2>&1
/opt/zimbra/bin/zmtrainsa --cleanup >> /opt/zimbra/log/spamtrain.log 2>&1
```

Run the:
```
/opt/zimbra/libexec/sa-learn --dbpath /opt/zimbra/data/amavisd/.spamassassin --dump magic
```
command again, and make sure the nspam and nham values increased from last time. Possible reasons it may not increase is if you or someone trained the same messages before at one point, or if zimbra has a bug (8.x versions before 8.6 patch 3 did not train).

At least 200 messages needs to be marked as spam or ham for the baysian filtering to work at all according to SpamAssassin (though zimbra reduced the bare minimum to 60). Around 400 of each is highly recommended. Since you are manually training the spam filder, you can disable auto-training for a few weeks as that is pretty unreliable, edit /opt/zimbra/conf/salocal.cf.in and change:
```
bayes_auto_learn 1
```
to
```
bayes_auto_learn 0
```

Once you think the BAYES_XX numbers make sense (i.e. close to 00/05 for ham emails, and close to 95/99 for spam emails), you can enable bayes_auto_learn again.


### Limited admins

Creating limited admins is actually possible on the open source edition. Weirdly this seems to be completely undocumented on the internet; everyone seems to be under the impression that this feature is not available without the Network Edition just because the GUI is missing. 
Create the limited admin user, make sure the user is _not_ a Global Administrator. Using the example limitedadmin@domain.com. 
Create a distribution list for the admins with the FQDN domain, and select the option to not receive email and hide in GAL. Using the example limitedadmins@domain.com : 
```
zmprov modifyDistributionList limitedadmins@domain.com zimbraIsAdminGroup TRUE
zmprov modifyAccount limitedadmin@domain.com zimbraIsDelegatedAdminAccount TRUE
```

At this stage, you should be able to log in to the zimbra admin console as that limited admin user, but be able to do or see nothing useful. So give the group some views, the following is a general use case, preventing actual server config changes:
```
zmprov modifyDistributionList limitedadmins@domain.com zimbraAdminConsoleUIComponents accountListView zimbraAdminConsoleUIComponents DLListView zimbraAdminConsoleUIComponents aliasListView zimbraAdminConsoleUIComponents COSListView zimbraAdminConsoleUIComponents saveSearch
```

Here are some of the zimbraAdminConsoleUIComponents options, remember if you want to add more things later, you have to either use the + sign, or mention all of the old options and the new one in one line.
```
Account List View           :   accountListView
Distribution List View      :   DLListView
Alias List View             :   aliasListView
Resource List View          :   resourceListView
Class of Service LIst View  :   COSListView
Domain List View            :   domainListView
Server List View            :   serverListView
Zimlet List View            :   zimletListView
Admin Zimlet List View      :   adminZimletListView
Global Settings View        :   globalConfigView
Global Server Status View   :   globalServerStatusView
Help Search View            :   helpSearch
Saved Searches View         :   saveSearch
Mail Queue View             :   mailQueue
Backups  View               :   backupsView
Certificates View           :   certsView
Software Updates            :   softwareUpdatesView
Account Migration           :   bulkProvisionTasksView
Per Server Statistics View  :   perServerStatisticsView
Global ACL View             :   globalPermissionView
Right List View             :   rightListView
```


The views themselves just allow the widgets/UI to be visible, but with no data. For that, you'd need to give it some rights. It's actually easier granting it "domainRights", which is the usual array of creating accounts, deleteing, changing passwords, etc, and then removing any specific rights. For allowing access to all domains, just use:
```
zmprov grantRight global grp limitedadmins@domain.com +domainAdminRights
```

Or for specific domains, use :
```
zmprov grantRight domain mydomain.com limitedadmins@domain.com +domainAdminRights
```

You may want to add `+adminConsoleCOSRights` for changing the default COS if needed. 

Then get the list of rights with `zmprov getAllRights` and remove rights as required for specific groups or accounts. For example, to prevent the admin from changing the password for the user dude, you could type:
```
zmprov grantRight account dude@domain.com grp limitedadmins@domain.com -setAccountPassword
```

BTW: conviniently by default, the view mail option is disabled, and limited admins cannot change global admin's passwords (it would appear to, but give an error at the last moment).

If you need anything advanced or want to know about more options, read the zimbra [wiki](https://wiki.zimbra.com/wiki/UmaT-Implementing-Delegated-Administration).


### Using virtual/aliased IPs

If you use a virtual IP (eg. migration, or a Red Hat cluster), and you want outgoing emails to send via that IP (eg. if the NATing is such that you'd only get the correct public IP & thus reverse DNS record if it's from a particular IP), edit /opt/zimbra/conf/zmconfigd.cf, in the mta section, put this line before the line "RESTART mta":
```
POSTCONF smtp_bind_address                      1.2.3.4
```
where 1.2.3.4 is your virtual IP. You're not done yet. Edit /opt/zimbra/conf/amavisd.conf.in, and add this after @mynetworks:
```
@inet_acl = qw( 127.0.0.1 [::1] 1.2.3.4);
```
The last thing to do, to prevent Access denied errors, is edit /opt/zimbra/postfix/conf/master.cf.in, edit the section that starts with '[%%zimbraLocalBindAddress%%]:10025', and add the IP to the mynetwork list:
```
-o mynetworks=127.0.0.0/8,[::1]/128,1.2.3.4
```
then restart the MTA.


### Maintenance/tips

- If a user account is compromised, lock the account quickly with:
`zmprov ma joe@domain.com zimbraAccountStatus locked`
Change the "locked" to active to re-enable the user (after you change the password. Passwords can be changed with `zmprov sp account@domain.com newpassword`)

- A common request is to allow an IP to relay emails as any user or without a password. To do that, log in as zimbra (if this is multiserver setup, log into the MTA) and first get the current list:
`zmprov gs $(hostname) zimbraMtaMyNetworks`
then copy and paste the previous output starting after and not including "zimbraMtaMyNetworks: ", and then paste it like:
`zmprov ms $(hostname) zimbraMtaMyNetworks '127.0.0.0/8 1.2.3.0/24 ...'`
adding the IP to exclude in the end. DO NOT run zmmtactl! Just do a:
`postfix reload`

Somehow sometimes amavis stops working after this, so check it and start it if necessary:
`zmamavisdctl status`
`zmamavisdctl start`

- To restrict who can email a distribution list, make sure the milter service is enabled, and then: 
	- Allow a user dude@company.com to send to the DL everyone@company.com:  `zmprov grantRight dl everyone@company.com usr dude@company.com sendToDistList`  (grantRight can be shortened to grr)
	- Undo the above/remove the right: `zmprov revokeRight dl everyone@company.com usr dude@company.com sendToDistList` (revokeRight can be shortened to rvr)
	- Allow members of marketing@company.com DL to send to the DL everyone@company.com: `zmprov grr dl everyone@company.com grp marketing@company.com sendToDistList`
	- Allow everyone in the internal domain company.com to send to the DL everyone@company.com: `zmprov grr dl everyone@company.com dom company.com sendToDistList`
	- Allow everyone in an external non-zimbra domain microsoft.com to send to the DL everyone@company.com: `zmprov grr dl everyone@company.com edom microsoft.com sendToDistList`
	- Allow all internal zimbra users of any domain to send to the DL everyone@company.com: `zmprov grr dl everyone@company.com all sendToDistList`
	- Allow all non internal (=external/public) users to send to the DL everyone@company.com: `zmprov grr dl everyone@company.com pub sendToDistList`
	- Allow an external email billg@microsoft.com to send to the DL everyone@company.com: `zmprov grr dl everyone@company.com gst billg@microsoft.com sendToDistList`
	- Check if a user can send to a DL: `zmprov ckr dl everyone@company.com someuser@domain.com sendToDistList`
- You need to, strangely, restart the zmmilter service after making a change in the rights. Not sure if this is intended or a bug. 
- If you get a spam email complaint: 
	- Mark the email as spam, so that spamassassin is trained. There needs to be 200 spam messages and 200 ham messages tagged for the Bayesian filtering to activate. Find out how many you have with:
	`/opt/zimbra/libexec/sa-learn --dump magic | grep nspam\|nham`
	To mark messages has ham, forward emails _AS ATTACHMENTS_ to the ham account (and do the same for spam emails)
	- Analyze the headers to find out why it was not tagged as spam (the X-Spam headers), and what scores could be increased without affecting other email. Verify separately that Pyzor, Razor, DCC and antispam updates are working (if you have a restrictive outgoing firewall as outlined in the Firewall section above, refreshing the firewall to get new IPs often helps)
	- If the sender's IP resolves to a domain, and that domain looks dodgy, add it to /opt/zimbra/conf/postfix_blacklist in the format (with the leading dot to specify all subdomains) .thedomain.com  REJECT
	- If the BAYES_xx value always seems messed up (it should be close to 99 for spam, and close to 00 for ham), and you have autolearning enabled (=the default), consider clearing the entire bayesian filter, disabling auto training (see above) and re-training manually. To clear the database, run, as zimbra: `/opt/zimbra/zimbramon/bin/sa-learn --dbpath /opt/zimbra/data/amavisd/.spamassassin  --backup > /tmp/bayesian-backup.201xxxx`

-  If you use domain aliases, Zimbra does not check the RCPT TO addresses for aliased domains. The docs has incorrect instructions for enabling this (see my bug [#98941](https://bugzilla.zimbra.com/show_bug.cgi?id=98941)), so instead use:
```
zmprov mcf zimbraMtaEnableSmtpdPolicyd TRUE
zmprov mcf +zimbraMtaRestriction "check_policy_service unix:private/policy"
```

- If you are having issues with Zimbra and you suspect it's because of the proxy (it happened once with slow clients with spotty internet connections), you can try ruling it out by accessing the web client directly on port 8080 or 8443, and the POP3/IMAP port directly on port 7110 and 7143. If it turns out it was indeed a problem with the proxy, try increasing the nginix timeouts, or just bypass the proxy either by disabling it, or as a temporary workaround until you have proper downtime, using iptables to redirect the ports.



