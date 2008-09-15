#!/usr/bin/python
"""Analiza os dados capturados"""

import os
import sys
import re
import glob
import time

import pylab

INTERVAL=0.1

def print_ts(ts):
    return time.asctime(time.localtime(int(ts)))

# {{{ list_results
def list_results(results_dir):
    """Monta a lista dos experimentos"""
    exp_r = re.compile('results.(\d+).txt')
    clients_through_r = re.compile('results.\d+.(\d+\.\d+\.\d+\.\d+).mcast')
    experiments = []
    headers = glob.glob("results*txt") # monta a lista de experimentos
    for e in headers:
        ret = exp_r.findall(e)
        if not ret:
            print "Error experiment %s has no timestamp!" % e
            continue
        timestamp = ret[0]
        if timestamp in headers:
            print "Error: experiment %s was already processed!" % timestamp
            continue
        experiment = {}
        print "Processing experiment %s:" % timestamp
        title = open(e).readline().strip()
        experiment['title'] = title
        experiment['timestamp'] = timestamp
        experiment['timestamp_s'] = print_ts(timestamp)
        # agora vamos ver os clientes
        logs = glob.glob("results.%s*.mcast" % timestamp)
        if not logs:
            experiment['clients'] = []
        else:
            # foram encontrados logs de tshark
            clients = []
            for l in logs:
                ret = clients_through_r.findall(l)
                if not ret:
                    print "Error: %s is not valid log file!" % l
                    continue
                client = ret[0]
                clients.append(client)
            experiment['clients'] = clients
        experiments.append(experiment)
    # volta para diretorio anterior
    return experiments
# }}}


if __name__ == "__main__":
    r = re.compile("# total msgs: (\d+), max bandwidth: (\d+)")
    for exp in list_results("."):
        # vamos ver se o titulo esta certo
        title = exp['title']
        try:
            title.split(":", 1)[1]
        except:
            print "bad"
            try:
                client = exp['clients'][0]
            except:
                continue
            newtitle = open("results.%s.%s.mcast" % (exp['timestamp'], client)).readline().strip()
            print newtitle
            msgs, bandwidth =  r.findall(newtitle)[0]
            fd = open("results.%s.txt" % exp['timestamp'], "w")
            title = title + ": %s msgs, %s bandwidth." % (msgs, bandwidth)
            print >> fd, "%s\nClients: %s" % (title, ",".join(exp['clients']))
            fd.close()
