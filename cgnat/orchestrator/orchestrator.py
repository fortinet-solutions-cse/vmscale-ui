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
import html2text

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
    'https://10.210.14.35/']

# URLs to access hypervisor REST API (cpu load)
urls_hypervisors = [
    'http://10.210.14.18:61208/api/2/cpu',
    'http://10.210.14.19:61208/api/2/cpu',
    'http://10.210.14.6:61208/api/2/cpu']

# Address of the hypervisor of each fortigate
fgt_hypervisors = [
    '10.210.14.18',
    '10.210.14.19',
    '10.210.14.6']

url_cgnatmapper = 'http://10.210.9.133:8080'

FTS1_IP = "10.210.1.50"
FTS2_IP = "10.210.1.29"

FTS1_CASE_ID = '5bfd52a1edc8ea03e7691ded'
FTS2_CASE_ID = '5b02d8acac929f0348c9c9d0'
FTS_CPS_PER_VM = 5200

TIMEOUT = 3
POLL_INTERVAL = 4
USER_FGT = 'admin'
PASSWORD_FGT = ''
USERNAME_HYPERVISOR = 'root'
KEEP_DATA = 1

MAX_NUMBER_OF_SAMPLES = 300

VMS_RUNNING = 1

TOP_IP_LIMIT = 200
PUBLIC_SUBNET_PREFIX = '64.64.84.'  # IP Pools will be contained in PUBLIC_SUBNET_PREFIX.1 up to PUBLIC_SUBNET_PREFIX.TOP_IP_LIMIT

BANDWIDTH_VALUE = 0
LAST_BANDWITH_VALUE = 0

AUTO_SPAWN = True

DPID = '00000090fb64cce9'

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

returned_str = ""


def push_value_to_list(list, value):
    list.append(float("{0:.2f}".format(value)))
    if list[0] <= -1 or not KEEP_DATA or len(list) > MAX_NUMBER_OF_SAMPLES:
        del list[0]


@app.route("/start_vm", methods=['POST'])
def start_vm():

    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')

    try:
        fgt_id = request.args.get('fgt')
        fgt_id = int(fgt_id)

        response.data = _start_vm(fgt_id, auto_throughput=False)
        return response
    except:
        response.data = traceback.format_exc()
        return response


def _start_vm(fgt_id, auto_throughput=True):

    global returned_str
    returned_str = ""
    try:
        returned_str = execute_start_vm(fgt_id) + "<!--status:10%-->"

        fgt_contacted = False
        counter = 0
        while not fgt_contacted and counter < 60:
            try:
                results = requests.post(urls_fgt[fgt_id - 1] + '/logincheck',
                                        data='username=admin&secretkey=&ajax=1',
                                        verify=False,
                                        timeout=TIMEOUT)
                fgt_contacted = (results.status_code == 200 or counter >= 40)
            except:
                print("Monitoring FortiGate startup (%s). Attempt: %d" % (urls_fgt[fgt_id - 1], counter))
            counter += 1
            time.sleep(1)

        returned_str += execute_add_device(fgt_id) + "<!--status:60%-->"

        returned_str += execute_rebalance_public_ips() + "<!--status:70%-->"

        # Increase traffic load FTS1
        if auto_throughput:
            time.sleep(3)
            headers = {
                'Content-Type': "application/json",
            }

            url_fts = "http://" + FTS1_IP + "/api/networkLimit/modify"
            fts_data = '{"config": { \
                        "SpeedLimit": ' + str(fgt_id * FTS_CPS_PER_VM / 2) + ', \
                        "RampUpSecond": "0", \
                        "RampDownSecond": "0", \
                        "TestType": "HttpCps", \
                        "LimitType": "speed"}, \
                        "order": 0}'

            results = requests.post(url_fts,
                                    data=fts_data,
                                    headers=headers,
                                    timeout=TIMEOUT)

            returned_str += "<br><b>FortiTester1 response (code): </b>" + str(results.status_code)
            returned_str += "<br><b>FortiTester1 response (content): </b>" + \
                            str(dumps(loads(results.content.decode('utf-8')),
                                      indent=4,
                                      sort_keys=True).replace('\n', '<br>').replace(' ', '&nbsp;')) + "<!--status:85%-->"

            # Increase traffic load FTS2
            url_fts = "http://" + FTS2_IP + "/api/networkLimit/modify"
            results = requests.post(url_fts,
                                    data=fts_data,
                                    headers=headers,
                                    timeout=TIMEOUT)

            returned_str += "<br><b>FortiTester2 response (code): </b>" + str(results.status_code)
            returned_str += "<br><b>FortiTester2 response (content): </b>" + \
                            str(dumps(loads(results.content.decode('utf-8')),
                                      indent=4,
                                      sort_keys=True).replace('\n', '<br>').replace(' ', '&nbsp;')) + "<!--status:100%-->"

        return returned_str

    except:
        return returned_str + traceback.format_exc()


