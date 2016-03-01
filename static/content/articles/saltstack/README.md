[SaltStack](http://saltstack.com/community/) is a Python based configuration and execution management application written in Python. It competes with the likes of Puppet and Ansible.

The advantages Salt has over Puppet is that it supports running and checking the output of arbitrary commands (not possible without a lot of hoops/hacks in Puppet), easier to get started with, easier for me to write modules for (python instead of Ruby), has fewer dependencies, and allows instant changes to all servers, vs. waiting for 30 or whatever minutes in Puppet, and has an option for agent-less clients (via salt-ssh). Salt also as a top-down order (that can be overriden with dependencies), whereas Puppet  always goes in a random order unless you specify dependencies; the lack of a top-down approach makes setting dependencies mandatory in Puppet, and optional with Ansible (where you can set failhard: True on a block to make it stop if something fails)

The advantage over Ansible is in one key aspect if you are not using it on a LAN-only environment, Ansible is primarily a server -> client design, which for me isn't something I like for many setups, as a lot of my servers are inaccessible _from_ the internet, but can have outgoing connections _to_ the internet. Ansible-pull is a workaround for that, but is just a cron job on the client, making it difficult for it to get the output of commands executed, or run something instantaneously. Salt is a client -> server thing, which would work well for the sort of people who do not like having all their machines accessible from the internet the via SSH. 

Some disadvantages of Salt is that it's not yet as ubiquitous as Puppet, and it's web interface is in the Enterprise edition only (though with Red Hat's Foreman, you can have a rudimentary GUI. The fact that Foreman supports Salt in newer versions suggests it may be supported by Satellite 6 in the future too). However I personally don't see how a GUI would be useful since most of the work has to be done over the command line anyway, so it'd be a pain switching back and forth between the browser GUI and the command line.

Having a configuration management setup like Salt or Puppet is a huge security risk. If someone takes over your Salt server, they have root over all your servers. Not fun. So you need to take great care about securing the server you'd be keeping Salt in. Some suggestions include:

* Keeping Salt and your OS updated constantly
* Host it in your infrastructure if possible; using public instances/VPSs/containers is a bit riskier (the risk being one of the many people sharing the physical server you happen to end up in finds a way to launch a hypervisor or container host attack)
* Have Salt listen to non-standard ports (won't help in targetted attacks)
* Use password-protected keys for SSH only, and limit direct logins over the internet if possible, preferring a bastion host
* No other ports should be opened at all except for Salt and possibly SSH
* Have your firewall run with very restricted connections for non-root users, with even DNS looks disabled (salt doesn't really need DNS). 
* The firewall should only allow incoming connections from your specific client IPs, or an ISP/state/country range if it's dynamic. Since this should make your server invisible to most of the rest of the world, this should by itself make it realistically much more secure from actual hacks if Salt ever were to have a vulnerability
* Running the Salt master as a [limited user](https://docs.saltstack.com/en/latest/ref/configuration/nonroot.html), instead of the default of root
* Once your rules are more-or-less stable, with few changes, having a real-time (=inotify) H-IDS like the complicated [Samhain](http://la-samhna.de/samhain/) or the easier OSSEC, so that you get instant notifications when the configuration/formulas (or any system binaries) are modified
* Have a second VM dedicated as a syslog server, so in the unlikely event something does happen, you can get an idea of what went wrong
* Perhaps don't even install the Salt agent on some of your ultra-secure servers; and perhaps instead run a gpg signed SLS file manually
* Other things mentioned in the [Security guide](/articles/server-security-guide/)

This document assumes you've read the official [Getting Started guide](https://docs.saltstack.com/en/getstarted/) and some of the [documentation](https://docs.saltstack.com/en/latest/), I will not be explaining the basics. This just gets into making a comfortable setup, allowing for easy per-host overrides and other niceties.


### Installation (client/server)

(There's a 5000+ line install [bash script](https://github.com/saltstack/salt-bootstrap) which can do all the work, but I prefer to do it via a yum repo, so that it's easier to maintain and we know what's going on)
 
Salt is in the EPEL repo. For CentOS, just a yum install epel-release should do. If you're using RHEL, you need to enable the Red Hat Optional and Supplementary Channel, edit the RHEL_MAJOR_VERSION from 7 to 6 if you're on RHEL6:
```
RHEL_MAJOR_VERSION=7 bash -c 'subscription-manager repos --enable rhel-${RHEL_MAJOR_VERSION}-server-supplementary-rpms --enable rhel-${RHEL_MAJOR_VERSION}-server-optional-rpms'
```
  
EPEL comes with an old version of ZeroMQ, 3.x, whereas Salt is tested on 4.x, so use their repositories:

```  
   (EL6) : cd /etc/yum.repos.d/ && wget https://copr.fedoraproject.org/coprs/saltstack/zeromq4/repo/epel-6/saltstack-zeromq4-epel-6.repo
   (EL7) : cd /etc/yum.repos.d/ && wget https://copr.fedoraproject.org/coprs/saltstack/zeromq4/repo/epel-7/saltstack-zeromq4-epel-7.repo
```    

Continue below to see which package you need to install.


### Installation (server)

If this is a production install, the first thing you'd want to do is set up a restrictive firewall with [FireHOL](/articles/easy-secure-firewalls-with-firehol/), something like this:

```bash
version 5
FIREHOL_LOG_PREFIX="firehol: "
SSH_IPs="192.168.67.0/24"
DNS_SERVERS="192.168.67.1"
SALT_CLIENTS="192.168.67.0/24 1.2.3.4"
 
interface eth0 net
        protection strong
        # Only allow SSH from certain IPs
        server ssh accept src "$SSH_IPs"
        # Salt connections, non-standard port
        server custom salt "tcp/6505 tcp/6506" default accept src "$SALT_CLIENTS"
        # Root is allowed everything; we're not strict here because if
        # someone has root, they can flush the firewall anyway
        client all accept user "root"
        # Allow NTP to sync the time for EL 7, change to user ntp for EL 6
        client "dns ntp" accept user chrony
        # No other outgoing connections are allowed, not even DNS.
```

Note we changed the default port that Salt uses (4505/4506) above to in this case 6505/6506. It's _highly_ recommended that you limit the clients that can connect to the Salt master, as that's by far the weakest point of the server. You'll also want to secure SSH (it's best not having direct logins from the internet at all), and other stuff mentioned in the [security guide](/articles/server-security-guide/), including having a remote syslog server. Remember, if they get this server, they get all your servers.

If this is in a LAN, consider having the hostname 'salt', and the search path configured in all your clients. This would result in not needing to mention the hostname or IP address of the master on the client.

On the server, run:
```
yum install salt-master
systemctl enable salt-master.service # or for EL6 chkconfig salt-master on
service salt-master start
```

Then create a user on your server, say called 'salt':
```
useradd --system --shell /sbin/nologin salt
```

You'd then need to give salt permissions to read certain directories (but ignore the part of the documentation that says you need to let it write to /var/log/salt. I also don't think /etc/salt/ needs to be writable by salt) :
```
chown -R salt /var/cache/salt/ /var/run/salt*
```

You might want to make vim salt friendly by creating the file **/root/.vimrc** :
```
set modeline
set expandtab
set tabstop=2
```

Then change the configuration so that the Salt master runs as 'salt' instead of root; and also log to syslog instead of writing files directly and change the ports, by editing **/etc/salt/master**:
```
publish_port: 6505
user: salt
ret_port: 6506
log_file: file:///dev/log
log_level_logfile: info
```

Then restart salt:
```
systemctl restart salt-master.service
```

And make sure you can see the logs on your remote syslog server. You may want to `yum remove dmidecode` to remove those error messages about not being able to run dmidecode as a limited user every few minutes.

If you ever want to debug issues, it often helps starting the salt-master service in the foreground; so stop the salt-master service and run, **as salt**: `salt-master -l debug`



### Base configuration

Create some basic directories:
```
mkdir -p /srv/{salt,pillar}/
mkdir -p /srv/salt/{development,production}
mkdir -p /srv/salt/development/hosts
```

Append this to your **/etc/salt/master**, which sets up the environments, and also allows for per host (/src/pillar/hosts/your-server.com/) pillars, very handy:
```
file_roots:
  production:
    - /srv/salt/production
  development:
    - /srv/salt/development

pillar_roots:
  base:
    - /srv/pillar
  production:
    - /srv/pillar
  development:
    - /srv/pillar

ext_pillar:
  - file_tree:
      root_dir: /srv/pillar
```


Restart the salt master service, then create some basic files:

**/srv/salt/development/top.sls** :
```
{% for env in [ 'development','production' ] %}
{{env}}:
  '*':
    - hosts.host
  'roles:standard-install':
    - match: grain
    - standard-install
  'roles:firehol':
    - match: grain
    - firehol
{% endfor %}
```

As you can see, you can add roles to your server, so modify them as needed.

**/srv/salt/development/hosts/host.sls** :
```
{% include 'hosts/' + salt['grains.get']('id') + '/init.sls' ignore missing %}
```


**/srv/salt/development/standard-install/init.sls**
```
# Just a sample example
{% if grains['osmajorrelease'] == '7' %}
# EL 7:
  {% set enable_services = [ 'chronyd' ] %}
{% else %}
# EL 6:
  {% set enable_services = [ 'ntpd' ] %}
{% endif %}
 
```

**/srv/pillar/top.sls** :
```
{% for env in [ 'base', 'development','production' ] %}
{{env}}:
  '*':
    - globals
{% endfor %}
```

Put all your global pillars in **/srv/pillar/globals.sls**, and per host pillar overrides/variables in **/srv/pillar/hosts/your-server.yourdomain.com/**.

You can create per-host states by creating a file like **/srv/salt/development/hosts/your-server.yourdomain.com/init.sls** and putting it your state there.

You can do a `git init` on /srv/salt/development, and optionally consider setting up a remote origin just for logs or backups, but be sure to never ever pull from the remote, because if the git server gets hacked, salt gets hacked too. So remotes are only for keeping a record or backup of what's going on.

With git, make the development directory always in a 'devel' git branch, and the production directory in 'master'. Then, as you test this in devel, if you are satisfied, you can push it to the production.

Create a devel branch:
```
cd /srv/salt/development
git checkout -b devel
```

And clone the master branch in production:
```
cd /srv/salt/production/
git clone /srv/salt/development/ .
```

Then go do your stuff in development, test it and do a git add and git commit as usual. Then when you think it's ready and want to publish this to the master branch, type:
```
cd /srv/salt/development
git push . development:master
cd /srv/salt/production
git pull
```

If you want to preview a rendered SLS as it'd appear on the client, I have yet to find a good way, but this is something:
```
salt some-salt-client.rizvir.com cp.get_template "salt://standard-install/init.sls" /tmp/preview saltenv=development
```


### Salt basics

The most common thing would be running a command on all your clients:
`salt '*' cmd.run 'uname -a'`

There are a lot of [modules](http://docs.saltstack.com/en/latest/ref/modules/all/index.html) that you can use to save you from long commands, eg. to install a package:
`salt '*' pkg.install zsh`

If you want to see what that exactly does, you can log into a minion and run the same command in debug mode:
`salt-call -l debug pkg.remove zsh`

It's important to get familiar with Grains, which are static pieces of information that the client has like their OS or RAM. You can do selections based on grains, eg.:
`salt -G 'os:CentOS' test.ping`

If a grain is in a dictionary, you need to put a colon to traverse it. A fictional example is "tags:type:*test*". Get the list of all grains on a client with `salt-call grains.items`.  Arbitrary grains can also be manually set via the minion configuration file, in **/etc/salt/grains**

You can also select clients based on regular expressions:
`salt -E 'salt-client-0[123].*' test.ping`

Or as an explicit comma separated list:
`salt -L 'salt-client-01-el6.rizvir.com, salt-client-02-el6.rizvir.com' test.ping`



### Salt formulas

Formulas are in YAML, and it's important to remember that indentation is done via two spaces, not tabs. The commands that you'd have in it aren't the same as the stuff you'd type on the command line, for example instead of pkg.install (which is a salt.module), the formula would be pkg.installed (which is a salt.state).

You can make your life easier by using the .vim settings ":set expandtab" and ":set tabstop=2".

If you've followed the above setup guide with the included example, you can get started by creating this file in your minion (=client) **/etc/salt/grains** like
```
roles:
- standard-install
```

This will make it follow the /src/salt/standard-install/init.sls formula which, in the sample we did before, installs NTP or Chrony depending on your EL version.

BTW when writing states, you can put in "- failhard: True" if you want Salt to stop if a section did not work. The default otherwise would be to continue doing the rest.
 
You can create host specific stuff by optionally creating files like /src/salt/hosts/{your-minion-id}/init.sls for every host specific state you want.

Test your changes with:
```
salt --state-output=changes '*' state.highstate test=true saltenv=development
```
(the state-output=changes part makes the output only be verbose on changes, and one-liners on non-changes)

States can be seen by all hosts, even for roles they are not part of. If you want to keep host specific secure things like a specific hosts passwords, or if you just need a nice dump for variables per host, use Pillars. Assuming you set the /srv/pillar/top.sls file as described before, create a file called /srv/pillar/globals.sls with your variables, eg. :
```
# User account password (generated with:
# python -c "import crypt; print(crypt.crypt('thepassword', crypt.mksalt(crypt.METHOD_SHA512)))"
account_password: $6$abcdabcdabc2344er5werfwer/abcd.abcd0

# Auto generated list of interfaces excluding loopback
interfaces:
{% for interface in grains['ip4_interfaces'] if (grains['ip4_interfaces'][interface] and interface != "lo") %}
  - {{interface}}
{% endfor %}
```

You can create per host pillars by creating the directory **/src/pillar/hosts/yourhost.yourdomain.com/** and putting files inside; the name of the file is the name of the pillar, and it's raw contents are it's values. Variables in globals.sls can be overridden by host pillar variables. You can reference pillars with:
```
...
- password: {{ pillar['account_password'] }}
and list pillars with:
{% for interface in salt['pillar.get']('interfaces') %}
 - something: {{interface}}
{% endfor %}
```

After you modify a Pillar file, you may need to refresh it on all hosts:
```
salt '*' saltutil.refresh_pillar
```

You can view the pillars that a client sees on the client with:
```
salt-call pillar.items
```

If you change a grain on a minion, you can run:
```
salt yourminion.domain.com saltutil.sync_all
```



### Installation (client)

For the client, run:
```
yum -y install salt-minion
service salt-minion start  # create default directories
```


Unless your salt server is resolvable via just 'salt', you probably would need create a file called **/etc/salt/minion.d/master.conf** with the content:
```
master: salt-server.yourdomain.com
master_port: 6506
environment: development # or production, if you forget this, you'll get a lot of errors about duplicate IDs
```

(try always changing the minion config via the config directory /etc/salt/minion.d instead of the main /etc/salt/minion configuration file, so that it can be managed more easily by Salt)

Some other settings you may consider having are:
```
id: the-hostname-if-the-hostname-is-not-set-or-is-virtual.something.com
```

Create the file /etc/salt/grains, and put in the roles and any specific information of that node you want added, eg:
```
roles:
  - standard-install
  - firehol
  anything: else
```

That should be it. You can add useful settings like `backup_mode: minion` (would back up any configs modified in a cache dir) and `ping_interval: 30` (monitor if the minion gets disconnected) as a managed configuration file so that it's the same in all of your clients and is easily changeable later.
 
Then run:
```
chkconfig salt-minion on
service salt-minion restart
```

(If you're having difficulty starting up or finding an issue with salt-minion, you can enable debug mode by stopping the service and running 'salt-minion -l debug'.)

On the master, type `salt-key -L` , you should be able to see your new client. A quick way to add the client is to accept all keys with `salt-key -A`, although if you want to be more secure, you can see what the claimed key is on the master first:
(server) `salt-key -f salt-client.yourdomain.com`
(client) `salt-call key.finger --local`
(server, if they match) `salt-key -a salt-client.yourdomain.com`

You may have to restart the daemon again once you accept the key in the server (or wait for a bit). Then make sure it works:
salt salt-client.yourdomain.com test.ping
 
Do a test highstate if you want. If there is a bug, and you want to fix it in the development branch but test it on a non-critical server whose environment is 'production', use `salt your-server-name state.highstate saltenv=development`

If you want to make corrections to your SLSs:

* Type in git status before any changes to make sure it's clean
* Do your changes in /srv/salt/development/
* After that, test it on the or a client with:
`salt --state-output=changes yournode.com state.highstate test=true saltenv=development`
* If it looks good, commit it to the development branch:
`cd /srv/salt/development/`
`git add file1 file2`
`git commit -m '(standard-install.sls) Some comment' --author='...'`
`git push --all origin`
* And if you think it's ready for production too:
`git push . development:master`
`cd /src/salt/production`
`git pull`

 
### Example Salt Fomula snippets

Give a warning if RHEL isn't subscribed and fail immediately
```
{% if grains['os'] == "RedHat" %}
  {% if not salt['file.file_exists']('/etc/yum.repos.d/redhat.repo') %}
rhel_not_subscribed:
    test.fail_without_changes:
      - name: "RHEL is not subscribed. Run subscription-manager."
      - failhard: True
  {% endif %} 
{% endif %}
```

Create a default user account
```
rizvir_account:
  user.present:
    - name: 'rizvir'
    - fullname: 'Rizvi R'
    - password: {{ pillar['rizvir_password'] }} 
	# Passwords are generated with python -c "import crypt; print(crypt.crypt('thepassword', crypt.mksalt(crypt.METHOD_SHA512)))"
```


Create  /root/apps, temp, bin, etc. :
```
{% for name in ['apps','temp','bin','scripts','backups'] %}
create_dir_root_{{name}}:
  file.directory:
    - name: /root/{{name}}
{% endfor %}
```

Move anaconda postinstall files if it exsts:
```
{% for anaconda_file in [ 'anaconda-ks.cfg', 'install.log', 'install.log.syslog' ] %}
{% if salt['file.file_exists']('/root/'+anaconda_file) %}
move_{{anaconda_file}}:
  module.run:
    - name: file.move
    - src: {{ "/root/" + anaconda_file }}
    - dst: {{ "/root/temp/" + anaconda_file }}
{% endif %}
{% endfor %}
```

Enabling scrolling in screen:
```
screen_scrolling:
  file.append:
    - name: "/etc/screenrc"
    - text: "termcapinfo xterm* ti@:te@"
```

Modify sshd_config according to the standard installation guidelines:
```
{% set sshd_config = '/etc/ssh/sshd_config' %}
ssh_disable_GSSAPI_auth:
  file.replace:
    - name: {{ sshd_config }}
    - pattern: '^GSSAPIAuthentication yes'
    - repl: 'GSSAPIAuthentication no'
ssh_disable_dns:
  file.prepend:
    - name: {{ sshd_config }}
    - text: 'UseDNS no'
ssh_disable_root_logins:
  file.prepend:
    - name: {{ sshd_config }}
    - text: 'PermitRootLogin no'
    - require:
      - user: rizvir_account
ssh_config_watch:
  service.running:
    - name: 'sshd'
    - watch:
      - file: '/etc/ssh/sshd_config'
```

Colored prompts, set the color in your minion's pillar:
```
# Somehow file.replace goes crazy if there is a x-x because it's between [ ], but escaping 
# that makes the slash visible in the prompt. So a simple workaround is having hostname -f
{% set default_color = "blue" %}
{% set minion_color = salt['pillar.get']('prompt_color', default_color) %}
{% set prompt_color_codes = { 'blue':'1;34m', 
                              'red':'1;31m', 
                              'green':'1;32m', 
                              'gold':'38;5;191m' } %}
{% set color_code = prompt_color_codes.get(minion_color, prompt_color_codes[default_color]) %}
prompt_root_bashrc:
  file.replace:
    - name: '/root/.bashrc'
    - pattern: '^export PS1=.*'
    - repl: export PS1="[\u@\[\e[{{color_code}}\]$(hostname -f)\[\e[0m\] \W]\\\$ "
    - append_if_not_found: True
```
 
Include hardware-HP.sls (that say installs hp-health/hpssa) if it's an HP ProLiant server:
```
{% if salt['grains.get']('productname', '').startswith('ProLiant') %}
include:
  - .hardware-HP
{% endif %}
```





