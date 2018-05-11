#!/usr/bin/python3
from flask import Flask, Response, request, jsonify
from random import random
from apscheduler.schedulers.background import BackgroundScheduler
from json import loads, dumps
import grequests
import requests
import gevent
import paramiko
import traceback


# Note previous patch to avoid error with paramiko
# and grequests: https://github.com/paramiko/paramiko/issues/633

from gevent import monkey
import time

monkey.patch_all()

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# This requires glances to run on the hypervisors
# install the package and run: glances -w & disown
#
# Ensure ports are open in the server (CentOS 7):
# firewall-cmd --zone=public --permanent --add-port=61208/tcp
# firewall-cmd --reload


# Urls to access FGT REST API
urls_fgt = [
    'https://10.210.14.33/',
    'https://10.210.14.34/',
    'https://10.210.14.100/',
    'https://10.210.14.101/',
    'https://10.210.14.102/',
    'https://10.210.14.103/'
]

# URLs to access hypervisor REST API (cpu load)
urls_hypervisors = [
    'http://10.210.14.18:61208/api/2/cpu',
    'http://10.210.14.6:61208/api/2/cpu',
    'http://10.210.14.22:61208/api/2/cpu',
    'http://10.210.14.23:61208/api/2/cpu'
]

# Address of the hypervisor of each fortigate
fgt_hypervisors = [
    '10.210.14.18',
    '10.210.14.6',
    '10.210.14.22',
    '10.210.14.22',
    '10.210.14.23',
    '10.210.14.23',
    '127.0.0.1',
    '127.0.0.1'
]

url_cybermapper = 'http://10.210.9.132:8080'

FTS1_IP = "10.210.1.28"
FTS2_IP = "10.210.1.29"

FTS_CASE_ID = '5af4339cdfaa0f02ec656be4'
FTS_CPS_PER_VM = 5200

TIMEOUT = 3
POLL_INTERVAL = 4
USER_FGT = 'admin'
PASSWORD_FGT = ''
USERNAME_HYPERVISOR = 'root'

fgt_sessions = [requests.Session() for u in urls_fgt]

data_cpuload_time1 = [-1] * 60
data_cpuload_time2 = [-1] * 60
data_cpuload_time3 = [-1] * 60
data_cpuload_time4 = [-1] * 60
data_fgtload_time1 = [-1] * 60
data_fgtload_time2 = [-1] * 60
data_fgtload_time3 = [-1] * 60
data_fgtload_time4 = [-1] * 60
data_fgtload_time5 = [-1] * 60
data_fgtload_time6 = [-1] * 60

data_totalthroughput_ingress_time = [-1] * 60
data_totalthroughput_egress_time = [-1] * 60

data_fgtthroughput1_time = [-1] * 60
data_fgtthroughput2_time = [-1] * 60
data_fgtthroughput3_time = [-1] * 60
data_fgtthroughput4_time = [-1] * 60
data_fgtthroughput5_time = [-1] * 60
data_fgtthroughput6_time = [-1] * 60


def push_value_to_list(list, value):
    list.append(value)
    if list[0]<=0:
        del list[0]