@app.route("/stop_vm", methods=['POST'])
def stop_vm():

    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')

    try:
        fgt_id = request.args.get('fgt')
        fgt_id = int(fgt_id)
        
        response.data = _stop_vm(fgt_id, auto_throughput=False)
        return response
    except:
        response.data = traceback.format_exc()
        return response


def _stop_vm(fgt_id, auto_throughput=True):
    global returned_str
    returned_str = ""

    try:
        if auto_throughput:
            # Decrease traffic load FTS1
            headers = {
                'Content-Type': "application/json",
            }

            url_fts = "http://" + FTS1_IP + "/api/networkLimit/modify"
            fts_data = '{"config": { \
                        "SpeedLimit": ' + str((fgt_id - 1) * FTS_CPS_PER_VM / 2) + ', \
                        "RampUpSecond": "0", \
                        "RampDownSecond": "0", \
                        "TestType": "HttpCps", \
                        "LimitType": "speed"}, \
                        "order": 0}'

            results = requests.post(url_fts,
                                    data=fts_data,
                                    headers=headers,
                                    timeout=TIMEOUT)

            returned_str = "<b>FortiGate id: </b>" + str(fgt_id) + "<br>" + \
                        "<b>FortiTester1 response (code): </b>" + str(results.status_code) + \
                        "<br><b>FortiTester1 response (content): </b>" + \
                        str(dumps(loads(results.content.decode('utf-8')),
                                  indent=4,
                                  sort_keys=True).replace('\n', '<br>').replace(' ', '&nbsp;')) + "<!--status:20%-->"

            # Decrease traffic load FTS2
            url_fts = "http://" + FTS2_IP + "/api/networkLimit/modify"

            results = requests.post(url_fts,
                                    data=fts_data,
                                    headers=headers,
                                    timeout=TIMEOUT)

            returned_str += "<b>FortiTester2 response (code): </b>" + str(results.status_code) + \
                            "<br><b>FortiTester2 response (content): </b>" + \
                            str(dumps(loads(results.content.decode('utf-8')),
                                      indent=4,
                                      sort_keys=True).replace('\n', '<br>').replace(' ', '&nbsp;')) + "<!--status:40%-->"
            time.sleep(1)

        returned_str += execute_remove_device(fgt_id) + "<!--status:60%-->"

        time.sleep(5)

        # StopVm
        returned_str += execute_stop_vm(fgt_id) + "<!--status:80%-->"

        returned_str += execute_rebalance_public_ips() + "<!--status:100%-->"
        return returned_str

    except:
        return returned_str + traceback.format_exc()


