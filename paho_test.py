from asyncio_mqtt import Client, MqttError
import time
import paho.mqtt.client as mqtt
import asyncio

# async def pull():
#     async with Client("mqtt.eclipseprojects.io") as client:
#         async with client.filtered_messages("floors/+/humidity") as messages:
#             await client.subscribe("floors/#")
#             async for message in messages:
#                 print(message.payload.decode())

# async def push():
#     async with Client("mqtt.eclipseprojects.io") as client:
#         message = "10%"
#         await client.publish(
#                 "floors/bed_room/humidity",
#                 payload=message.encode()
#             )

# if __name__ == '__main__':
#     loop = asyncio.get_event_loop()
#     asyncio.ensure_future(pull(), loop=loop)
#     # loop.ensure_future(pull())
#     time.sleep(3)
#     asyncio.get_event_loop().run_until_complete(push())
#     time.sleep(3)
#     asyncio.ensure_future(pull(), loop=loop)
#     time.sleep(3)

import time
import paho.mqtt.client as paho
broker="broker.hivemq.com"
"mqtt.eclipseprojects.io"
broker="135.181.198.245"
#define callback
def on_message(client, userdata, message):
    time.sleep(1)
    print("received message =",str(message.payload.decode("utf-8")))

client= paho.Client("client-001") #create client object client1.on_publish = on_publish #assign function to callback client1.connect(broker,port) #establish connection client1.publish("house/bulb1","on")
##### Bind function to callback
client.on_message=on_message
#####
print("connecting to broker ",broker)
client.connect(broker)  # connect
client.loop_start()  # start loop to process received messages
print("subscribing ")
client.subscribe("house/bulb1")#subscribe
time.sleep(2)
print("publishing ")
client.publish("house/bulb1","on")#publish
time.sleep(4)
client.loop_forever()
# client.disconnect() #disconnect
# client.loop_stop() #stop loop

"""
stream {
    server {
        listen 443 ssl;
        ssl_certificate             /etc/nginx/server-cert.crt;
        ssl_certificate_key         /etc/nginx/server-cert.key;
        server_name www.m.direktech.co.uk; m.direktech.co.uk;
        proxy_protocol on;
        proxy_pass 127.0.0.1:8443;
    }
}
server {
    listen 80;
    listen 443 ssl;
    ssl_certificate             /etc/nginx/server-cert.crt;
    ssl_certificate_key         /etc/nginx/server-cert.key;
    server_name www.command.direktech.co.uk; command.direktech.co.uk;
    location / {
        proxy_pass http://localhost:5055;
    }   
}
"""

"""
upstream websocket_analytics {
    server 0.0.0.0:5001;
}

upstream websocket_sims {
	server 0.0.0.0:5000;
}

server {
    client_max_body_size 8M;

    listen 443 ssl;

    ssl_certificate             /etc/nginx/server-cert.crt;
    ssl_certificate_key         /etc/nginx/server-cert.key;

    server_name www.direktech.co.uk direktech.co.uk;

#    location / {
#        proxy_pass http://0.0.0.0:4200;
#        proxy_set_header Host $host;
#        proxy_http_version 1.1;
#        proxy_set_header Upgrade $http_upgrade;
#        proxy_set_header Connection 'upgrade';
#        proxy_cache_bypass $http_upgrade;
#    }

    location /website {
        proxy_pass http://unix:/var/lib/docker/volumes/website-backend-python_gunicorn_socket/_data/gunicorn.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_redirect off;
    }

    location /implant-genius {
        proxy_pass http://unix:/var/lib/docker/volumes/implant_genius_backend_gunicorn_socket/_data/gunicorn.sock;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_redirect off;
    }

    location /sims-analytics/live-zone{
	    proxy_pass http://websocket_analytics;
	    proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
	    proxy_set_header Origin '';
        proxy_connect_timeout 605;
        proxy_send_timeout 605;
        proxy_read_timeout 605;
        send_timeout 605;
        keepalive_timeout 605;
    }

    location /sims-backend/ble-csis/add{
        proxy_pass http://websocket_sims;
	    proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Origin '';
        proxy_connect_timeout 605;
        proxy_send_timeout 605;
        proxy_read_timeout 605;
        send_timeout 605;
        keepalive_timeout 605;
    }

    location /sims-backend {
        proxy_pass http://0.0.0.0:8081;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_redirect off;
    }

    location /pips-backend {
        proxy_pass http://0.0.0.0:8080;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_redirect off;
    }

    location /user {
        proxy_pass http://localhost:8001;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_redirect off;
    }
}
"""

"""
server {
    listen 80;
    server_name YOUR.OWN.DOMAIN.URL;
    location / {
        proxy_pass http://THE.SITE.URL.YOU.WANT.TO.DELEGAGE/;
        proxy_redirect off;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
server {
    listen 80;
    # maps p8080.example.com -> localhost:8080
    server_name ~^p(?<port>[^.]+)\.example\.com$;
    location / {
        proxy_pass http://localhost:$port;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
"""