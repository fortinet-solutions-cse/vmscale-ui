# GET ippool
import requests

url = "http://192.168.122.40/api/v2/cmdb/firewall/ippool"

headers = {
    'Content-Type': "application/json",
    'cache-control': "no-cache"
    }

response = requests.request("GET", url, headers=headers)

print(response.text)


# POST new ippool

import requests

url = "https://192.168.122.40/api/v2/cmdb/firewall/ippool"

payload = "{\n    \"name\": \"dynip2\",\n    \"type\": \"overload\",\n    \"startip\": \"64.84.84.51\",\n    \"endip\": \"64.84.84.100\",\n    \"comments\": \"\"\n}"
headers = {
    'Content-Type': "application/json",
    'x-csrftoken': "CAB2DC63339962EECD42D357CC5377",
    'cache-control': "no-cache"
    }

response = requests.request("POST", url, data=payload, headers=headers)

print(response.text)



# GET poolname from policy
import requests

url = "http://192.168.122.40/api/v2/cmdb/firewall/policy/1/poolname"

headers = {
    'cache-control': "no-cache"
    }

response = requests.request("GET", url, headers=headers)

print(response.text)


# POST (add) ip poolname in policy

import requests

url = "https://192.168.122.40/api/v2/cmdb/firewall/policy/1/poolname"

payload = "{\n    \"name\": \"dynip2\"\n}"
headers = {
    'Content-Type': "application/json",
    'x-csrftoken': "CAB2DC63339962EECD42D357CC5377",
    'cache-control': "no-cache"
   }

response = requests.request("POST", url, data=payload, headers=headers)

print(response.text)

# PUT full list of ip poolname in policy

import requests

url = "https://192.168.122.40/api/v2/cmdb/firewall/policy/1/"

payload = "{  \n   \"poolname\":[  \n      {  \n         \"name\":\"dynip2\"\n      },\n      {  \n         \"name\":\"dynip1\"\n      }\n   ]\n}"
headers = {
    'Content-Type': "application/json",
    'x-csrftoken': "CAB2DC63339962EECD42D357CC5377",
    'cache-control': "no-cache"
    }

response = requests.request("PUT", url, data=payload, headers=headers)

print(response.text)