@app.route("/start_traffic", methods=['POST'])
def start_traffic():
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')

    # Login FTS1
    url = "http://" + FTS1_IP + "/api/user/login"

    payload = '{ "name":"admin", "password":"" }'
    headers = {"Content-Type": "application/json",
               "Cache-Control": "no-cache"}

    result_login_fts1 = requests.post(url,
                                      data=payload,
                                      timeout=TIMEOUT,
                                      headers=headers,
                                      verify=False)

    # Login FTS2
    url = "http://" + FTS2_IP + "/api/user/login"

    result_login_fts2 = requests.post(url,
                                      data=payload,
                                      timeout=TIMEOUT,
                                      headers=headers,
                                      verify=False)

    # Start case FTS1
    url = "http://" + FTS1_IP + "/api/case/" + FTS1_CASE_ID + "/start"

    if result_login_fts1.status_code == 200:
        result_start_fts1 = requests.get(url,
                                         timeout=TIMEOUT,
                                         cookies=result_login_fts1.cookies,
                                         verify=False)

        if result_start_fts1.status_code == 200:
            returned_str = "<b>FortiTester 1.</b> Traffic started successfully."
        else:
            returned_str = "<b>Error:</b> Could not start traffic in FortiTester1. <br>" + \
                           " Code: " + str(result_start_fts1.status_code) + " Text: " + str(result_start_fts1.text)
    else:
        returned_str = "<b>Error:</b> Could not log in to FortiTester1. <br> " + \
                       " Code: " + str(result_login_fts1.status_code) + " Text: " + str(result_login_fts1.text)

    # Start case FTS2
    url = "http://" + FTS2_IP + "/api/case/" + FTS2_CASE_ID + "/start"

    if result_login_fts2.status_code == 200:
        result_start_fts2 = requests.get(url,
                                         timeout=TIMEOUT,
                                         cookies=result_login_fts2.cookies,
                                         verify=False)

        if result_start_fts2.status_code == 200:
            returned_str += "<br><b>FortiTester 2.</b> Traffic started successfully."
        else:
            returned_str += "<br><b>Error:</b> Could not start traffic in FortiTester2. <br>" + \
                            " Code: " + str(result_start_fts2.status_code) + " Text: " + str(result_start_fts2.text)
    else:
        returned_str += "<br><b>Error:</b> Could not log in to FortiTester2. <br> " + \
                        " Code: " + str(result_login_fts2.status_code) + " Text: " + str(result_login_fts2.text)

    # Logout FTS1
    url = "http://" + FTS1_IP + "/api/user/logout"

    result_logout_fts1 = requests.get(url,
                                      timeout=TIMEOUT,
                                      cookies=result_login_fts1.cookies,
                                      verify=False)

    if result_logout_fts1.status_code != 200:
        returned_str += "<br> <b>Note:</b> User was not logged out of FortiTester1."

    # Logout FTS2
    url = "http://" + FTS2_IP + "/api/user/logout"

    result_logout_fts2 = requests.get(url,
                                      timeout=TIMEOUT,
                                      cookies=result_login_fts2.cookies,
                                      verify=False)

    if result_logout_fts2.status_code != 200:
        returned_str += "<br> <b>Note:</b> User was not logged out of FortiTester2."

    response.data = returned_str

    return response


