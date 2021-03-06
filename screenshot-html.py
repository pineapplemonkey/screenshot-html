#!/usr/bin/env python
import subprocess
import threading
import argparse
import requests
import sys
import os

def main(args):
    '''
    Takes a screenshot of the destination URLs web page.
    Returns ??
    
    Args is expected to a dict containing:
     1) args["urls"] = [ "url1", ... ]
     2) args["basefolder"] = "<path-to-folder>" - folder to store screenshots

    Optional args:
     1) args["verbose"] = True - debug output
    
    URLs can be in variations of the following formats:
    1) 127.0.0.01
    2) example.com
    3) https://example.com
    4) 127.0.0.1:9000 
    '''
    verbose_enabled = "verbose" in args and args["verbose"] == True

    phantomjs_script_path = "/tmp/phantomjs_bootstrap.js"
    setup_base(args, phantomjs_script_path)
    urls = setup_urls(args["urls"]) 
    thread_count = args["threads"]
    url_count = len(urls)
    urls_per_shard = url_count / thread_count

    shards = []
    for i in range(0, thread_count):
        start = i * urls_per_shard
        end = start + urls_per_shard
        if i == thread_count - 1:
            end = url_count
        shards.append( (start, end) )

    results = {}

    loglock = threading.Lock()
    threads = []
    for i in range(0, thread_count):
        shard = shards[i]
        threads.append(ThreadedDownloader(urls, args["basefolder"], phantomjs_script_path, verbose_enabled, shard[0], shard[1], loglock))
    
    for thread in threads:
        thread.start()

    for thread in threads:
        try:
            thread.join()
        except:
            continue

    for thread in threads:
        results.update(thread.results)

    return results

class ThreadedDownloader(threading.Thread):
    def __init__(self, urls, basefolder, phantomjs_script, verbose_enabled, start, end, loglock):
        threading.Thread.__init__(self)
        self.urls = urls
        self.verbose = verbose_enabled
        self.basefolder = basefolder
        self.phantomjs_script = phantomjs_script
        self.start_index = start
        self.end_index = end
        self.loglock = loglock
        self.results = {}

    def run(self):
        self.results = {}
        for i in range(self.start_index, self.end_index):
            url = self.urls[i]
            self.results[url] = {}
            result_path = os.path.abspath(self.basefolder + "/" + url_to_filename(url) + ".png")
            process = subprocess.Popen(["phantomjs", self.phantomjs_script, url, result_path], stdout=subprocess.PIPE)
            line = process.stdout.readline().strip()
            self.results[url]["path"] = result_path
            self.results[url]["status"] = line

            if self.verbose:
                self.loglock.acquire()
                print("[+] Result: %s (%s)" % (line, url))
                self.loglock.release()

def plugin_run(args):
    '''
    Run the tool as a plugin, using the given args to execute
    '''
    return main(args)

def parse_cmdline():
    description="""Testar testsson.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("-u", "--urls", help="The url to take a screenshot of.", nargs="*", default=[])
    parser.add_argument("-r", "--read", help="Read urls from the specified file.")
    parser.add_argument("-f", "--format", help="The format to use for the output", choices=["json", "grep"], default="grep")
    parser.add_argument("-b", "--basefolder", help="The folder to place the screenshots in.", default="./screenshots")
    parser.add_argument("-v", "--verbose", help="Outputs the status of the script.", action="store_true")
    parser.add_argument("-t", "--threads", help="Amount of threads to use", default=1, type=int)
    args = parser.parse_args()
    
    if args.read:
        with open(args.read, "r") as f:
            lines = f.readlines()
            args.urls.extend(map(lambda x: x.strip(), lines))
    elif args.urls == []: 
        lines = sys.stdin.readlines()
        args.urls.extend(map(lambda x: x.strip(), lines))

    return args

def setup_base(args, payload_path):
    '''
    Prepare the resources required.
    '''
    javascript_payload = """
var page = require("webpage").create();
page.settings.userAgent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/55.0.2883.87 Chrome/55.0.2883.87 Safari/537.36";
var system = require("system");
var args = system.args;
page.open(args[1], function(status) {
    if (status == "success") {
        page.render(args[2]);
    } 
    console.log(status)
    phantom.exit();
});
"""
    with open(payload_path, "w") as f:
        f.write(javascript_payload)

    if not os.path.exists(args["basefolder"]):
       os.makedirs(args["basefolder"]) 

def url_to_filename(url):
    return url.replace("/", "_").replace("\\", "_").replace("?", "_") 

def setup_urls(urls):
    ret = []
    for url in urls:
        if not url.startswith("http"):
            ret.append("http://" + url)
            ret.append("https://" + url) 
        else:
            ret.append(url)
    return list(set(ret))

if __name__ == "__main__":
    args = parse_cmdline()
    results = main(vars(args))
