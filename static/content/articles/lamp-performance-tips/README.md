### Quantifying things
Before you get started, make you have a method of measuring the performance of your web application. You may need to keep track of both single page load times (either by simple things like Firefox/Chromes dev tools to show page load times or a just a silly `time wget "http://yoursite"`, or possibly services like New Relic) as well as the maximum requests per second your server can handle with different concurrent requests, either by tools like `ab`, or, my favorite, [Apache JMeter](http://jmeter.apache.org), which is a bit complicated to get started with, but allows you to simulate page logins even if you generate dynamic tokens for CSRF protection in your forms using regex extractors. 

If you can, try doing your tests on the same network to cut down the variations caused by your internet connection latency. 


### PHP stuff
Enable APC, which involves just a simple `yum install php-pecl-apc`. This is a quick way to drastically improve your PHP performance. Watch the error_log to make sure it has enough memory; if it doesn't increase it by editing `/etc/php.d/apc.ini` and changing `apc.shm_size`.

You could also increase the realpath cache in your php.ini, though increasing the ttl can lead to strange things happening after a change for longer if the cache is supposed to be invalidated:
```
realpath_cache_size = 128k
realpath_cache_ttl = 3600 
```


### Query caching
Depending on your website, enabling MySQL query caching could drastically improve your performance if your sites run the same queries that get the same results over and over again (but it can also significantly reduce performance in some cases, say if there are a lot of changes in the database). 

To enable query caching, you can try adding something like this to the `[mysqld]` section in `/etc/my.cnf` (changing the setting based on your RAM):
```
thread_cache_size = 50
table_cache = 200
query_cache_size = 1024M
join_buffer_size = 256K
tmp_table_size = 32M
max_heap_table_size = 32M
innodb_buffer_pool_size = 4G
``` 

You can also use [mysqltuner.pl](http://mysqltuner.com/ "http://mysqltuner.com/") to find out other ways you could optimize your DB.

### Query logging
If you have custom-developed sites or SQL queries in your PHP app, enable slow query logging in MySQL (/etc/my.cnf's [mysqld]) to find out any slow dynamic queries:
```
slow_query_log = 1
long_query_time = 0
slow_query_log_file = /var/log/mysqlslowquery.log
```

(you need to touch and chown mysql:mysql /var/log/mysqlslowquery.log)
 
 
### Strace
Run strace on Apache to find out if it's being delayed with lots of stat calls. For example, create a file called /root/bin/StraceApache with:
```bash
strace -f $(for i in `ps aux | grep http | awk ' { print $2 }'`; do echo -n "-p $i "; done) $@
``` 

You can run "StraceApache -c", load a slow page, and then see what calls is causing the most slowdowns. If it's stat calls, you can for example do a:
StraceApache  2>&1 | tee /tmp/strace
cat /tmp/strace | grep " stat("
to see what files are stat()ed.

As an example, for light fast websites, you could increase your requests/second significantly by disabling AllowOverride, which according to strace is a limiting factor because of the numerous getcwd calls per directory per request.
 
 
### Apache KeepAlive
This may not help benchmark results, but would improve the user experience. Change
```
KeepAlive On
```
in `/etc/httpd/conf/httpd.conf`
 

### Kernel TCP reuse
Avoid tcp_tw_recycle as that may cause issues with NATing or load balancers. Just use the safer tcp_tw_reuse in /etc/sysctl.conf:
```
net.ipv4.tcp_tw_reuse=1
```
 
### Enable GZIP compression
This won't help benchmark numbers (in fact it may do the opposite, by a drastic amount), but will improve user experience if there are large text reponses. Have something like /etc/httpd/conf.d/compress.conf with:

```bash
<IfModule mod_deflate.c>
        SetOutputFilter DEFLATE
        AddOutputFilterByType DEFLATE text/plain
        AddOutputFilterByType DEFLATE text/html
        AddOutputFilterByType DEFLATE text/xml
        AddOutputFilterByType DEFLATE text/css
        AddOutputFilterByType DEFLATE application/xml
        AddOutputFilterByType DEFLATE application/xhtml+xml
        AddOutputFilterByType DEFLATE application/rss+xml
        AddOutputFilterByType DEFLATE application/javascript
        AddOutputFilterByType DEFLATE application/x-javascript
        AddOutputFilterByType DEFLATE application/x-httpd-php
</IfModule>
```
 
### Cache static files
A trend in application development is putting a request on static content to force it to not be cached, eg. site_application.js?revision=3. See if you can have the developer use the Yahoo method instead, which is put the file as a softlink with the version number in the filename, eg. site_application_rev_3.js.

If that's not possible, you can force caching of JS/CSS files regardless, but this can break websites so be careful; this is mainly useful for internal sites where the users can be told to hard refresh or clear their cache, so this is **NOT** recommended generally:
```bash
		# Not recommended:
        <ifModule mod_expires.c>
                ExpiresActive On
                ExpiresByType text/javascript "access plus 216000 seconds"
                ExpiresByType application/x-javascript "access plus 216000 seconds"
                ExpiresByType text/css "access plus 216000 seconds"
                ExpiresByType image/gif "access plus 2592000 seconds"
                ExpiresByType image/jpeg "access plus 2592000 seconds"
                ExpiresByType image/png "access plus 2592000 seconds"
        </ifModule>
```
 
 
### Maximum open files
Extreme benchmarking can lead apache to reach the default open file limit. Increase the open file limit by editing `/etc/security/limits.conf` :
```
*               soft    nofile          60240
*               hard    nofile          60240
```

If you expect a huge number of processes, consider increasing the 1024 process limit per user in /etc/security/limits.d/90-nproc.conf
 

### ZendDB caching
If you are using ZendDB, you can add schema caching in the code, which in one of my clients websites increased page load times by an entire second.
 
### xhprof
Enable PHP's xhprof to examine where the slowdowns in the code are.
 
* Enable EPEL
* yum install xhprof
* Edit `/etc/php.d/xhprof.ini` & change the `xhprof.output_dir` to somewhere that is writeable by Apache
* Edit `/etc/httpd/conf.d/xhprof.conf` and make it accessible from your LAN (but not the internet)
 
Now normally you need to change the code to add the profiling, but a hack from techPortal makes this uncessary; create these two files:
 
`/usr/share/xhprof/xhprof_html/header.php` :
```php
<?php
if (extension_loaded('xhprof')) {
    include_once '/usr/share/xhprof/xhprof_lib/utils/xhprof_lib.php';
    include_once '/usr/share/xhprof/xhprof_lib/utils/xhprof_runs.php';
    xhprof_enable(XHPROF_FLAGS_CPU + XHPROF_FLAGS_MEMORY);
}
?>
```

`/usr/share/xhprof/xhprof_html/footer.php` (change the URLs as required) :
```php
<?php
if (extension_loaded('xhprof')) {
    $profiler_namespace = 'ecampus';  // namespace for your application
    $xhprof_data = xhprof_disable();
    $xhprof_runs = new XHProfRuns_Default();
    $run_id = $xhprof_runs->save_run($xhprof_data, $profiler_namespace);

    // url to the XHProf UI libraries (change the host name and path)
    $profiler_url = sprintf('http://1.2.3.4/xhprof/index.php?run=%s&amp;source=%s', $run_id, $profiler_namespace);
    echo '<a href="'. $profiler_url .'" target="_blank">Profiler output</a>';
}
?>
```
 
Then in the .htaccess or (if you disabled AllowOverride for performance) Apache configuration directory, add this:
```
  php_value auto_prepend_file /usr/share/xhprof/xhprof_html/header.php
  php_value auto_append_file /usr/share/xhprof/xhprof_html/footer.php
```

Then just click on the link at the bottom of the page, and sort by Excl. Wall Time (excl. means time specifically for that function without dependencies).
 
**REMEMBER TO DISABLE xhprof AFTER YOU ARE DONE.**
 
 
### Timers in code
If xhprof is too much for your simple needs, you can double check if a PHP function or block that you suspect is slow really is slow by putting in timers when the function starts:
 
```php
$_bench_time_before = round(microtime(true) * 1000);
```

and this when it just ends (eg. before every return):
 
```php
$_bench_time = round(microtime(true) * 1000) - $_bench_time_before ;  error_log("In " . __FILE__ . ":" . __FUNCTION__ . ", milliseconds: $_bench_time");
```

You just have to tail the error_logs to see the times. You can add them up by running:
```bash
tail -f -n0 /var/log/apache2/error.log  | tee /tmp/phptime
```
Then loading a single page, stopping the tail and then adding the numbers up:
```bash
cat /tmp/phptime | grep "milliseconds: " | sed -e 's/.* milliseconds: \([0-9.]\+\).*/\1/g' | tr '\n' '+' | head -c -1 | awk ' { print $0 '\n' } ' | bc
```