@app.route("/stop_traffic", methods=['POST'])
def stop_traffic():
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')

    # Login FTS1
    url = "http://" + FTS1_IP + "/api/user/login"

    payload = '{ "name":"admin", "password":"" }'
    headers = {"Content-Type": "application/json",
               "Cache-Control": "no-cache"}

    result_login_fts1 = requests.post(url,
                                      data=payload,
                                      timeout=TIMEOUT,
                                      headers=headers,
                                      verify=False)

    # Login FTS2
    url = "http://" + FTS2_IP + "/api/user/login"

    result_login_fts2 = requests.post(url,
                                      data=payload,
                                      timeout=TIMEOUT,
                                      headers=headers,
                                      verify=False)

    # Stop case FTS1
    url = "http://" + FTS1_IP + "/api/case/stop"

    if result_login_fts1.status_code == 200:
        result_start_fts1 = requests.get(url,
                                         timeout=TIMEOUT,
                                         cookies=result_login_fts1.cookies,
                                         verify=False)

        if result_start_fts1.status_code == 200:
            returned_str = "<b>FortiTester 1</b>: Traffic stopped succesfully. <br>"
        else:
            returned_str = "<b>Error:</b> Could not stop traffic in FortiTester1. <br>" + \
                           " Code: " + str(result_start_fts1.status_code) + " Text: " + result_start_fts1.text
    else:
        returned_str = "<b>Error:</b> Could not log in to FortiTester1. <br> " + \
                       " Code: " + str(result_login_fts1.status_code) + " Text: " + result_login_fts1.text

    # Stop case FTS2
    url = "http://" + FTS2_IP + "/api/case/stop"

    if result_login_fts2.status_code == 200:
        result_start_fts2 = requests.get(url,
                                         timeout=TIMEOUT,
                                         cookies=result_login_fts2.cookies,
                                         verify=False)

        if result_start_fts2.status_code == 200:
            returned_str += "<b>FortiTester 2</b>: Traffic stopped succesfully"
        else:
            returned_str += "<b>Error:</b> Could not stop traffic in FortiTester2. <br>" + \
                            " Code: " + str(result_start_fts2.status_code) + " Text: " + result_start_fts2.text
    else:
        returned_str += "<b>Error:</b> Could not log in to FortiTester2. <br> " + \
                        " Code: " + str(result_login_fts2.status_code) + " Text: " + result_login_fts2.text

    # Logout FTS1
    url = "http://" + FTS1_IP + "/api/user/logout"

    result_logout_fts1 = requests.get(url,
                                      timeout=TIMEOUT,
                                      cookies=result_login_fts1.cookies,
                                      verify=False)

    if result_logout_fts1.status_code != 200:
        returned_str += "<br> <b>Note:</b> User was not logged out of FortiTester1."

    # Logout FTS2
    url = "http://" + FTS2_IP + "/api/user/logout"

    result_logout_fts2 = requests.get(url,
                                      timeout=TIMEOUT,
                                      cookies=result_login_fts2.cookies,
                                      verify=False)

    if result_logout_fts2.status_code != 200:
        returned_str += "<br> <b>Note:</b> User was not logged out of FortiTester2."

    response.data = returned_str

    return response


@app.route("/reset_data", methods=['POST'])
def reset_data():
    global data_cpuload_time1, data_cpuload_time2, data_cpuload_time3, \
        data_cpuload_time4, data_fgtload_time1, data_fgtload_time2, \
        data_fgtload_time3, data_fgtload_time4, data_fgtload_time5, \
        data_fgtload_time6, data_totalthroughput_ingress_time, \
        data_totalthroughput_egress_time, data_fgtthroughput1_time, \
        data_fgtthroughput2_time, data_fgtthroughput3_time, \
        data_fgtthroughput4_time, data_fgtthroughput5_time, \
        data_fgtthroughput6_time

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

    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.data = "Records emptied"
    return response


@app.route("/keep_old_data", methods=['POST'])
def keep_old_data():
    keep_data = request.args.get('value')
    try:
        keep_data = int(keep_data)
    except:
        return "Error, identifier not recognized"

    print("Parameter received:", keep_data)

    global KEEP_DATA
    KEEP_DATA = keep_data

    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.data = "Keeping data: " + str(KEEP_DATA)
    return response


@app.route("/status", methods=['GET'])
def status():

    data = {"cpuload_time1": data_cpuload_time1,
            "cpuload_time2": data_cpuload_time2,
            "cpuload_time3": data_cpuload_time3,
            "cpuload_time4": data_cpuload_time4,
            "fgtload_time1": data_fgtload_time1,
            "fgtload_time2": data_fgtload_time2,
            "fgtload_time3": data_fgtload_time3,
            "fgtload_time4": data_fgtload_time4,
            "fgtload_time5": data_fgtload_time5,
            "fgtload_time6": data_fgtload_time6,
            "totalthroughput_ingress_time": data_totalthroughput_ingress_time,
            "totalthroughput_egress_time": data_totalthroughput_egress_time,
            "fgtthroughput1_time": data_fgtthroughput1_time,
            "fgtthroughput2_time": data_fgtthroughput2_time,
            "fgtthroughput3_time": data_fgtthroughput3_time,
            "fgtthroughput4_time": data_fgtthroughput4_time,
            "fgtthroughput5_time": data_fgtthroughput5_time,
            "fgtthroughput6_time": data_fgtthroughput6_time,
            "vms_running": VMS_RUNNING
            }

    vms_running_real = 0
    for k, v in data.items():
        if 'fgtload_time' in k:
            if v[len(v)-1] != -1:
                vms_running_real += 1
    data['vms_running_real'] = vms_running_real

    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.data = dumps(data)
    return response


