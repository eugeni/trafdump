#!/usr/bin/python
"""Analiza os dados capturados"""

import os
import sys
import re
import glob
import time

import pylab

def printts(ts):
    return time.asctime(time.localtime(int(ts)))

# {{{ list_results
def list_results(results_dir):
    """Monta a lista dos experimentos"""
    exp_r = re.compile('results.(\d+).txt')
    clients_tshark_r = re.compile('results.\d+.(\d+\.\d+\.\d+\.\d+).pcap')
    clients_through_r = re.compile('results.\d+.(\d+\.\d+\.\d+\.\d+).dump')
    experiments = {}
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
        print "  >> %s" % title
        print "  >> %s" % printts(timestamp)
        # agora vamos ver os clientes
        logs = glob.glob("results.%s*.pcap" % timestamp)
        if logs:
            # foram encontrados logs de tshark
            clients = []
            print "  >> Traffic data:"
            for l in logs:
                ret = clients_tshark_r.findall(l)
                if not ret:
                    print "Error: %s is not valid log file!" % l
                    continue
                client = ret[0]
                print "    >> %s" % client
                clients.append(client)
            experiment['clients'] = clients
        experiments[timestamp] = experiment
        # agora vamos ver os resultados de throughput
        logs = glob.glob("results.%s*.band" % timestamp)
        if logs:
            # foram encontrados logs de tshark
            clients = []
            print "  >> Throughput data:"
            for l in logs:
                ret = clients_through_r.findall(l)
                if not ret:
                    print "Error: %s is not valid log file!" % l
                    continue
                client = ret[0]
                print "    >> %s" % client
                clients.append(client)
            experiment['throughput'] = clients
        experiments[timestamp] = experiment
    # volta para diretorio anterior
    return experiments
# }}}

# {{{ parse_tshark
def parse_tshark(file, params):
    """Parses tshark output and strips headers and footers"""
    space_r = re.compile("^\s*$")
    sep_r = re.compile("^=*$")
    data = os.popen("tshark -q -r %s %s" % (file, params)).readlines()
    output = []
    for l in data:
        if space_r.findall(l):
            continue
        if sep_r.findall(l):
            continue
        output.append(l.strip())
    return output
# }}}

# {{{ exp_summary
def exp_summary(file, output=sys.stdout):
    """Parseia o sumario"""
    proto_r = re.compile('(\w*)\s*frames:(\d+)\s*bytes:(\d+)')
    data = parse_tshark(file, "-z io,phs")
    descr = data[0]
    filter = data[1]
    res = proto_r.findall("\n".join(data))
    if not res:
        print "Unable to find protocol statistics"
        return
    protocols = []
    traf = 0
    # Avalia os protocolos
    for z in res:
        proto, frames, bytes = z
        bytes = int(bytes)
        protocols.append((proto, bytes))
        traf += bytes

    # Calcula a distribuicao
    print >>output, """
        <table class="summary">
        <tr>
        <td><b>Protocol</b></td>
        <td><b>Bytes</b></td>
        <td><b>Percentage</b></td>
        </tr> """
    for proto, bytes in protocols:
        percentage = float((bytes * 100.0) / traf)
        print >>output, """
            <tr>
            <td><b>%(name)s</b></td>
            <td><i>%(bytes)d</i></td>
            <td><i>%(percentage)0.2f%%</i></td>
            </tr>""" % { 'name': proto,
                    'bytes': bytes,
                    'percentage': percentage
                    }
    print >>output, """
        </table> """
    return
# }}}

# {{{ exp_totaltraf
def exp_totaltraf(file, output=sys.stdout, interval=1):
    """Calcula a distribuicao do trafego ao longo do tempo"""
    traf_r = re.compile("(\d+.\d+)-(\d+.\d+)\s*(\d+)\s*(\d+)")
    data = parse_tshark(file, "-z io,stat,%s" % interval)
    res = traf_r.findall("\n".join(data[5:]))
    timeline = []
    traf = []
    for start, end, frames, bytes in res:
        timeline.append(float(start))
        traf.append(int(bytes))
    return timeline, traf
# }}}

# {{{ exp_trafmyth
def exp_trafmyth(file, output=sys.stdout, interval=1):
    """Calcula a distribuicao do trafego ao longo do tempo"""
    traf_r = re.compile("(\d+.\d+)-(\d+.\d+)\s*(\d+)\s*(\d+)")
    data = parse_tshark(file, "-z io,stat,%s,ip.dst==225.2.41.11" % interval)
    res = traf_r.findall("\n".join(data[5:]))
    timeline = []
    traf = []
    for start, end, frames, bytes in res:
        bytes = int(bytes)
        if bytes == 0:
            continue
        timeline.append(float(start))
        traf.append(bytes)
    return timeline, traf
# }}}

def generate_report(experiments, output=sys.stdout):
    """Gera o relatorio de tudo"""
    for ts in experiments:
        experiment = experiments[ts]
        title = experiment['title']
        date = printts(ts)
        print experiment
        timelines = []
        total_trafs = []
        myth_trafs = []
        curfigure = 0
        for client in experiment['clients']:
            timeline_sec, total_traf = exp_totaltraf("results.%s.%s.pcap" % (ts, client))
            timeline_sec_myth, total_traf_myth = exp_trafmyth("results.%s.%s.pcap" % (ts, client))
            total_trafs.append((client, timeline_sec, total_traf))
            myth_trafs.append((client, timeline_sec_myth, total_traf_myth))
            print client
        pylab.figure(curfigure)
        pylab.title("%s\n%s" % (title, date))
        pylab.xlabel("Execution timeline")
        pylab.ylabel("Traffic (bytes)")
        for client, timeline, traf in total_trafs:
            pylab.plot(timeline, traf, label="Total traffic for %s" % client)
        for client, timeline, traf in myth_trafs:
            pylab.plot(timeline, traf, label="Mythware traffic for %s" % client)
        pylab.legend()
        pylab.show()
        curfigure += 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print "Usage: %s <results directory>"
        sys.exit(1)
    results_dir = sys.argv[1]
    curdir = os.getcwd()
    try:
        os.chdir(results_dir)
    except:
        print "Error: unable to enter %s: %s!" % (results_dir, sys.exc_value)
        sys.exit(1)
    print "Processing log files.."
    experiments  = list_results(results_dir)
    if experiments:
        generate_report(experiments)
    os.chdir(curdir)
