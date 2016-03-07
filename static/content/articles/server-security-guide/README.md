* Follow the standard installation guidelines for [RHEL6](/articles/el6-standard-installation/) or [RHEL7](/articles/el7-standard-installation/), but have a separate /tmp at least.

* If this is a virtual machine, and you made it from a template, be sure you re-generate the SSH host keys (run rm -vf /etc/ssh/ssh_host_* and restart SSH), and make sure none of the users have any "authorized_keys" files lying around in their .ssh directories. Ideally your templates shouldn't have this in the first place, but it's best to double check, esp. if you are using some [cloud providers](http://www.theregister.co.uk/2016/02/09/linode_ssh_security/). 

* Set `PermitRootLogin` to `no`, and set `AllowUsers` in sshd_config to the users who should log in. Each admin should have their own account of course, for accountability.

* Enable SELinux unless it's flat-out not supported by your application. Note that if this is an Apache web server, and you aren't using GFS2, you really really should have SELinux enabled;

* Disable all unnecessary services. Your `netstat -lptun` output should only have things listening on 0.0.0.0/::: that needs to.

* Depending on the server, you might have been given an IPv6 address. If you don't need it, don't ignore it completely; I've seen too many non-enterprise servers, esp. VPSs, that have iptables set up for IPv4, but leave IPv6 wide open. The iptables6 service should be running and shouldn't allow all SSH connections, or better yet, use FireHOL and consolidate your IPv4 and IPv6 rules into a single ruleset.

* In your iptables firewall, don't focus on incoming connections, but limit outgoing connections too as much as possible. You might be thinking that would make updates difficult, but it wouldn't; just allow all outgoing connections for the root user (as if you're root, you can flush the firewall anyway).  I recommend you install [FireHOL](/articles/easy-secure-firewalls-with-firehol/) to make firewall management much easier.

* Make sure that your services that do not need external access at all listen to 127.0.0.1, so that even if the firewall is accidentally kept disabled, people can't connect to it. Eg. in apache, use "Listen 127.0.0.1:80", and in mysql use "bind-address = localhost"

* Make sure you have [command logging](/articles/command-logging/) enabled.

* Ensure you have a good backup strategy, and, as importantly, a recovery strategy.

* You need to have some sort of a host based Intrusion Detection System (HIDS) to monitor your static files and binaries. If your server's been hacked, don't expect your website's front page to have a black background with a flag GIF; most hacks are more subtle and can remain undetected for months or even years, unless you have a system of monitoring whether your files have been modified or whether there are unusual log messages.
If you have a lot of time, I recommend [Samhain](http://la-samhna.de/samhain/) which has inotify support for immediate detection of changes, a system of emailing you log messages that you define as not usual, and is one of the more secure IDSs I've seen. But it's quite complex to set up (though I hope an upcoming article would make it clearer), so you might want to instead use things like Tripwire and others. 

* In the same vein, a monitoring system is crucial as well; and do review the graphs and reports as well to detect anomalies (some commercial tools can do this automatically I believe). Unusual outgoing network spikes to a few external IPs for example could be a sign of something taking a DB dump (no toilet humor intended). 

* Make sure all files in /etc/cron.d are only writable by root. Use cron/at allow/deny files as needed to prevent users like apache from setting cron/at jobs.

* If you have a dynamic web site or web application, a WAF is much much more important than an standard firewall; moreso if your web apps are custom written by your devs, as that can help with detecting SQL injection attacks, XSS, etc. [mod_security](https://www.modsecurity.org/) is a good software WAF (though it requires a lot of tweaking), but there are many vendors dealing with WAF appliances that may be easier, but everything requires monitoring and tweaking.
(if you have any custom code written by devs, make sure they are familiar with secure coding practices to prevent this possibility in the first place)

* It should go without telling, but if you know your server's software would have a limited audience, limit the IPs that can access it (like VPN users only, or those from a certain network, or even country)

* You could use something like [fail2ban](http://www.fail2ban.org/) for admin services, but I would give a second thought about using it for user services unless security trumps availability; as I've seen entire offices blocked out from IMAP because one of the users forgot their password; and the dynamic IPs in branch offices makes whitelisting difficult without mentioning the entire country IP block.


### Apache/LAMP security

* It is very important to disable viewing Indexes; this is enabled by default and should be disabled. Also symLinksIfOwnerMatch is [safer](https://krystal.info/index.php?/News/NewsItem/View/9/security-measure-symlinks) than FollowSymLinks. Edit **/etc/httpd/conf/httpd.conf**, and change:
`Options Indexes FollowSymLinks`
to:
`Options SymLinksIfOwnerMatch`


* Create a file in **/etc/php.d/**, say custom_security.ini, to prevent the use of dangerous functions. If the PHP code is unknown/custom written, you may need to grep out the code for each of the following and exclude any functions that are actively being used. An example for Joomla is:
`disable_functions = show_source, system, shell_exec, passthru, exec, phpinfo, popen, proc_open`
Also, unless there is a lot of custom code that may need it, disable remote URL object loading:
`allow_url_fopen = 0`
`allow_url_include = 0 `
You can also hide the PHP version number:
`expose_php=Off`


* It is also important to limit which directories PHP can access, set that with php.ini:
open_basedir = /var/www/html/:/tmp/:/usr/bin/
However, if you use open_basedir, you cannot benefit from PHP's realpath cache, but it might be worth it for the security benefits.

* It is critical that the permissions are set properly. It's best to have a script set the permission rather than doing it by hand. PHP execution should be disabled on those directories as well. A script can be something like this, name it say permissions-execute.sh, and then create more scripts that `source`s it like the comment in the script below says:

```bash
#!/bin/bash

# This script should be included at the end of
# a script that has something like these contents:
#
#	#!/bin/bash
#	NAME="piwigo"
#	ROOT_DIR="/var/www/html/rizvir.com/photos"
#	RW_DIR=("/var/www/html/rizvir.com/photos/_data") # BASH array
#	source $(dirname $0)/permissions-execute.sh

set -e
set -u

APACHE_USER="apache"
APACHE_GROUP="apache"

HTTPD_CONFIG="/etc/httpd/conf.d/disable-php-$NAME.conf"

if [ -z "$ROOT_DIR" ]; then
        echo "ROOT_DIR needs to be set"
        exit 1
fi

# First set the default permission (440, root:apache)

chown -R root:apache $ROOT_DIR
chmod -R 440 $ROOT_DIR
find $ROOT_DIR -type d -exec chmod 750 {} \;
 
# clear the existing configuration
rm -f $HTTPD_CONFIG

# Then go to each R/W directory and set the permissions
for rwdir in "${RW_DIR[@]}"; do
        chown -v -R $APACHE_USER:$APACHE_GROUP "$rwdir"
        chmod -v -R 664 "$rwdir"
        find "$rwdir" -type d -exec chmod -v 775 {} \;

        # Also disable php execution
        echo "<Directory \"$rwdir\">" >> $HTTPD_CONFIG
        echo "    php_admin_flag engine off" >> $HTTPD_CONFIG
        echo "</Directory>" >> $HTTPD_CONFIG
done

/etc/init.d/httpd reload
echo "All done"
```

* Add a '.disabled' extension to any plugins you don' tneed in /etc/httpd/conf.d

* Consider setting up mod_security if you don't have an external web application filter, but be warned it's a lot, a lot, of work.

* If you're using MySQL, change the shell of the mysql user to /sbin/nologin instead of /bin/bash

* In your PHP app, if possible, rename the admin panel to something that is not the default. In any case, limit the IPs that can access the admin panel (if you have a dynamic IP, consider only allowing 127.0.0.1 and using SSH port forwarding). If you have many sites, one maintainable way of doing this is creating a file like **/etc/httpd/conf.d/allowed-admin-IPs**:
`order deny,allow`
`allow from 127.0.0.1`
`allow from 192.168.67.0/24`
...
Then create an apache config file like (which depends on your application, in this example admin.php handles the admin panel):
```
<Directory "/var/www/html/rizvir.com/photos">
	<Files "admin.php">
		Include /etc/httpd/conf.d/admin-ip-addresses
	</Files>
	...
</Directory>
```

* I prefer having `AllowOverride None` (for security and performance reasons), but you might inadvertently reduce your security (or functionality) unless you take the time to move the .htaccess rules that your app or devs put into a /etc/httpd/conf.d/something.conf file. So do a `find` for .htacces, and then move the contents to /etc/httpd/conf.d/sitename-htaccess.conf instead like:
```
<Directory "/var/www/html/mysite.domain.com">
    # paste contents of /var/www/html/mysite.domain.com/.htaccess
</Directory>
<Directory "/var/www/html/mysite.domain.com/logs">
    # paste contents of /var/www/html/mysite.domain.com/logs/.htaccess
</Directory>
...
```

* If you write code, I've always thought it'd be nice if you had MySQL users more like a Linux users, with lots of them per site rather than the single master one most CMSs seem to have, with each user having limited read-only or write-only access to whatever tables they need, so if a web script has a vulnerability, it could do limited damage. Why is this such a rare thing though?

* This isn't necessarily related to security, but it's nice to have a live view of colored logs, esp. if you use mod_security. So `yum install multitail` (EPEL), and append the following to /etc/multitail.conf :
```
colorscheme:apachemod:Apache enchanced logging
cs_re:red:.*404.*
cs_re:blue|blue,,bold:^... .. ..:..:..
cs_re_s:green:GET (.*) HTTP.* 200
cs_re_s:yellow:GET (.*) HTTP.* 304
cs_re_s:red:GET (.*) HTTP.* 404
cs_re_s:magenta:("POST .*)
cs_re_s:red,,bold:(.*) HTTP.* 403
cs_re_s:yellow,,bold:access_(.*):
cs_re_s:yellow,,bold:error_(.*): \[
cs_re_s:red,,bold: (error_.*)
```

You can then monitor log files with `multitail -cS apachemod /path/to/file`. If you have a lot of files, you can have a script:
```bash
#!/bin/bash

SITES="www.site.com login.site.com something.com"
MULTITAIL_ARGS="-cS apachemod"
LOG_ROOT="/var/log/httpd"
ARGS=""

for site in $SITES; do
        ARGS="$ARGS $MULTITAIL_ARGS -I $LOG_ROOT/$site/access_log"
done

multitail $MULTITAIL_ARGS $ARGS
```


### Remote logging

You should have a remote logging server. Remember, your logs on your main servers are useless if it's been compromised; so it helps having a lightweight machine running nothing but logging services which is less likely to be cracked as well. If you are short of servers, at least use your standby or backup server. To do that, uncomment these lines in /etc/rsyslog.conf:
```
$ModLoad imudp
$UDPServerRun 514
```

If you've done by standard install, append this to the **/etc/rsyslog.d/disable_ratelimit.conf** file:
```
$SystemLogRateLimitInterval 0
$SystemLogRateLimitBurst 0
$IMUxSockRateLimitBurst 0
$IMUXSockRateLimitInterval 0
$IMUxSockRateLimitSeverity 7
```

and add `-x` to the `SYSLOG_OPTIONS` in **/etc/sysconfig/rsyslog** to disable reverse DNS lookups which really slows things down.

That's it on the server side for the very basics, but all client logs goes into the log serers's /var/log/messages which is silly, so you should start writing filters to separate things. For example, you could add:
`+your-rsyslog-hostname-without-domain`
just after Include (after the "RULES" comment). Then you can add files called something like /etc/rsyslog.d/somehost.somewhere.com.conf (make sure that the first line is NOT the FQDN) :
```
+YourClientHostnameWithoutDomain
:msg, contains, "firehol"                               -/var/log/somehost.test.local/firewall.log
& ~
*.info;mail.none;authpriv.none;cron.none,local5.none    -/var/log/somehost.test.local/messages
authpriv.*                                              -/var/log/somehost.test.local/secure
mail.*                                                  -/var/log/somehost.test.local/maillog
cron.*                                                  -/var/log/somehost.test.local/cron
uucp,news.crit                                          -/var/log/somehost.test.local/spooler
local7.*                                                -/var/log/somehost.test.local/boot.log
local6.*                                                -/var/log/somehost.test.local/command.log
# etc

& ~
```

Alternatively, you can also use the rsyslog conditional syntax, but that syntax is much better if you have rsyslog7 (available from the red hat repo as "rsyslog7") as rsyslog7 supports braces {} and rsyslog 5 does not, so you can only have simple rules like:
`if $fromhost-ip == '192.168.1.2' and $msg contains 'TR' then -/var/log/something.log`

Now on the clients, create a file called **/etc/rsyslog.d/00-remote_logging.conf** with the following contents (replace 1.2.3.4 with the syslog IP):
```
*.* @1.2.3.4:514
```

That's it.

audit logs do not go through rsyslog though, and if you want to stream audit logs to a remote host as well, you have two options. One is simply passing auditd messages to syslog, which you can easily do by editing **/etc/audisp/plugins.d/syslog.conf** and changing `enable = no` to `enable = yes`. 
The other option is to enable native logging, which has the advantage of allowing you to use the many included audit log parsing and reporting tools. However, I wasn't able to figure out how to encrypt the connection, so logs would go via plain text (whereas in the first option you can enable TLS for rsyslog to avoid plain text). For native logging, edit **/etc/audit/auditd.conf** and uncomment `#tcp_listen_port =` to make it `tcp_listen_port = 60`. Restart auditd, and allow port tcp/60 in your firewall. On your clients, edit `/etc/audisp/plugins.d/au-remote.conf` and set `active=yes`, and edit `/etc/audisp/audisp-remote.conf` to specify the location of the server, and restart auditd. That's it.

Logs will be going between your servers in plain text. If your logs contain sensitive information, enable encrypted connections between the log server and clients with rsyslog's TLS functionality. You can read up on `/usr/share/doc/rsyslog-*/rsyslog_tls.html`, or get a self-signed setup done quickly with:
```bash
cd /etc/pki/rsyslog/ # doesn't matter where really, even for SELinux it seems
certtool --generate-privkey --outfile ca-key.pem
certtool --generate-self-signed --load-privkey ca-key.pem --outfile ca.pem
# Answer the questions;  the cert belongs to a cert authority used to sign other certs. 
```

scp the ca.pem file the same location on the client. Then type:
```
certtool --generate-privkey --outfile key.pem
certtool --generate-request --load-privkey key.pem --outfile request.pem
certtool --generate-certificate --load-request request.pem --outfile cert.pem  --load-ca-certificate ca.pem --load-ca-privkey ca-key.pem
# cert does not belong to an authority, it is a TLS web and client cert, DNS name must  be the server name (press enter again)
```

Then add this to **/etc/rsyslog.d/tls.conf**:
```
# make gtls driver the default                                                    
$DefaultNetstreamDriver gtls                                                      
																			   
# certificate files                                                               
$DefaultNetstreamDriverCAFile /etc/pki/rsyslog/ca.pem                      
$DefaultNetstreamDriverCertFile /etc/pki/rsyslog/cert.pem                  
$DefaultNetstreamDriverKeyFile /etc/pki/rsyslog/key.pem                    
																			   
$ModLoad imtcp # load TCP listener                                                
																			   
$InputTCPServerStreamDriverMode 1 # run driver in TLS-only mode                   
$InputTCPServerStreamDriverAuthMode anon # client is NOT authenticated            
$InputTCPServerRun 6514 # start up listener at port 6514 
```

The last port number is 10514 in the rsyslog HTML doc, change it to 6514, as that is allowed by SELinux with RHEL, but if you want a different port, use `semanage port -a -t syslogd_port_t -p tcp 1234` to allow it. Also don't forget to add the port to iptables.

Finally on the clients, assuming you copied over the ca.pem file, add this to their **/etc/rsyslog.d/remote_logs.conf**
```
# certificate files - just CA for a client                                     
$DefaultNetstreamDriverCAFile /etc/pki/rsyslog/ca.pem                   
                                                                               
# set up the action                                                            
$DefaultNetstreamDriver gtls # use gtls netstream driver                       
$ActionSendStreamDriverMode 1 # require TLS for the connection                 
$ActionSendStreamDriverAuthMode anon # server is NOT authenticated             
*.* @@(o)logs.rizvir.com:6514 # send (all) messages 
```

That's it if your only worry is plain text logs, but ideally you should read more into encrypted logging with rsyslog, in particular authenticating the server and clients, so that the server doesn't get messages from just any client, and the client doesn't send it's logs to just any server. It supports x509 certs for this.


### Remote Apache logging

You can stream your Apache logs to syslog, so that they can be kept on a dedicated log server. I'm not sure if this is the best way to do it, in that calling "logger" would sound like it would have performance issues but it doesn't seem to in practice according to my benchmarks, but do your own research.

So instead of say:
```
        ErrorLog /var/log/httpd/error.log
        CustomLog /var/log/httpd/access.log combined
```
in each virtual host, you can have:
```
        ErrorLog "|/usr/bin/logger -t error_www.site.com -p local5.info"
        CustomLog "|/usr/bin/logger -t access_www.site.com -p local5.info" combined
```

and then create a file called /etc/rsyslog.d/apache.conf with something like:
```
   # www.site.com
   :syslogtag, isequal, "error_www.site.com:"        -/var/log/httpd/www.site.com/error_log
   & ~
   :syslogtag, isequal, "access_www.site.com:"        -/var/log/httpd/www.site.com/access_log
   & ~

   # ... add more hosts as required in the same way
```


*[WAF]: Web Application Filter
