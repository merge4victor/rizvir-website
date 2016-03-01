There are two methods you could use to keep track of commands run on your linux boxes:

* **Command Logging**: (BASH only) This doesn't add much security (as one could easily bypass logging), but gives an extremely easy to read log file with the command run, the user running the command (even if they run su), and the exit code of the command. I prefer this method as it makes it really easy to get an idea of what you or a trusted colleague did on a server. Since it integrates with syslog, it's also easy to stream it to a log server if needed. The log file would look like this:
```
Feb 24 15:51:40 webserver rizvir: rizvir [10127]: cd /var/www/html/ [0]
Feb 24 15:51:40 webserver rizvir: rizvir [10127]: ls [0]
Feb 24 15:53:11 webserver rizvir: root [10191]: yum update [1]
Feb 24 15:53:18 webserver rizvir: root [10191]: vim /etc/hosts [0]
Feb 24 15:53:41 webserver rizvir: root [10191]: tail -n100 /var/lgocasd [1]
```

* **Keystroke logging with PAM** This is technically more comprehensive and records every keystroke entered on the terminal (optionally only for certain users like root). By default, it also does not log keystokes when the TTY is asking for a password. However, the disadvantage is that it doesn't keep it in a readable text file, so you have to use a tool to see it, and since it records backspaces as well, the output isn't pleasant to read or grep. It also behaves fairly oddly with non-root logging, as the user needs to either type 4K worth of text, or log out (=have the shell exit) before it writes to the log, resulting in things going out of order. However, it doesn't allow non-root users to disable logging like the first option. This is how the aureport tty log would look like for an interaction similar to the previous log output:
```
===============================================
# date time event auid term sess comm data
===============================================
...
12. 02/24/2016 19:43:21 190 1000 ? 4 bash "exit",<ret>
13. 02/24/2016 19:43:23 194 1000 ? 4 bash "su -",<ret>,"exit",<ret>
14. 02/24/2016 19:43:47 231 1000 ? 6 bash "yum update",<ret>
15. 02/24/2016 19:43:52 233 1000 ? 6 bash "vim /et",<tab>,"hosts",<ret>
16. 02/24/2016 19:43:58 235 1000 ? 6 vim <esc>,"[2;2R",<esc>,"[>1;4203;0c0Go",<ret>,"1.2.3.4 test.com",<esc>,":wq",<ret>
17. 02/24/2016 19:44:03 236 1000 ? 6 bash "tail -n100 /var/log/asdasd",<ret>
18. 02/24/2016 19:44:10 238 1000 ? 6 bash "exit",<ret>
19. 02/24/2016 19:44:10 242 1000 ? 6 bash "cd /va",<tab>,"w",<tab>,"h",<tab>,<ret>,"ls",<ret>,"su -",<ret>,"exit",<ret>
```
You can see that the events are out of order (the "cd /var/www/html" was the first command typed, but came in at the end), and it's difficult to read, but on the upside one can see what was modified in /etc/hosts, whereas in the first method it was impossible.

 
You can also use both methods together.
 
### Command Logging

Thanks to my ex-colleague, [Khizer Naeem](blog.kxr.me) for coming up with this.

Optionally, for accountability, it's best if each admin has their own username, and that you disable root logins.

* Append the following line in **/etc/profile.d/z-command_log.sh** (the z- prefix is because some GUI apps in RHEL7 overrides the PROMPT_COMMAND):

```bash
export PROMPT_COMMAND='RETRN_VAL=$?;printf "\033]0;%s@%s:%s\007" "${USER}" "${HOSTNAME%%.*}" "${PWD/#$HOME/~}";logger -p local6.debug "$(whoami) [$$]: $(history 1 | sed "s/^[ ]*[0-9]\+[ ]*//" ) [$RETRN_VAL]"'
# # You could also set:
# readonly PROMPT_COMMAND
# # But that can still be removed by advanced users using gdb on the current shell
```

* Set the syslogger to log local6 to a log file by creating a file called **/etc/rsyslog.d/command_log.conf** with :

```
 local6.*                        /var/log/command.log
```
(If you are running RHEL/CentOS 5, you'd need to append it to /etc/syslog.conf)

* Restart the rsyslog service. 

* That's it. New sessions should have any commands entered logged in /var/log/command.log.

* You can optionally log SFTP file transfers (not scp, but sftp, like FileZilla) by changing the line in **/etc/ssh/sshd_config** that looks like this:
```
	 Subsystem       sftp    /usr/libexec/openssh/sftp-server
```
to
```
	 Subsystem       sftp    /usr/libexec/openssh/sftp-server -l INFO -f LOCAL6
```
and reloading ssh. File transfer logs will then be kept in /var/log/command.log

<br>

### Keystroke logging with PAM

Before you start, ensure you have or create a backup of your /etc/pam.d directory, and note that a mistake can prevent anyone, even root, from logging in, so keep a terminal open and test logins in a separate terminal.

* Add this line to **/etc/pam.d/sshd** if you are only worried about SSH, or to /etc/pam.d/system-auth & /etc/pam.d/password-auth if you want to capture every login:
```
session required pam_tty_audit.so disable=* enable=root,rizvir
```
This would work as it reads, i.e. disable logging for everyone, and then enable it for the users root and rizvir. By default, this won't log keystrokes when a password is being asked, but if you want to log passwords as well (NOT recommended), you can append `log_passwd` to the above line.

On your next login, as long as you haven't disabled the auditd service, your keystrokes would be recorded in the audit log, but don't bother trying to read it as it'd be a mess, use this command instead:

```
aureport --tty
```

That's it. Note however that, for non-root users, this is heavily buffered, so you may not see what you type until the buffer gets flushed, which I think is when you have 4K worth of text, or if you log out (=shell dies). 

For remote audit logging, it's not as easy as enabling /etc/audisp/plugins.d/syslog.conf, as the aureport tool won't be able to parse this style of logs. So you may need to enable native auditd logging on your log server.

On the logging server, you need to make the audit daemon listen on port 60 (open it in the firewall too) by editing **/etc/audit/auditd.conf** and uncommenting `tcp_listen_port =` and putting 60 at the end :
```
tcp_listen_port = 60
```
Restart auditd, and make sure it's listening on port 60, and that iptables allows it.

On the clients, you need to `yum install audispd-plugins.x86_64` , then edit **/etc/audisp/plugins.d/au-remote.conf** to set `active=yes` and edit the **/etc/audisp/audisp-remote.conf** file (I don't know why it's all over the place) to specify the location of the log server. Restart auditd, and that's it. 


