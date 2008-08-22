#!/usr/bin/python
"""Analiza os dados capturados"""

import os
import sys
import re
import glob
import time

import pylab

INTERVAL=0.1

def printts(ts):
    return time.asctime(time.localtime(int(ts)))

CSS_TEMPLATE="""
body {
    font-family: Arial, sans-serif;
    padding: 20px 20px 20px 20px;
}

.resultsclient {
    margin-left: 20px;
    padding: 5px 5px 5px 10px;
    background-color: #eee;
    margin-bottom: 10px;
    display: block;
    font-size: 11px;
}

.conclusions {
    margin-left: 10px;
    padding: 5px 5px 5px 10px;
    margin-bottom: 10px;
    display: block;
    font-size: 12px;
}
"""

# {{{ list_results
def list_results(results_dir):
    """Monta a lista dos experimentos"""
    exp_r = re.compile('results.(\d+).txt')
    clients_tshark_r = re.compile('results.\d+.(\d+\.\d+\.\d+\.\d+).pcap')
    clients_through_r = re.compile('results.\d+.(\d+\.\d+\.\d+\.\d+).dump')
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
        experiment['timestamp'] = printts(timestamp)
        print "  >> %s" % title
        print "  >> %s" % printts(timestamp)
        # agora vamos ver os clientes
        logs = glob.glob("results.%s*.pcap" % timestamp)
        if not logs:
            experiment['clients'] = []
        else:
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
        # agora vamos ver os resultados de throughput
        logs = glob.glob("results.%s*.band" % timestamp)
        if not logs:
            experiment['throughput'] = []
        else:
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
        experiments.append((timestamp, experiment))
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
def exp_summary(timestamp, client):
    """Parseia o sumario"""
    proto_r = re.compile('(\w*)\s*frames:(\d+)\s*bytes:(\d+)')
    data = parse_tshark("results.%s.%s.pcap" % (timestamp, client), "-z io,phs")
    descr = data[0]
    filter = data[1]
    res = proto_r.findall("\n".join(data))
    if not res:
        print "Unable to find protocol statistics"
        return
    protocols = []
    traf = 0
    # Avalia os protocolos
    ignore_proto = ["frame", "eth", "data", "ip"]
    for z in res:
        proto, frames, bytes = z
        if proto in ignore_proto:
            continue
        bytes = int(bytes)
        protocols.append((proto, bytes))
        traf += bytes

    list_protocols = []
    list_bytes = []
    list_percentages = []
    for proto, bytes in protocols:
        percentage = float((bytes * 100.0) / traf)
        list_protocols.append(proto)
        list_bytes.append(bytes)
        list_percentages.append(percentage)
    return list_protocols, list_bytes, list_percentages
# }}}

# {{{ exp_totaltraf
def exp_totaltraf(file, output=sys.stdout, interval=INTERVAL):
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

# {{{ exp_trafmythscreen
def exp_trafmythscreen(file, output=sys.stdout, interval=INTERVAL):
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

# {{{ exp_trafmythfile
def exp_trafmythfile(file, output=sys.stdout, interval=INTERVAL):
    """Calcula a distribuicao do trafego ao longo do tempo"""
    traf_r = re.compile("(\d+.\d+)-(\d+.\d+)\s*(\d+)\s*(\d+)")
    data = parse_tshark(file, "-z io,stat,%s,ip.dst==225.2.41.12" % interval)
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

