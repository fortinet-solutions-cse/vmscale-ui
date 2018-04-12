from flask import Flask, jsonify, Response
from random import random

app = Flask(__name__)

data_cputime1 = [1, 12, 23, 45, 46, 57, 46, 32, 12, 1, 12, 23, 45, 46, 57, 46, 32, 12, 1, 12, 23, 45, 46, 57, 46, 32, 12]
data_cputime2 = [12, 32, 46, 57, 46, 45, 23, 12, 1]
data_cputime3 = [12, 32, 46, 57, 46, 45, 23, 12, 1]
data_cputime4 = [12, 32, 46, 57, 46, 45, 23, 12, 1]


@app.route("/status", methods=['GET'])
def hello():
    global data_cputime1

    print("HOLA")
    remove = data_cputime1[1:len(data_cputime1)]
    print(remove)
    remove.append(random()*100)
    print(remove)
    data_cputime1 = remove

    print(data_cputime1)
    newData = """{
        "cputime1": """ + str(data_cputime1) + """,
        "cputime2": """ + str(data_cputime2) + """,
        "cputime3": """ + str(data_cputime3) + """,
        "cputime4": """ + str(data_cputime4) + """
        }"""
    response = Response()
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.data = newData
    return response
