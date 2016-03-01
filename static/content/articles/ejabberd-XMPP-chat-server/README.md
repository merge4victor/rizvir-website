### Intro

There are loads of XMPP servers available; however if you're installing it on a server that has other things running on it like Zimbra, you'd want something light. Openfire is good, but is java based and takes up a lot of RAM. jabberd2 is in the EPEL repo, but does not support majority of the XMPP extensions. Prosody is the first thing that people suggest when it comes to lightweight yet good XMPP servers, but it's written in an obscure language, Lua, and as of writing (April 2015) does not support EL7 without compiling dozens of Lua dependencies from scratch. ejabberd is also written in an unfamiliar language, but has an installer that consolidates everything into /opt, making it unobtrusive, and making it not depend on anything outside the norm.


### Installation
First, pre-create the directory:
```
mkdir /opt/ejabberd
```

Then create the user:
```
useradd --system --shell /bin/bash --home-dir /opt/ejabberd ejabberd
```

And set the permissions:
```
chown -R ejabberd:ejabberd /opt/ejabberd
```
 
Copy the installer to /tmp, and make it owned by ejabberd, and run it as ejabberd:
```
cp /root/apps/ejabberd*.run /tmp/
chown ejabberd:ejabberd /tmp/ejabberd*.run
chmod +x /tmp/ejabberd*.run
su - ejabberd
cd /tmp
./ejabberd*.run
```
When it asks, install it on /opt/ejabberd . Also, set the domain properly, you probably would not want to have the FQDN, but rather the domain that would appear after user@...  .
 
For convinience, you may want to have the ejabber binaries in you ejabber user's $PATH:

```
su - ejabberd
echo 'PATH="$PATH:/opt/ejabberd/bin"' >> /opt/ejabberd/.bash_profile
``` 

If this is EL7, copy the systemd unit file:
 
```
cp /opt/ejabberd/bin/ejabberd.service /etc/systemd/system/
systemctl enable ejabberd.service
systemctl start ejabberd.service
```
 
If it's EL6, you put `/opt/ejabberd/bin/ejabberd.init` in `/etc/init.d/` and do a `chkconfig --add ejabberd && chkconfig ejabberd on`
 
### Certificate
If you're using a self signed certifcate, the one in the installer would not work properly (eg. pidgin would refuse to accept it), so create a new one:
 
```
cd /opt/ejabberd/conf
openssl req -new -x509 -newkey rsa:1024 -days 3650 -keyout privkey.pem -out server.pem
openssl rsa -in privkey.pem -out privkey.pem
cat privkey.pem >> server.pem
rm privkey.pem
```
 
If you're using zimbra, see the Zimbra integration notes below about using Zimbra's certificate (useful if you purchased a certificate for Zimbra)


### Configuration
To add users, you can use the (very sparse) web interface at http://yourip:5280/admin as admin@yourdomain.com, and then go to virtual hosts, or use the command line:
```
ejabberdctl register rizvi rizvir.com thepassword
```
For anything else, the configuration is kept in /opt/ejabberd/conf/ejabberd.yml. There are some things that you may want to change:
```
# ejabberd is mainly used for huge million public user installs, but in our case we have limited trusted users, so there's no need to traffic shape:
shaper:
  normal: 1000 -> 1000000

# With spotty connections (esp. in mobiles), one user may appear to have multiple sessions, so it's best to increase the value:
acl:
  max_user_sessions:
     all: 10   -> 100

# This is to prevent public registrations, but even if you don't put this, it should be fine in theory because the default configuration only allows registrations on the local network anyway"
  register:
    all: allow -> deny
```

If you want to mandate the use of encrypted connections, add this to the listen stanza:
```hl_lines="4 4"
listen:
  - ...
  starttls: true
  starttls_required: true
```

Next you need to decide the authentication scheme. If you're using the internal authentication scheme, you should know that by default, it keeps the passwords in plain text. To keep the passwords encrypted, uncomment the `"auth_password_format: scram"` line. If you plan to use LDAP, see Zimbra integration below to get an idea about how it can work.
 
You may also want to enable allow NAT traversals for file transfers:

``` 
  mod_proxy65:
    ip: "1.2.3.4"  ## The _external_ IP of the server, also open port 7777 in your firewall.
    auth_type: "plain"
``` 
 