@app.route("/panic", methods=['POST'])
def panic():

    global returned_str
    returned_str = ""

    try:
        global VMS_RUNNING

        response = Response()
        response.headers.add('Access-Control-Allow-Origin', '*')

        returned_str = "<b>Panic log:</b> <br>" + str(stop_traffic().data.decode('ascii').strip('\n')) + "<br><br> <!--status:10%-->"

        for vm in reversed(range(2, len(urls_fgt)+1)):
            returned_str += "<b>Orchestrating removal for device: </b>" + str(vm) + execute_remove_device(vm) + "<br>"

        returned_str += "<b>Orchestrating creation for device:</b> 1 " + execute_add_device(1) + "<br> <!--status:30%-->"

        for vm in range(2, len(urls_fgt)+1):
            returned_str += execute_stop_vm(vm)

        returned_str += execute_start_vm(1) + "<!--status:50%-->"

        VMS_RUNNING = 1
        
        returned_str += execute_rebalance_public_ips() + "<!--status:70%-->"

        time.sleep(5)

        returned_str += "<br><b>Resetting charts:</b> " + str(reset_data().data.decode('ascii').strip('\n')) + "<!--status:100%-->"

        global KEEP_DATA
        KEEP_DATA = 1

        response.data = returned_str
        return response

    except:

        response.data = returned_str + traceback.format_exc()
        return response


@app.route("/progress_report", methods=['GET'])
def progress_report():
    global returned_str

    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.data = returned_str

    return response


@app.route("/synchronize_counters", methods=['POST'])
def synchronize_counters():

    global VMS_RUNNING

    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')

    data = {"fgtload_time1": data_fgtload_time1,
            "fgtload_time2": data_fgtload_time2,
            "fgtload_time3": data_fgtload_time3,
            "fgtload_time4": data_fgtload_time4,
            "fgtload_time5": data_fgtload_time5,
            "fgtload_time6": data_fgtload_time6
            }

    vms_running_real = 0
    for k, v in data.items():
        if 'fgtload_time' in k:
            if v[len(v)-1] != -1:
                vms_running_real += 1

    VMS_RUNNING = vms_running_real
    response.data = str(VMS_RUNNING)
    return response


@app.route("/update_bandwidth", methods=['POST'])
def update_bandwidth():

    global BANDWIDTH_VALUE
    global AUTO_SPAWN
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    try:
        BANDWIDTH_VALUE = int(request.args.get('value'))
        AUTO_SPAWN = request.args.get('auto_spawn') == "true"
        response.status_code = 200

    except:
        response.status_code = 500
        print("No value returned")
        return response

    print("Bandwidth change request set to: " + str(BANDWIDTH_VALUE) +
          " and auto-spawn: " + str(AUTO_SPAWN))
    return response