@app.route("/start_vm", methods=['POST'])
def start_vm():
    fgt_id = request.args.get('fgt')
    try:
        fgt_id = int(fgt_id)
    except:
        return "Error, identifier not recognized"

    print("Parameter received:", fgt_id)

    try:
        response = Response()
        response.headers.add('Access-Control-Allow-Origin', '*')

        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.connect(fgt_hypervisors[fgt_id - 1], username=USERNAME_HYPERVISOR)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(
            "LIBVIRT_DEFAULT_URI=qemu:///system virsh start fortigate" + str(fgt_id))

        stdout = ssh_stdout.read().decode('ascii').strip('\n')
        stderr = ssh_stderr.read().decode('ascii').strip('\n')

        returned_str = "<b>FortiGate id: </b>" + str(fgt_id) + "<br>" + \
                       "<b>FortiGate VM instantiation: </b>" + str(stderr).replace('\\n', '<br>') + \
                       ":" + str(stdout).replace('\\n', '<br>') + "<br>"

        time.sleep(40)

        global url_cybermapper

        # Get dpid

        loadbal = requests.get(url_cybermapper + '/v1.0/loadbal',
                               timeout=TIMEOUT)

        # Use this notation '[*' to get the keys extracted into a list
        dpid = [*loads(loadbal.content.decode('utf-8')).keys()][0]

        # Send "add target" request
        target_data = '{ \
            "type": "pair", \
            "port_ingress": ' + str(fgt_id * 2 + 3) + ', \
            "port_egress": ' + str(fgt_id * 2 + 4) + ', \
            "id": "dpi' + str(fgt_id) + '" }'

        results = requests.post(url_cybermapper + '/v1.0/loadbal/' + dpid + '/0/targets',
                                data=target_data,
                                timeout=TIMEOUT)

        returned_str += "<b>NoviFlow response (code): </b>" + str(results.status_code)

        returned_str += "<br><b>NoviFlow response (content): </b>" + \
                        str(dumps(loads(results.content.decode('utf-8')),
                                  indent=4,
                                  sort_keys=True).replace('\n', '<br>').replace(' ', '&nbsp;'))

        # Increase traffic load
        time.sleep(5)

        headers = {
            'Content-Type': "application/json",
        }

        url_fts = "http://" + FTS1_IP + "/api/networkLimit/modify"
        fts_data = '{"config": { \
                       "SpeedLimit": ' + str(fgt_id * FTS_CPS_PER_VM) + ', \
                       "RampUpSecond": "0", \
                       "RampDownSecond": "0", \
                       "TestType": "HttpCps", \
                       "LimitType": "speed"}, \
                    "order": 0}'

        results = requests.post(url_fts,
                                data=fts_data,
                                headers=headers,
                                timeout=TIMEOUT)

        returned_str += "<br><b>FortiTester response (code): </b>" + str(results.status_code)
        returned_str += "<br><b>FortiTester response (content): </b>" + \
                        str(dumps(loads(results.content.decode('utf-8')),
                                  indent=4,
                                  sort_keys=True).replace('\n', '<br>').replace(' ', '&nbsp;'))

        response.data = returned_str
        return response

    except:
        response.data = returned_str + traceback.format_exc()
        return response


@app.route("/stop_vm", methods=['POST'])
def stop_vm():
    fgt_id = request.args.get('fgt')
    try:
        fgt_id = int(fgt_id)
    except:
        return "Error, identifier not recognized"

    print("Parameter received:", fgt_id)

    try:
        # Decrease traffic load
        headers = {
            'Content-Type': "application/json",
        }

        url_fts = "http://" + FTS1_IP + "/api/networkLimit/modify"
        fts_data = '{"config": { \
                       "SpeedLimit": ' + str((fgt_id - 1) * FTS_CPS_PER_VM) + ', \
                       "RampUpSecond": "0", \
                       "RampDownSecond": "0", \
                       "TestType": "HttpCps", \
                       "LimitType": "speed"}, \
                    "order": 0}'

        print(fts_data)

        results = requests.post(url_fts,
                                data=fts_data,
                                headers=headers,
                                timeout=TIMEOUT)

        returned_str = "<b>FortiGate id: </b>" + str(fgt_id) + "<br>" + \
                       "<b>FortiTester response (code): </b>" + str(results.status_code) + \
                       "<br><b>FortiTester response (content): </b>" + \
                       str(dumps(loads(results.content.decode('utf-8')),
                                 indent=4,
                                 sort_keys=True).replace('\n', '<br>').replace(' ', '&nbsp;'))

        time.sleep(1)

        global url_cybermapper

        # Get dpid

        loadbal = requests.get(url_cybermapper + '/v1.0/loadbal',
                               timeout=TIMEOUT)

        # Use this notation '[*' to get the keys extracted into a list
        dpid = [*loads(loadbal.content.decode('utf-8')).keys()][0]

        # Send "remove target" request
        results = requests.delete(url_cybermapper + '/v1.0/loadbal/' + dpid + '/0/targets/dpi' + str(fgt_id),
                                  timeout=TIMEOUT)

        returned_str += "<br><b>NoviFlow response (code): </b>" + str(results.status_code) + "<br>"

        time.sleep(10)
        # StopVm

        ssh = paramiko.SSHClient()
        ssh.load_system_host_keys()
        ssh.connect(fgt_hypervisors[fgt_id - 1], username=USERNAME_HYPERVISOR)
        ssh_stdin, ssh_stdout, ssh_stderr = ssh.exec_command(
            "LIBVIRT_DEFAULT_URI=qemu:///system virsh shutdown fortigate" + str(fgt_id))

        stdout = ssh_stdout.read().decode('ascii').strip('\n')
        stderr = ssh_stderr.read().decode('ascii').strip('\n')

        returned_str += "<b>FortiGate VM shutdown: </b>" + str(stderr).replace('\\n', '<br>') + \
                        ":" + str(stdout).replace('\\n', '<br>') + "<br>"

        response = Response()
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.data = returned_str

        return response

    except:
        response.data = returned_str + traceback.format_exc()
        return response