# {{{ generate_report
def generate_report(experiments, output=sys.stdout):
    """Gera o relatorio de tudo"""
    # {{{ html header
    print >>output, """
    <html>
    <head>
    <title>Lab traffic analysis report</title>
    <link rel="stylesheet" href="style.css" type="text/css">
    <script type="text/javascript">
function toggle(whichLayer)
{
    if (document.getElementById)
    {
        // this is the way the standards work
        var style2 = document.getElementById(whichLayer).style;
        if (style2.display == "none") { style2.display = "block"; }
        else { style2.display = "none"; }
    }
    else if (document.all)
    {
        // this is the way old msie versions work
        var style2 = document.all[whichLayer].style;
        if (style2.display == "none") { style2.display = "block"; }
        else { style2.display = "none"; }
    }
    else if (document.layers)
    {
        // this is the way nn4 works
        var style2 = document.layers[whichLayer].style;
        if (style2.display == "none") { style2.display = "block"; }
        else { style2.display = "none"; }
    }
}
    </script>
    </head>

    <body>

    <h1>Lab traffic analysis report</h1>
    <h2>Contents</h2>
    <ul>
    """
    # }}}

    # monta o conteudo
    for ts, experiment in experiments:
        print >>output, """
        <li> <a href="#%(ts)s">%(timestamp)s: %(descr)s"</a> """ % {"ts": ts, "timestamp": experiment['timestamp'], "descr": experiment['title']}

    print >>output, """
        </ul>"""

    # processa os experimentos
    curexperiment = 1
    for ts, experiment in experiments:
        title = experiment['title']
        date = printts(ts)
        print experiment
        timelines = []
        total_trafs = []
        myth_traf_screen = []
        myth_traf_file = []
        print >>output, """
            <hr>
            <a name="%(ts)s">
            <h3>Experiment %(curexperiment)d</h3>
            </a>

            <table class="experiment">
            <tr>
            <td><b>Description:</b></td>
            <td>%(descr)s</td>
            </tr>
            <tr>
            <td><b>Date:</b></td>
            <td>%(timestamp)s</td>
            </tr>
            <tr>
            <td><b>Number of clients for throughput test:</b></td>
            <td>%(clients_throughput)d</td>
            </tr>
            <tr>
            <td><b>Number of clients for mythware test:</b></td>
            <td>%(clients_myth)d</td>
            </tr>
            </table>

            """ % {
                    "ts": ts,
                    "curexperiment": curexperiment,
                    "descr": experiment["title"],
                    "timestamp": experiment["timestamp"],
                    "clients_throughput": len(experiment["throughput"]),
                    "clients_myth": len(experiment["clients"])
                    }
        # mythware results
        elapsed_times_screen = []
        elapsed_times_file = []
        for client in experiment['clients']:
            print >>output, """
                <div class="resultsclient">
                <h3>
                Results for client %s
                </h3>""" % client
            # calcula as estatisticas
            list_protocols, list_bytes, list_percentages = exp_summary(ts, client)
            print >>output, """
                <p><a href="#%(ts)s" onclick='javascript:toggle(\"clientsummary.%(ts)s.%(client)s\");'>Protocol statistics</a></p>
                <div id="clientsummary.%(ts)s.%(client)s" style="display:none;">
                <table class="clientsummary">
                <thead>
                <tr>
                <td><b>Protocol statistics</b></td>
                </tr>
                </thead>
                <tr>
                <td valign="top">
                <div class="splitsummary">
                <table>
                <tr>
                <td>
                <td><b>Protocol</b></td>
                <td><b>Bytes</b></td>
                <td><b>Percentage</b></td>
                </tr> """ % {"ts": ts, "client": client}
            for proto, bytes, percentage in map(None, list_protocols, list_bytes, list_percentages):
                print >>output, """
                    <tr>
                    <td><b>%(name)s</b></td>
                    <td><i>%(bytes)d Bytes</i></td>
                    <td><i>%(percentage)0.2f%%</i></td>
                    </tr>""" % { 'name': proto,
                            'bytes': bytes,
                            'percentage': percentage
                            }
            print >>output, """
                </table>
                </div>
                </td>

                <td>
                <img src="img.%s.%s.summary.png" width="420" height="420">
                </td>
                </tr>
                </table>

                </td>
                </tr>
                </table>
                </div>""" % (ts, client)
            # monta o grafico da distribuicao dos protocolos
            pylab.figure(figsize=(8,8))
            ax = pylab.axes([0.1, 0.1, 0.8, 0.8])
            pylab.title("Protocol usage distribution")
            pylab.pie(list_bytes, labels=list_protocols)
            pylab.savefig("img.%s.%s.summary.png" % (ts, client), format="png")
            # Calcula a distribuicao
            timeline_sec, total_traf = exp_totaltraf("results.%s.%s.pcap" % (ts, client))
            timeline_sec_myth_screen, total_traf_myth_screen = exp_trafmythscreen("results.%s.%s.pcap" % (ts, client))
            timeline_sec_myth_file, total_traf_myth_file = exp_trafmythfile("results.%s.%s.pcap" % (ts, client))
            total_trafs.append((client, timeline_sec, total_traf))
            myth_traf_screen.append((client, timeline_sec_myth_screen, total_traf_myth_screen))
            myth_traf_file.append((client, timeline_sec_myth_file, total_traf_myth_file))
            elapsed_time_screen = 0
            # calcula o tempo que demorou
            if timeline_sec_myth_screen:
                elapsed_time_screen = max(timeline_sec_myth_screen) - min(timeline_sec_myth_screen)
                elapsed_times_screen.append(elapsed_time_screen)
            elapsed_time_file = 0
            if timeline_sec_myth_file:
                elapsed_time_file = max(timeline_sec_myth_file) - min(timeline_sec_myth_file)
                elapsed_times_file.append(elapsed_time_file)
            print >>output, """
            <p><a href="#%(ts)s" onclick='javascript:toggle(\"trafficsummary.%(ts)s.%(client)s\");'>Detailed traffic</a></p>
            <div id="trafficsummary.%(ts)s.%(client)s" style="display:none;">
            <a href="img.%(ts)s.%(client)s.totaltraf.png">
            <img src="img.%(ts)s.%(client)s.totaltraf.png" width="420" height="420">
            </a>
            <a href="img.%(ts)s.%(client)s.mythscreentraf.png">
            <img src="img.%(ts)s.%(client)s.mythscreentraf.png" width="420" height="420">
            </a>
            <a href="img.%(ts)s.%(client)s.mythfiletraf.png">
            <img src="img.%(ts)s.%(client)s.mythfiletraf.png" width="420" height="420">
            </a>
            </div>

            <div class="clientresults">
            <table>
            <tr>
            <td><b>Screen transmition duration:</b></td>
            <td>%(elapsed_time_screen)0.2f seconds</td>
            </tr>
            <tr>
            <td><b>File transmition duration:</b></td>
            <td>%(elapsed_time_file)0.2f seconds</td>
            </tr>
            </table>
            </div>
            </div>
            """ % ( {"elapsed_time_screen": elapsed_time_screen, "elapsed_time_file": elapsed_time_file, "client": client, "ts": ts } )

            # monta as figuras
            # trafego total
            pylab.figure(figsize=(8,8))
            pylab.title("Traffic for client %s\n%s" % (client, experiment["timestamp"]))
            pylab.xlabel("Execution timeline")
            pylab.ylabel("Traffic (bytes)")
            pylab.plot(timeline_sec, total_traf, label="Total traffic")
            pylab.legend()
            pylab.grid()
            pylab.savefig("img.%s.%s.totaltraf.png" % (ts, client), format="png")

            # trafego da tela
            pylab.figure(figsize=(8,8))
            pylab.title("Mythware Screen Traffic for client %s\n%s" % (client, experiment["timestamp"]))
            pylab.xlabel("Execution timeline")
            pylab.ylabel("Traffic (bytes)")
            pylab.plot(timeline_sec, total_traf, label="Total traffic")
            pylab.plot(timeline_sec_myth_screen, total_traf_myth_screen, 'r-', label="Mythware screen")
            pylab.legend()
            pylab.grid()
            pylab.savefig("img.%s.%s.mythscreentraf.png" % (ts, client), format="png")

            # trafego de arquivos
            pylab.figure(figsize=(8,8))
            pylab.title("Mythware File Traffic for client %s\n%s" % (client, experiment["timestamp"]))
            pylab.xlabel("Execution timeline")
            pylab.ylabel("Traffic (bytes)")
            pylab.plot(timeline_sec, total_traf, label="Total traffic")
            pylab.plot(timeline_sec_myth_file, total_traf_myth_file, 'r-', label="Mythware SendFile")
            pylab.legend()
            pylab.grid()
            pylab.savefig("img.%s.%s.mythfiletraf.png" % (ts, client), format="png")

        # calcula os resultados gerais
        if elapsed_times_screen:
            min_elapsed_time_screen = min(elapsed_times_screen)
            max_elapsed_time_screen = max(elapsed_times_screen)
        else:
            min_elapsed_time_screen = 0
            max_elapsed_time_screen = 0
        if elapsed_times_file:
            min_elapsed_time_file = min(elapsed_times_file)
            max_elapsed_time_file = max(elapsed_times_file)
        else:
            min_elapsed_time_file = 0
            max_elapsed_time_file = 0
        min_max_screen_diff = max_elapsed_time_screen - min_elapsed_time_screen
        min_max_file_diff = max_elapsed_time_file - min_elapsed_time_file

        print >>output, """
            <div class="conclusions">
            <b>Overall experiment results</b>
            <div class="clientresults">
            <table>
            <tr>
            <td><b>Minimum screen transmission time:</b></td>
            <td>%(min_elapsed_time_screen)0.2f seconds</td>
            </tr>
            <tr>
            <td><b>Maximum screen transmission time:</b></td>
            <td>%(min_elapsed_time_screen)0.2f seconds</td>
            </tr>
            <tr>
            <td><b>Difference between best and worst client:</b></td>
            <td>%(min_max_screen_diff)0.2f seconds</td>
            </tr>
            <tr>
            <td><b>Minimum file transmition duration:</b></td>
            <td>%(min_elapsed_time_file)0.2f seconds</td>
            </tr>
            <tr>
            <td><b>Maximum file transmition duration:</b></td>
            <td>%(min_elapsed_time_file)0.2f seconds</td>
            </tr>
            <tr>
            <td><b>Difference between best and worst client:</b></td>
            <td>%(min_max_file_diff)0.2f seconds</td>
            </tr>
            </table>
            </div>
            """ % {
                    "min_elapsed_time_screen": min_elapsed_time_screen,
                    "max_elapsed_time_screen": max_elapsed_time_screen,
                    "min_elapsed_time_file": min_elapsed_time_file,
                    "max_elapsed_time_file": max_elapsed_time_file,
                    "min_max_screen_diff": min_max_screen_diff,
                    "min_max_file_diff": min_max_file_diff,
                    }

        print >>output, """
            <p><a href="#%(ts)s" onclick='javascript:toggle(\"trafficsummary.%(ts)s\");'>Complete Lab traffic</a></p>
            <div id="trafficsummary.%(ts)s" style="display:none;">
            <a href="img.%(ts)s.totaltraf.png">
            <img src="img.%(ts)s.totaltraf.png" width="420" height="420">
            </a>
            <a href="img.%(ts)s.totalmythscreentraf.png">
            <img src="img.%(ts)s.totalmythscreentraf.png" width="420" height="420">
            </a>
            <a href="img.%(ts)s.totalmythfiletraf.png">
            <img src="img.%(ts)s.totalmythfiletraf.png" width="420" height="420">
            </a>
            </div>
            """ % {"ts": ts}

        print >>output, """
            </div>
            """
        pylab.figure(figsize=(8,8))
        pylab.title("Total Traffic for all clients\n%s" % (experiment["timestamp"]))
        pylab.xlabel("Execution timeline")
        pylab.ylabel("Traffic (bytes)")
        for client, timeline, traf in total_trafs:
            pylab.plot(timeline, traf, label="Total traffic for %s" % client)
        pylab.legend()
        pylab.grid()
        pylab.savefig("img.%s.totaltraf.png" % (ts), format="png")

        pylab.figure(figsize=(8,8))
        pylab.title("Total Screen traffic for all clients\n%s" % (experiment["timestamp"]))
        pylab.xlabel("Execution timeline")
        pylab.ylabel("Traffic (bytes)")
        for client, timeline, traf in myth_traf_screen:
            pylab.plot(timeline, traf, label="Screen traffic for %s" % client)
        pylab.legend()
        pylab.grid()
        pylab.savefig("img.%s.totalmythscreentraf.png" % (ts), format="png")

        pylab.figure(figsize=(8,8))
        pylab.title("Total SendFile traffic for all clients\n%s" % (experiment["timestamp"]))
        pylab.xlabel("Execution timeline")
        pylab.ylabel("Traffic (bytes)")
        for client, timeline, traf in myth_traf_file:
            pylab.plot(timeline, traf, label="File traffic for %s" % client)
        pylab.legend()
        pylab.grid()
        pylab.savefig("img.%s.totalmythfiletraf.png" % (ts), format="png")
        curexperiment += 1
# }}}


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
    output = open("report.html", "w")
    if experiments:
        generate_report(experiments, output=output)
    output.close()

    # gera o css
    css = open("style.css", "w")
    print >>css, CSS_TEMPLATE
    css.close()
    os.chdir(curdir)
