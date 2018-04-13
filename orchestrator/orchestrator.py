from flask import Flask, Response
from random import random
from apscheduler.schedulers.background import BackgroundScheduler
from json import loads
import grequests

app = Flask(__name__)

data_cpuload_time1 = [0] * 60
data_cpuload_time2 = [0] * 60
data_cpuload_time3 = [0] * 60
data_cpuload_time4 = [0] * 60
data_fgtload_time1 = [0] * 60
data_fgtload_time2 = [0] * 60
data_fgtload_time3 = [0] * 60
data_fgtload_time4 = [0] * 60
data_fgtload_time5 = [0] * 60
data_fgtload_time6 = [0] * 60
data_fgtload_time7 = [0] * 60
data_fgtload_time8 = [0] * 60

data_totalthroughput_ingress_time = [0] * 60
data_totalthroughput_egress_time = [0] * 60

data_fgtthroughput1_time = [0] * 60
data_fgtthroughput2_time = [0] * 60
data_fgtthroughput3_time = [0] * 60
data_fgtthroughput4_time = [0] * 60
data_fgtthroughput5_time = [0] * 60
data_fgtthroughput6_time = [0] * 60
data_fgtthroughput7_time = [0] * 60
data_fgtthroughput8_time = [0] * 60


def push_value_to_list(list, value):
    list.append(value)
    del list[0]


@app.route("/status", methods=['GET'])
def hello():
    global data_cpuload_time1

    push_value_to_list(data_fgtload_time1, random() * 100)
    push_value_to_list(data_fgtload_time2, random() * 100)
    push_value_to_list(data_fgtload_time3, random() * 100)
    push_value_to_list(data_fgtload_time4, random() * 100)
    push_value_to_list(data_fgtload_time5, random() * 100)
    push_value_to_list(data_fgtload_time6, random() * 100)
    push_value_to_list(data_fgtload_time7, random() * 100)
    push_value_to_list(data_fgtload_time8, random() * 100)

    push_value_to_list(data_totalthroughput_ingress_time, random() * 40)
    push_value_to_list(data_totalthroughput_egress_time, random() * 40)

    push_value_to_list(data_fgtthroughput1_time, random() * 10)
    push_value_to_list(data_fgtthroughput2_time, random() * 10 + 10)
    push_value_to_list(data_fgtthroughput3_time, random() * 10 + 20)
    push_value_to_list(data_fgtthroughput4_time, random() * 10 + 30)
    push_value_to_list(data_fgtthroughput5_time, random() * 10 + 40)
    push_value_to_list(data_fgtthroughput6_time, random() * 10 + 50)
    push_value_to_list(data_fgtthroughput7_time, random() * 10 + 60)
    push_value_to_list(data_fgtthroughput8_time, random() * 10 + 70)

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
        "fgtload_time7": """ + str(data_fgtload_time7) + """,
        "fgtload_time8": """ + str(data_fgtload_time8) + """,
        "totalthroughput_ingress_time": """ + str(data_totalthroughput_ingress_time) + """,
        "totalthroughput_egress_time": """ + str(data_totalthroughput_egress_time) + """,
        "fgtthroughput1_time": """ + str(data_fgtthroughput1_time) + """,
        "fgtthroughput2_time": """ + str(data_fgtthroughput2_time) + """,
        "fgtthroughput3_time": """ + str(data_fgtthroughput3_time) + """,
        "fgtthroughput4_time": """ + str(data_fgtthroughput4_time) + """,
        "fgtthroughput5_time": """ + str(data_fgtthroughput5_time) + """,
        "fgtthroughput6_time": """ + str(data_fgtthroughput6_time) + """,
        "fgtthroughput7_time": """ + str(data_fgtthroughput7_time) + """,
        "fgtthroughput8_time": """ + str(data_fgtthroughput8_time) + """
        }"""
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.data = newData
    return response


def request_cpu_load_from_nodes():

    urls = [
        'http://10.210.9.130:61208/api/2/cpu',
        'http://10.210.9.130:61208/api/2/cpu',
        'http://10.210.9.130:61208/api/2/cpu',
        'http://10.210.9.130:61208/api/2/cpu'
    ]

    rs = (grequests.get(u) for u in urls)

    results = grequests.map(rs)
    push_value_to_list(data_cpuload_time1, loads(results[0].content)['total'])
    push_value_to_list(data_cpuload_time2, loads(results[1].content)['total'])
    push_value_to_list(data_cpuload_time3, loads(results[2].content)['total'])
    push_value_to_list(data_cpuload_time4, loads(results[3].content)['total'])


cron = BackgroundScheduler(daemon=True)
cron.add_job(request_cpu_load_from_nodes, 'interval', seconds=4)
cron.start()