### Zimbra integration
You'd probably want to use Zimbra's certificates, esp. if it's commercial:

```
mkdir -p /root/temp/cert
cd /root/temp/cert
cp /opt/zimbra/ssl/zimbra/commercial/commercial.key ./
cp /root/apps/certs/* ./ # GoDaddy or whatever certs
openssl rsa -in commercial.key -out commercial.key
cat abcdeba62ab71234.crt gd_bundle-g2-g1.crt commercial.key > server.pem
cp server.pem /opt/ejabberd/conf/
chmod 400 /opt/ejabberd/conf/server.pem
chown ejabberd:ejabberd /opt/ejabberd/conf/server.pem
systemctl stop ejabberd
systemctl start ejabberd
``` 


You can authenticate with Zimbra's LDAP server to keep the user name and passwords the same. Create a user in Zimbra called say ejabberd, with a random password. Verify that you can log in using ldapsearch. If you're really not sure of the DN, temporarily log in as the admin to see it:
```
ldapsearch -LLL -x -h zimbra.server -D 'uid=zimbra,cn=admins,cn=zimbra' -W '(mail=ejabberd@*)'  # password via zmlocalconfig -s zimbra_ldap_password
```

Then verify that you can do an ldap search with the ejabberd account in zimbra:

```
ldapsearch -LLL -x -h 10.113.5.85 -D 'uid=ejabberd,ou=people,dc=rizvir,dc=com' -w 'yourPass' '(mail=someRandomAccountToCheck@rizvir.com)'
```

Edit the configuration:

Comment out `auth_method: internal`
Underneath it, add:

```
auth_method: ldap
ldap_servers:
  - "1.2.3.4"
ldap_encrypt: none
ldap_port: 389
ldap_rootdn: "uid=ejabberd,ou=people,dc=rizvir,dc=com"
ldap_password: "yourPass"
ldap_base: "dc=rizvir,dc=com"
ldap_uids:
  - "mail": "%u@rizvir.com"
ldap_filter: "(objectClass=zimbraAccount)"
``` 
 
Stop and start ejabberd, and try out the authentication. If it doesn't work, check out the ejabberd logs (/opt/ejabberd/logs/) or see the ldap search commands on zimbra via tcpdump.
 
You may also want to use the shared roster feature, which allows you to pre-populate the user's buddy list with users taken from LDAP. Unfortanately, there's no easy way to do it because you can simple add people who'se objectClass=zimbraAccount, because there'd be plenty of system users (eg. ham, spam, nagios) that would not look good on everyones buddy list. In addition, neither I, nor people online it seems, could find a way to have a distribution list where you can have the chat users. However, I came up with something a bit hacky but can work fairly well at the expense of some manual (but GUI) work when adding a zimbra user.
The shared roster can be divided neatly into groups, eg. IT, Accounting, etc, with some clients like Pidgin allowing you to collapse groups you are not interested in. So put in the chat group of the user in the user's "Pager" section in their zimbra config, as that is unlikely to be actually used. If you don't need/have groups, just put in say the companies name. So now, only people who has a string in their Pager section would appear in their buddy list.
The config you need to add in ejabberd is, just  below mod_shared_roster:
``` 
  mod_shared_roster_ldap:
        ldap_base: "dc=rizvir,dc=com"
        ldap_rfilter: "(objectClass=zimbraAccount)"
        ldap_groupattr: "pager"
        ldap_memberattr: "uid"
        ldap_filter: "(objectClass=zimbraAccount)"
        ldap_userdesc: "displayName"
``` 
 
 
### Security
If you don't need server-to-server connections, do a "server jabber accept" in firehol (port 5222), otherwise if you plan to use s2s use "server jabberd accept" (port 5222 + 5269).
 
Set up restrictive file permissions, esp. useful if the server has other daemons:

```
chown -R root:ejabberd /opt/ejabberd/
chmod -R 440 /opt/ejabberd/
find /opt/ejabberd/ -type d -exec chmod 750 {} \;
chown -R ejabberd:ejabberd /opt/ejabberd/{database,logs,.erlang.cookie}
chmod -R 600 /opt/ejabberd/{database,logs,.erlang.cookie}
find /opt/ejabberd/{database,logs} -type d -exec chmod 770 {} \;
chmod -R 550 /opt/ejabberd/bin/
chown ejabberd:ejabberd /opt/ejabberd/
``` 