@app.route("/start_traffic", methods=['POST'])
def start_traffic():
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')

    # Login
    url = "http://" + FTS1_IP + "/api/user/login"

    payload = '{ "name":"admin", "password":"" }'
    headers = {"Content-Type": "application/json",
               "Cache-Control": "no-cache"}

    result_login = requests.post(url,
                                 data=payload,
                                 timeout=TIMEOUT,
                                 headers=headers,
                                 verify=False)

    # Start case
    url = "http://" + FTS1_IP + "/api/case/" + FTS_CASE_ID + "/start"

    if result_login.status_code == 200:
        result_start = requests.get(url,
                                    timeout=TIMEOUT,
                                    cookies=result_login.cookies,
                                    verify=False)

        if result_start.status_code == 200:
            response.data = "<b>Success.</b> Traffic started."
        else:
            response.data = "<b>Error:</b> Could not start traffic. <br>" + \
                            " Code: " + str(result_start.status_code) + " Text: " + result_start.text
    else:
        response.data = "<b>Error:</b> Could not log in to FortiTester. <br> " + \
                        " Code: " + str(result_login.status_code) + " Text: " + result_login.text

    # Logout
    url = "http://" + FTS1_IP + "/api/user/logout"

    result_start = requests.get(url,
                                timeout=TIMEOUT,
                                cookies=result_login.cookies,
                                verify=False)

    if result_start.status_code != 200:
        response.data += "<br> <b>Note:</b> User was not logged out."

    return response


@app.route("/stop_traffic", methods=['POST'])
def stop_traffic():
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')

    # Login
    url = "http://" + FTS1_IP + "/api/user/login"

    payload = '{ "name":"admin", "password":"" }'
    headers = {"Content-Type": "application/json",
               "Cache-Control": "no-cache"}

    result_login = requests.post(url,
                                 data=payload,
                                 timeout=TIMEOUT,
                                 headers=headers,
                                 verify=False)

    # Stop case
    url = "http://" + FTS1_IP + "/api/case/stop"

    if result_login.status_code == 200:
        result_start = requests.get(url,
                                    timeout=TIMEOUT,
                                    cookies=result_login.cookies,
                                    verify=False)

        if result_start.status_code == 200:
            response.data = "<b>Success.</b> Traffic stopped."
        else:
            response.data = "<b>Error:</b> Could not stop traffic. <br>" + \
                            " Code: " + str(result_start.status_code) + " Text: " + result_start.text
    else:
        response.data = "<b>Error:</b> Could not log in to FortiTester. <br> " + \
                        " Code: " + str(result_login.status_code) + " Text: " + result_login.text

    # Logout
    url = "http://" + FTS1_IP + "/api/user/logout"

    result_start = requests.get(url,
                                timeout=TIMEOUT,
                                cookies=result_login.cookies,
                                verify=False)

    if result_start.status_code != 200:
        response.data += "<br> <b>Note:</b> User was not logged out."

    return response


@app.route("/status", methods=['GET'])
def status():

    newData = """{
        "cpuload_time1": """ + str(data_cpuload_time1) + """,
        "cpuload_time2": """ + str(data_cpuload_time2) + """,
        "cpuload_time3": """ + str(data_cpuload_time3) + """,
        "cpuload_time4": """ + str(data_cpuload_time4) + """,
        "fgtload_time1": """ + str(data_fgtload_time1) + """,
        "fgtload_time2": """ + str(data_fgtload_time2) + """,
        "fgtload_time3": """ + str(data_fgtload_time3) + """,
        "fgtload_time4": """ + str(data_fgtload_time4) + """,
        "fgtload_time5": """ + str(data_fgtload_time5) + """,
        "fgtload_time6": """ + str(data_fgtload_time6) + """,
        "totalthroughput_ingress_time": """ + str(data_totalthroughput_ingress_time) + """,
        "totalthroughput_egress_time": """ + str(data_totalthroughput_egress_time) + """,
        "fgtthroughput1_time": """ + str(data_fgtthroughput1_time) + """,
        "fgtthroughput2_time": """ + str(data_fgtthroughput2_time) + """,
        "fgtthroughput3_time": """ + str(data_fgtthroughput3_time) + """,
        "fgtthroughput4_time": """ + str(data_fgtthroughput4_time) + """,
        "fgtthroughput5_time": """ + str(data_fgtthroughput5_time) + """,
        "fgtthroughput6_time": """ + str(data_fgtthroughput6_time) + """
        }"""
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.data = newData
    return response


