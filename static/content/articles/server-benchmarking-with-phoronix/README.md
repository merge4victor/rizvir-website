In my opinion, the documentation for the phoronix benchmarking suite is quite poor; it explains enough to get single results, but does not clearly explain how you can compare two runs, hence this document. The text below is specifically for Phoronix 5.2, but it may be similar for future releases.
 
### Installation and usage
There is no need to install Phoronix as you can run it straight from the tarball, but you also have the opportunity to install it if you want that copies the binary in the tarball to /usr/bin.

``` 
yum install php-cli php-xml php-gd glibc-static xz
```

Then download the phoronix-test-suite tarball, and, if you want, install it with ./install-sh, otherwise just prefix './' to every phoronix-test-suite command. The postgresql test needs to run as a non-root user, so it's generally better to not run these benchmarks as root.
 
If you just need a simple run with the results, it's easy, just run:

``` 
phoronix-test-suite list-available-tests
phoronix-test-suite benchmark thetest anothertest etc
```
 
Initially, after asking for your root password, it will spend a lot of time seemingly doing nothing, but it's actually running yum in the background, which might take a while to finish.
 
If a test is downloading much slower than your connection, try editing ~/.phoronix-test-suite/user-config.xml and set PromptForDownloadMirror to TRUE.
 
For disk tests, it will not ask you about which disk it should test in; so you need to edit ~/.phoronix-test-suite/user-config.xml and change:
<EnvironmentDirectory>~/.phoronix-test-suite/installed-tests/</EnvironmentDirectory>
to the directory you want to run the tests on. If you plan to format the disk in the mountpoint after each run, be sure to run:
phoronix-test-suite make-download-cache
so that it doesn't re-download everything (it will still have to install it again though).

### Comparing two runs

You will probably want to compare two situations. So to do that, first run the benchmarks, and when it asks you whether you want to save the results, say yes, and when it says "Enter a name to save these results under", give it a common name under which all your benchmarks (this one and future ones) will be under, and then when it asks "Enter a unique name to describe this test run", put in a short but clear name, which will be shown as the label in the graph for this run.

Now instead of putting the same arguments for the second benchmark, find out the exact name (case sensitive) that phoronix gave your last test:
```
ls ~/.phoronix-test-suite/test-results/
```
and then run:
```
phoronix-test-suite benchmark thenameofthetest
```
 
It'll ask you to put a unique name for this run, use some short name as usual. That's it. Look at the `~/.phoronix-test-suite/test-results/` directory for the graphs.
 
Alternatively, you can also use the merge-results option to merge different test results into one.

 
### Comparing two machines

If you want to compare multiple machines, copy the `~/.phoronix-test-suite/test-results` after you finished benchmarking one server to the next one, and remember to use the same test name. If you use a different test name, use the merge-results option.
 
To prevent it downloading the files again, run:
```
phoronix-test-suite make-download-cache
```
and copy the `~/.phoronix-test-suite/download-cache/` directory across servers.

 
### Editing text in the result page
If you want to change a label of a run that appears in the graphs, first get your test name from:
```
ls /.phoronix-test-suite/test-results
```
and then use:
```
phoronix-test-suite rename-identifier-in-result-file the-test-name
```
It will ask you which label you want to change, and what to change it to (spaces allowed).
 
If you want to change the heading or description that appears in the preface, use:
```
phoronix-test-suite edit-result-file the-test-name
```
It will ask you for the new heading (spaces and sane special characters allowed) and the description.
 
And if you want to change the test name, either rename the directory in test-results or type:
```
phoronix-test-suite rename-result-file the-test-name
```
It will ask you for the new name, do not use spaces or special characters.
 

### Standard benchmarks
For disk checks, use (might take 4 hours):
```
phoronix-test-suite benchmark pts/disk
```
 
For a quick yet interesting test; I use (less than 1 hour not including download time):
```
phoronix-test-suite benchmark pts/apache pts/build-php pts/compress-gzip pts/compress-pbzip2 pts/encode-mp3 pts/gnupg pts/network-loopback pts/openssl pts/pgbench pts/phpbench pts/pybench pts/system-decompress-xz pts/unpack-linux pts/aio-stress pts/sqlite
``` 
 