def request_cpu_load_from_nodes():
    # ******************************
    # Get Values from Hypervisors
    # ******************************

    global urls_hypervisors

    rs = (grequests.get(u, timeout=TIMEOUT) for u in urls_hypervisors)

    results = grequests.map(rs)
    if len(results) > 0:
        if results[0] is not None: push_value_to_list(data_cpuload_time1,
                                                      loads(results[0].content.decode('utf-8'))['total'])
    if len(results) > 1:
        if results[1] is not None: push_value_to_list(data_cpuload_time2,
                                                      loads(results[1].content.decode('utf-8'))['total'])
    if len(results) > 2:
        if results[2] is not None: push_value_to_list(data_cpuload_time3,
                                                      loads(results[2].content.decode('utf-8'))['total'])
    if len(results) > 3:
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
    # Get Values from DSO CGNATMapper
    # ********************************

    global url_cgnatmapper

    # Get port statistics

    results = requests.get(url_cgnatmapper + '/v1/switch_stats/switches/' + DPID + '/port_stats',
                           timeout=TIMEOUT)

    port_stats = loads(results.content.decode('utf-8'))

    bps = {}

    for port in port_stats:
        bps[port['id']] = (port['tx_bytes'] - port['last']['tx_bytes'] +
                           port['rx_bytes'] - port['last']['rx_bytes']) / \
                          (port['timestamp'] - port['last']['timestamp'])

    # Instead of port3 (which is faulty) we use 21-24
    # Instead of port4 we use 25-28
    push_value_to_list(data_totalthroughput_ingress_time,
                       bps[1] / 1000000000 * 8)
    push_value_to_list(data_totalthroughput_egress_time,
                       bps[2] / 1000000000 * 8)

    push_value_to_list(data_fgtthroughput1_time, (bps[31] + bps[32]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput2_time, (bps[27] + bps[28]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput3_time, (bps[9] + bps[10]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput4_time, (bps[11] + bps[12]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput5_time, (bps[13] + bps[14]) / 2000000000 * 8)
    push_value_to_list(data_fgtthroughput6_time, (bps[15] + bps[16]) / 2000000000 * 8)


def execute_start_vm(fgt_id):
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.connect(fgt_hypervisors[fgt_id - 1], username=USERNAME_HYPERVISOR)
    _, ssh_stdout, ssh_stderr = ssh.exec_command(
        "LIBVIRT_DEFAULT_URI=qemu:///system virsh start fgt-cgnat-" + str(fgt_id))

    stdout = ssh_stdout.read().decode('ascii').strip('\n')
    stderr = ssh_stderr.read().decode('ascii').strip('\n')

    # if ssh_stdout.channel.recv_exit_status() == 0:
    global VMS_RUNNING
    VMS_RUNNING += 1

    returned_str = "<b>FortiGate id: </b>" + str(fgt_id) + "<br>" + \
                   "<b>VM instantiation: </b>" + str(stderr).replace('\\n', '<br>') + \
                   ":" + str(stdout).replace('\\n', '<br>') + "<br>"

    return returned_str


def execute_stop_vm(fgt_id):
    ssh = paramiko.SSHClient()
    ssh.load_system_host_keys()
    ssh.connect(fgt_hypervisors[fgt_id - 1], username=USERNAME_HYPERVISOR)
    _, ssh_stdout, ssh_stderr = ssh.exec_command(
        "LIBVIRT_DEFAULT_URI=qemu:///system virsh shutdown fgt-cgnat-" + str(fgt_id))

    stdout = ssh_stdout.read().decode('ascii').strip('\n')
    stderr = ssh_stderr.read().decode('ascii').strip('\n')

    #if ssh_stdout.channel.recv_exit_status() == 0:
    global VMS_RUNNING
    VMS_RUNNING -= 1

    returned_str = "<b>FortiGate id: </b>" + str(fgt_id) + "<br>" + \
                   "<b>VM shutdown: </b>" + str(stderr).replace('\\n', '<br>') + \
                   ":" + str(stdout).replace('\\n', '<br>') + "<br>"

    return returned_str


def execute_add_device(fgt_id):

    # Send "add device" request: modify every device config and add a new one
    returned_str = ""
    private_port = [31, 27]
    public_port = [32, 28]
    for device in range(1, fgt_id+1):

        lower_limit = int(((device-1)*TOP_IP_LIMIT/fgt_id)+1)
        upper_limit = int(device*TOP_IP_LIMIT/fgt_id)

        device_data = {
            "private_port": private_port[device - 1],
            "public_port": public_port[device - 1],
            "public_ranges": [[PUBLIC_SUBNET_PREFIX + str(lower_limit), PUBLIC_SUBNET_PREFIX + str(upper_limit)]]
        }

        if device == fgt_id:
            returned_str += "<br><b> Adding device to NoviFlow: </b>" + str(device)
            results = requests.post(url_cgnatmapper + '/v1/devices',
                                    data=dumps(device_data),
                                    timeout=TIMEOUT)
        else:
            returned_str += "<br><b> Modifying device in NoviFlow: </b>" + str(device)
            results = requests.put(url_cgnatmapper + '/v1/devices/' + str(device),
                                   data=dumps(device_data),
                                   timeout=TIMEOUT)

        returned_str += "<br><b>NoviFlow response (code): </b>" + str(results.status_code)

        returned_str += "<br><b>NoviFlow response (content): </b>" + \
                        str(html2text.html2text(results.content.decode('utf-8'))) 

    return returned_str + "<br>"


def execute_remove_device(fgt_id):

    # Send "remove device" request
    returned_str = ""
    private_port = [31, 27, 23]
    public_port = [32, 28, 24]
    for device in range(1, fgt_id+1):

        lower_limit = int(((device-1)*TOP_IP_LIMIT/(fgt_id - 1))+1)
        upper_limit = int(device*TOP_IP_LIMIT/(fgt_id - 1))

        device_data = {
            "private_port": private_port[device - 1],
            "public_port": public_port[device - 1],
            "public_ranges": [[PUBLIC_SUBNET_PREFIX + str(lower_limit), PUBLIC_SUBNET_PREFIX + str(upper_limit)]]
        }

        if device == fgt_id:
            returned_str += "<br><b> Deleting device to NoviFlow: </b>" + str(device)
            results = requests.delete(url_cgnatmapper + '/v1/devices/' + str(device),
                                      timeout=TIMEOUT)
        else:
            returned_str += "<br><b> Modifying device in NoviFlow: </b>" + str(device)
            results = requests.put(url_cgnatmapper + '/v1/devices/' + str(device),
                                   data=dumps(device_data),
                                   timeout=TIMEOUT)

        returned_str += "<br><b>NoviFlow response (code): </b>" + str(results.status_code) 

    return returned_str + "<br>"


def execute_rebalance_public_ips():

    global returned_str
    returned_str = ""

    print("Rebalancing public ip pool. Number of VMs running: %d" % VMS_RUNNING)
    for vmId in range(1, VMS_RUNNING+1):
        lower_limit = int(((vmId-1)*TOP_IP_LIMIT/VMS_RUNNING)+1)
        upper_limit = int(vmId*TOP_IP_LIMIT/VMS_RUNNING)
        print("New range for vm: %d Range: %d..%d " % (vmId, lower_limit, upper_limit))

        results_login = requests.post(urls_fgt[vmId-1] + '/logincheck',
                                      data='username=admin&secretkey=&ajax=1',
                                      verify=False,
                                      timeout=TIMEOUT)
        xsrfToken = results_login.cookies['ccsrftoken']
        jar = results_login.cookies

        target_data = {'startip': PUBLIC_SUBNET_PREFIX + str(lower_limit),
                       'endip': PUBLIC_SUBNET_PREFIX + str(upper_limit)}

        headers = {"Content-Type": "application/json",
                   "x-csrftoken": xsrfToken.strip('"')}

        results_put_ippool = requests.put(urls_fgt[vmId-1] + 'api/v2/cmdb/firewall/ippool/dynIP?vdom=root',
                                          data=dumps(target_data),
                                          verify=False,
                                          headers=headers,
                                          cookies=jar,
                                          timeout=TIMEOUT)

        results_logout = requests.post(urls_fgt[vmId-1] + 'logout',
                                       verify=False,
                                       headers=headers,
                                       cookies=jar,
                                       timeout=TIMEOUT)

        returned_str += "<br><b>FortiGate %d. Re-balancing IPs. Responses: <br>     Login:</b> %s <b>Set IPPool:</b> %s <b>(Range:</b> %d..%d <b>) Logout:</b> %s" % \
            (vmId, str(results_login.status_code), str(results_put_ippool.status_code), lower_limit, upper_limit, str(results_logout.status_code))

    return returned_str


def execute_bandwith_change():

    global BANDWIDTH_VALUE, LAST_BANDWITH_VALUE, VMS_RUNNING
    returned_str = ""

    if LAST_BANDWITH_VALUE != BANDWIDTH_VALUE:
        LAST_BANDWITH_VALUE = BANDWIDTH_VALUE

        reqid = BANDWIDTH_VALUE

        # Send new bandwith limit to FTS
        try:
            headers = {
                'Content-Type': "application/json",
            }

            url_fts = "http://" + FTS1_IP + "/api/networkLimit/modify"
            fts_data = '{"config": { \
                        "BandWidthLimit": ' + str(reqid * 1000) + ', \
                        "PPSLimit": 0, \
                        "TestType": "HttpCps"}, \
                        "order": 0}'

            results = requests.post(url_fts,
                                    data=fts_data,
                                    headers=headers,
                                    timeout=TIMEOUT)

            returned_str += "<br><b>FortiTester1 response (code): </b>" + str(results.status_code)
            returned_str += "<br><b>FortiTester1 response (content): </b>" + \
                            str(dumps(loads(results.content.decode('utf-8')),
                                      indent=4,
                                      sort_keys=True).replace('\n', '<br>').replace(' ', '&nbsp;')) + "<!--status:85%-->"
        except:
            returned_str += traceback.format_exc()

        if not AUTO_SPAWN:
            return returned_str

        # Scale out/in according to new value

        # TODO: Put this in two separate loops for scaling out/in

        # TODO: Consider use a previous fixed BANDWITH_VALUE to avoid interferences during exec
        if BANDWIDTH_VALUE > 15 and VMS_RUNNING <= 1:
            print("Creating fgt: " + str(2) + " to service " + str(reqid) + " Gbps")
            _start_vm(2, auto_throughput=False)
        if BANDWIDTH_VALUE > 35 and VMS_RUNNING <= 2:
            print("Creating fgt: " + str(3) + " to service " + str(reqid) + " Gbps")
            _start_vm(3, auto_throughput=False)
        if BANDWIDTH_VALUE > 55 and VMS_RUNNING <= 3:
            print("Creating fgt: " + str(4) + " to service " + str(reqid) + " Gbps")
            _start_vm(4, auto_throughput=False)
        if BANDWIDTH_VALUE > 75 and VMS_RUNNING <= 4:
            print("Creating fgt: " + str(5) + " to service " + str(reqid) + " Gbps")
            _start_vm(5, auto_throughput=False)
        if BANDWIDTH_VALUE > 95 and VMS_RUNNING <= 5:
            print("Creating fgt: " + str(6) + " to service " + str(reqid) + " Gbps")
            _start_vm(6, auto_throughput=False)

        if BANDWIDTH_VALUE < 95 and VMS_RUNNING >= 6:
            print("Destroying fgt: " + str(6) + " to service " + str(reqid) + " Gbps")
            _stop_vm(6, auto_throughput=False)
        if BANDWIDTH_VALUE < 75 and VMS_RUNNING >= 5:
            print("Destroying fgt: " + str(5) + " to service " + str(reqid) + " Gbps")
            _stop_vm(5, auto_throughput=False)
        if BANDWIDTH_VALUE < 55 and VMS_RUNNING >= 4:
            print("Destroying fgt: " + str(4) + " to service " + str(reqid) + " Gbps")
            _stop_vm(4, auto_throughput=False)
        if BANDWIDTH_VALUE < 35 and VMS_RUNNING >= 3:
            print("Destroying fgt: " + str(3) + " to service " + str(reqid) + " Gbps")
            _stop_vm(3, auto_throughput=False)
        if BANDWIDTH_VALUE < 15 and VMS_RUNNING >= 2:
            print("Destroying fgt: " + str(2) + " to service " + str(reqid) + " Gbps")
            _stop_vm(2, auto_throughput=False)

    return returned_str


cron = BackgroundScheduler(daemon=True)
cron.add_job(request_cpu_load_from_nodes, 'interval', seconds=POLL_INTERVAL)
cron.add_job(execute_bandwith_change, 'interval', seconds=POLL_INTERVAL*2)
cron.start()
