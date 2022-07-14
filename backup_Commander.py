from sanic import Sanic, response
# from sanic_motor import BaseModel
from asyncio_mqtt import Client, MqttError
import sys

app = Sanic(__name__)
port = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isnumeric else sys.exit("Error -> port not specified e.g. 5055")
gateway = sys.argv[2] if len(sys.argv) == 3 else sys.exit("Error -> mqtt gateway not specified e.g. test.mosquitto.org")

# class Command(BaseModel):
#     @staticmethod
#     def rnd():
#         return {'detailed': True, 'link': str(ObjectId()), 'vendor': 'shaygan' if 1 == randint(0, 1) else 'neginatrisa', 'phone': ''.join([choice(digits) for _ in range(9)]), 'family': ''.join([choice(alphabets) for _ in range(randint(4, 7))]), 'gender': 1 == randint(0, 1), 'maker': 1 == randint(0, 1), 'taker': 0 == randint(0, 1), 'cool_down': randint(0, 60), 'watch_list': [], 'description': ' '.join([choice(lorem) for _ in range(40, 66)]), 'title': ' '.join([choice(lorem) for _ in range(3, 7)]), 'rent': True if randint(0, 1) == 1 else False, 'buy': True if randint(0, 1) == 1 else False, **{}}
    
#     __coll__ = "commands"
#     __unique_fields__ = [""]

# @app.route('/clients/<client>/devices/<device>/<command>', methods=['GET'])
# async def _command(r, client, device, command):
#     return response.json({}), 200

@app.route('/<topic:path>', methods=['GET', 'POST'])
async def _route(r, topic):
    async with Client(gateway) as client:
        payload = r.body if r.method == 'POST' else r.args['m'][0].encode() if 'm' in r.args else b''
        await client.publish(topic, payload=payload.decode())
    return response.json({'OK': True}, 201)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port)