def request_cpu_load_from_nodes():
    # ******************************
    # Get Values from Hypervisors
    # ******************************

    global urls_hypervisors

    rs = (grequests.get(u, timeout=TIMEOUT) for u in urls_hypervisors)

    results = grequests.map(rs)
    if len(results) >= 0:
        if results[0] is not None: push_value_to_list(data_cpuload_time1,
                                                      loads(results[0].content.decode('utf-8'))['total'])
        if results[1] is not None: push_value_to_list(data_cpuload_time2,
                                                      loads(results[1].content.decode('utf-8'))['total'])
        if results[2] is not None: push_value_to_list(data_cpuload_time3,
                                                      loads(results[2].content.decode('utf-8'))['total'])
        if results[3] is not None: push_value_to_list(data_cpuload_time4,
                                                      loads(results[3].content.decode('utf-8'))['total'])

    # ******************************
    # Get Values from FortiGates
    # ******************************

    global fgt_sessions
    global urls_fgt

    fgt_login_requests = [None] * len(urls_fgt)
    fgt_cpu_requests = [None] * len(urls_fgt)

    # First, request CPU data

    for i in range(len(fgt_sessions)):
        fgt_cpu_requests[i] = grequests.get(
            urls_fgt[i] + 'api/v2/monitor/system/resource/usage?resource=cpu&interval=1-min',
            session=fgt_sessions[i],
            headers=fgt_sessions[i].headers,
            timeout=TIMEOUT,
            verify=False)

    fgt_cpu_results = grequests.map(fgt_cpu_requests)

    # Check if request failed because of login
    # If failed, then login
    print("fgt_cpu_results:", fgt_cpu_results)

    reqs = []
    for i in range(len(fgt_sessions)):
        if fgt_cpu_results[i] is not None and fgt_cpu_results[i].status_code == 401:
            print("Login into FortiGate's REST API: ", i)
            fgt_login_requests[i] = grequests.post(urls_fgt[i] + 'logincheck',
                                                   data='username=' + USER_FGT + '&secretkey=' + PASSWORD_FGT + '&ajax=1',
                                                   session=fgt_sessions[i],
                                                   timeout=TIMEOUT,
                                                   verify=False)
            r = grequests.send(fgt_login_requests[i])
            reqs.append(r)
    gevent.joinall(reqs)

    # Only if request to get CPU was 200 OK then
    # get the value and push it to the list

    for i in range(len(fgt_cpu_results)):
        if fgt_cpu_results[i] and fgt_cpu_results[i].status_code == 200:
            try:
                push_value_to_list(globals()['data_fgtload_time' + str(i + 1)],
                                   loads(fgt_cpu_results[i].content.decode('utf-8'))['results']['cpu'][0]['current'])
            except:
                print("Error getting data from FortiGate:", i)
        else:
            print("FGT request was not ok:", i)
            if fgt_cpu_results[i] is not None:
                print("  -> result: ", fgt_cpu_results[i].status_code)
            push_value_to_list(globals()['data_fgtload_time' + str(i + 1)], -1)

    # ********************************
    # Get Values from DSO CyberMapper
    # ********************************

    global url_cybermapper

    # Get dpid

    loadbal = requests.get(url_cybermapper + '/v1.0/loadbal',
                           timeout=TIMEOUT)

    # Use this notation '[*' to get the keys extracted into a list
    dpid = [*loads(loadbal.content.decode('utf-8')).keys()][0]

    # Get port statistics

    results = requests.get(url_cybermapper + '/v1.0/switch_stats/switches/' + dpid + '/port_stats',
                           timeout=TIMEOUT)

    port_stats = loads(results.content.decode('utf-8'))

    bps = {}

    for port in port_stats:
        bps[port['id']] = (port['tx_bytes'] - port['last']['tx_bytes'] +
                           port['rx_bytes'] - port['last']['rx_bytes']) / \
                          (port['timestamp'] - port['last']['timestamp'])

    push_value_to_list(data_totalthroughput_ingress_time, (bps[1] + bps[3]) / 1000000000 * 8)
    push_value_to_list(data_totalthroughput_egress_time, (bps[2] + bps[4]) / 1000000000 * 8)

    push_value_to_list(data_fgtthroughput1_time, (bps[5] + bps[6]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput2_time, (bps[7] + bps[8]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput3_time, (bps[9] + bps[10]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput4_time, (bps[11] + bps[12]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput5_time, (bps[13] + bps[14]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput6_time, (bps[15] + bps[16]) / 2000000000 * 8)


cron = BackgroundScheduler(daemon=True)
cron.add_job(request_cpu_load_from_nodes, 'interval', seconds=POLL_INTERVAL)
cron.start()
