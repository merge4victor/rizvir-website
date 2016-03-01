[Firehol](https://firehol.org/) is a BASH script that makes it easy to handle iptables, and doesn't seem to have any bugs that I have seen. It makes it easy to have a restrictive outgoing firewall, something I feel is not given enough importance by most people because of the difficulty of doing so. A restrictive outgoing firewall helps in preventing your machines from downloading a payload from the internet, esp. common with PHP compromises. 

This isn't a quick easy tutorial; you will find plenty of those in the [official site](https://firehol.org/tutorial/) and elsewhere. This talks about a production install with some tips for certain situations.

### Installation

Install FireHOL by enabling [EPEL](https://fedoraproject.org/wiki/EPEL) and doing a `yum install firehol`. You may want to stop and disable firewalld (el7).

The configuration file is kept in /etc/firehol/firehol.conf. You can add firehol to the startup by using `chkconfig firehol on` in EL6, or `systemctl enable firehol.service` in EL7 <del>,  but that's not recommended IF you use hostnames (not in /etc/hosts) in the firehol config instead of IP addresses; as firehol would slow down at boot & revert to the old firewall if the DNS is inaccessible. Thus, you may want to set the default firewall (/etc/sysconfig/iptables) to only allow SSH, make sure firehol does not start at boot (chkconfig firehol off), and instead add it to /etc/rc.local like "service firehol start &".</del> If you need to use hostnames, use the "allow_domain" function below, so if the DNS is inaccessible, firehol would just time out and continue with the rest of the rules rather than fail and revert to your boot iptables rules (which is probably allow everything).

The basics are really simple, this is an example for only allowing pings and HTTP/HTTPS from anywhere, a custom port tcp/6543, custom udp ports from 1200 to 1230, SSH from some IPs, and restrict outgoing connections but still allow yum updates by root:
```bash
# Firewall config
version 5

ALLOWED_SSH_IPS="192.168.1.0/24 1.2.3.4"
DNS_SERVERS="192.168.1.1 8.8.8.8"

# Redirect port 1234 to 1111
redirect to 1111 inface eth0 proto tcp dport 1234

interface eth0 wan
	# Incoming:
	server ssh accept src "$ALLOWED_SSH_IPS"
	server "http https" accept
	server ping accept
	server custom yourAppNameOrAnything tcp/6543 default accept
	server custom anotherExample udp/1200:1230 default accept src "192.168.67.2 192.168.6.5"

	# Outgoing:
	client ping accept
	client dns accept dst "$DNS_SERVERS"
	# Allow root to access anything:
	client all accept user "root"
	
	# No other outgoing connections are allowed if they aren't mentioned. 
	# To allow all outgoing connections, use:
	# client all accept


```

Get a list of services that firehol understand from [here](https://firehol.org/services/).	

If you only need to worry about IPv4, you can use "version 5". Otherwise, if you want IPv6 support, use "version 6" and [read this](https://firehol.org/tutorial/firehol-ipv6/).

Remember to use `/etc/init.d/firehol try` (EL6) or `firehol try` (EL7) to apply the firewall rules, which will preview the rules for 30 seconds while asking you to type "commit".

Also note that the firehol.conf file is actually a BASH file, so you can have BASH loops, arrays, functions, etc. You can use `source` to include variables from other files. 

If there is something you want to do with iptables that isn't viable with the firehol syntax, simple type the iptables command (starting with `iptables -I INPUT...`) at the end of the file (don't prepend /usr/sbin or anything, because in this context iptables is a firehol function)

(a random thought: if preventing all possible outgoing communications to the outside world is important to you, don't even allow DNS as, in theory, even if you use your own private DNS servers, your compromised servers could upload your data to a hacker on the internet by encoding your data in say base64 and doing special lookups which would eventually reach the attacker's nameservers. I have never seen or heard such a thing, but it occured to me while writing the `client dns accept dst $DNS_SERVERS` rule)

This is another example for a setup that is a transparent squid proxy server and gateway:
```bash
version 5
FIREHOL_LOG_PREFIX="firehol: "

...
whole_network="10.40.0.0/16"
it_admin_ips="1.2.3.4 2.3.4.5"
redirect to 3128 inface eth0 src "$whole_network" proto tcp dport 80

interface eth0 lan
	server ssh accept src "$it_admin_ips"
	server ping accept
	client all accept

interface eth1 internet
	protection strong
	client all accept

router lan2internet inface eth0 outface eth1
	masquerade
	route imap accept
	route pop3 accept
	route smtp accept
	route all accept src "$it_admin_ips"
```

### Configuring logging

Firehol will log anything that is not matched by the configuration file. This is useful when finding out if something is being unnecessarily blocked. However, this often fills /var/log/messages with logs of packets, so you can create a separate line for this using rsyslog, by creating a file named **/etc/rsyslog.d/firehol.conf** :
```
:msg, startswith, "firehol: " -/var/log/firewall.log
& ~
```

And restart rsyslog. For messages to start with "firehol:"; make sure you have:
```
FIREHOL_LOG_PREFIX="firehol: "
```
in your **/etc/firehol/firehol.conf** config. This firewall.log file will quickly turn large with random blocked traffic; so you will want to create a **/etc/logrotate.d/firewall** file:
```
/var/log/firewall.log
{
    sharedscripts
    compress
    postrotate
        /bin/kill -HUP `cat /var/run/syslogd.pid 2> /dev/null` 2> /dev/null || true
    endscript
}
```

After you configure firehol with the rules you want and apply (=`firehol try`) them, watch the firewall.log file. You'll may notice a lot of broadcast packets being blocked, created by DHCP servers or SMB services. You can optionally reduce the noise in the log by blocking them in the firehol configuration explictly. Anything that is explicitly blocked in firehol.conf would not have a log displayed:
```
# Drop these explicitly as we get lots of logs
server netbios_dgm drop
server netbios_ns drop
# If you have a static IP and not a DHCP one:
server dhcp drop
server custom udp68 udp/68 any drop
server custom udp69 udp/69 any drop
# etc
```

### Using hostnames instead of IPs

By default, using hostnames may look as though it works, but cause firehol to hang at startup for a long time if it cannot reach your DNS server before reverting to your earlier ruleset (which might be allow everything). In addition, it only takes one IP address even if multiple A records are associated with that hostname.

So, after making sure you have `dig` installed (`yum install bind-utils`), you can include this function after `version` and your variables, but before the `interface` line: 

```bash
# usage example:
# allow_domain 'domainname.com another.domain.com' 'client http accept dst'
function allow_domain() {
        local domains="$1"
        local firehol_line="$2"

        for domain in ${domains}; do
                while read ip; do
                        if echo $ip | grep -Eq '^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$'; then
                                $firehol_line "$ip"
                        fi
                done < <(dig ${domain} +short +tries=1 +time=3)
        done
}
```

Then under the interface lines, along with your 'server ssh accept' lines, add things like:

```
allow_domain 'db.us.clamav.net' 'client http accept dst'
allow_domain 'nagios.rizvir.com' 'client custom tcp/3667 default accept"
```
Of course, like iptables, this will only translate the hostname to an IP at startup, so if the hostname's IP changes, you will have to reload firehol for it to know. So this isn't ideal for hostnames that would change often.


### Allowing or blocking countries

You might be tempted to just go through an online country IP list, convert it into a variable and do a "server accept ssh src "$COUNTRY" or something, but you may quickly discover that your firewall rule take more than 10 minutes to apply. iptables is just not efficient with a long list of IP networks. Use ipsets instead, it'd make the same thing apply almost instantly. 

So after a `yum install ipset`, include something this function after `version`, but before the `interface` line:

```bash
ipv4 ipset create countries hash:net
COUNTRIES="ae au"
IPSET_SRC_DST_OPTIONS=
for country in $COUNTRIES; do
        #url="http://www.ipdeny.com/ipblocks/data/aggregated/${country}-aggregated.zone" #site down?
        url="http://ipverse.net/ipblocks/data/countries/${country}.zone"
        country_ips=$(curl -s $url)
        if [ $? != 0 ]; then
                echo "Error downloading country IP list from $url"
                server countrylist deny # force firehol to error out
        fi
        # Make sure that the entry is an IP, or error out
        while read ip; do
                if [[ "$ip" =~ ^#.* ]]; then
                        continue
                fi
                if ! [[ "$ip" =~ ^[0-9].*\/.* ]]; then
                        echo "Country zone had a line with no network address: $ip"
                        server countrylist deny # force firehol to error out
                else
                        ipv4 ipset add countries "$ip"
                fi
        done <<< "$country_ips"
done
```

Then under your interface lines, reference those countries with something like:
```
        server imap accept src ipset:countries
```




### Setting the activation policy

Firehol by default temporarily allows all connections momentarily while the firewall is being reloaded or activated, possibly to not disrupt your SSH session, or to allow DNS lookups. You may want to change this so that it drops all connections while activating:
```
FIREHOL_INPUT_ACTIVATION_POLICY="DROP"
FIREHOL_OUTPUT_ACTIVATION_POLICY="DROP"
FIREHOL_FORWARD_ACTIVATION_POLICY="DROP"
```

There are other useful variables you can read about [here](https://firehol.org/firehol-manual/firehol-variables/).










