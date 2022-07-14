import datetime
import json
import logging
import sys
from typing import Any
from uuid import uuid4

import numpy as np
import pandas as pd
import tornado.gen
import tornado.ioloop
import tornado.locks
import tornado.web
from config import settings
from pymongo import MongoClient
from tornado import httputil
from tornado.websocket import WebSocketHandler

logger = logging.getLogger("SimsESPServer (" + str(uuid4())[:3] + ")")
logger.setLevel(logging.DEBUG)
lock = tornado.locks.Lock()


class EspSocketHandler(WebSocketHandler):
    mongo_client = MongoClient(settings.mongo_url)
    waiters = set()
    zone_modes = {}
    csi_buffer_length = settings.csi_buffer_length
    ble_buffer_length = settings.ble_buffer_length
    update_zone_mode_frequency = settings.update_zone_mode_frequency
    working_async = settings.working_async

    def __init__(
        self,
        application: tornado.web.Application,
        request: httputil.HTTPServerRequest,
        **kwargs: Any
    ) -> None:
        super().__init__(application, request, **kwargs)
        self.uuid = None
        self.clientId = None
        self.clientDB = None
        self.clientFloor = None
        self.clientZone = None
        self.clientVersion = None
        self.clientAPid = None
        self.csiBuffer = []
        self.bleBuffer = []
        self.clientMode = False
        self.clientOccupancy = -1
        self.clientActivity = -1
        self.clientUpdate = None
        self.clientBattery = None
        self.clientLight = None
        self.clientTemperature = None

    @classmethod
    async def update_zone_modes(cls):
        while True:
            waitInterval = tornado.gen.sleep(cls.update_zone_mode_frequency)
            await cls.read_zone_modes()
            await waitInterval

    @classmethod
    async def read_zone_modes(cls):
        sims_maps = [
            m for m in cls.mongo_client.list_database_names() if m.startswith("sims")
        ]
        for map_name in sims_maps:
            try:
                if "zones" in cls.mongo_client[map_name].list_collection_names():
                    zones = pd.DataFrame(
                        list(
                            cls.mongo_client[map_name]["zones"].find(
                                {},
                                {
                                    "FloorNumber": 1,
                                    "ZoneNumber": 1,
                                    "Activity": 1,
                                    "Occupancy": 1,
                                    "Mode": 1,
                                    "OTA": 1,
                                    "_id": 0,
                                },
                            )
                        )
                    )
                    cls.zone_modes[map_name] = zones
            except Exception:
                logger.exception("Failed at reading zones of {}!".format(map_name))

        for waiter in cls.waiters:
            (
                waiter.clientMode,
                waiter.clientOccupancy,
                waiter.clientActivity,
                waiter.clientUpdate,
            ) = cls.check_mode(waiter.clientDB, waiter.clientFloor, waiter.clientZone)

            if waiter.clientUpdate is not None:
                logger.critical(
                    "$$$ Updating ESP-{} of floor-{} at {}".format(
                        waiter.clientZone, waiter.clientFloor, waiter.clientDB
                    )
                )

                firmwareMessage = (
                    '{"firmware_update":1,"url":"' + str(waiter.clientUpdate) + '"}'
                )
                logger.critical(
                    "$$$ firmware update message is: {}".format(firmwareMessage)
                )
                waiter.write_message(firmwareMessage)
                logger.critical("$$$ firmware update command sent")

                waiter.clientUpdate = None
                cls.mongo_client[waiter.clientDB]["zones"].update_one(
                    {
                        "FloorNumber": waiter.clientFloor,
                        "ZoneNumber": waiter.clientZone,
                    },
                    {"$set": {"OTA": []}},
                )

    @classmethod
    def send_message(cls, waiter, message):
        try:
            waiter.write_message(message)
        except Exception:
            logging.error("Error sending message", exc_info=True)

    @classmethod
    @tornado.gen.coroutine
    def add_waiter(cls, waiter):
        logger.info("Adding a waiter with (uuid: %s) ..." % waiter.uuid)

        with (yield lock.acquire()):
            EspSocketHandler.waiters.add(waiter)

    @classmethod
    @tornado.gen.coroutine
    def remove_waiter(cls, waiter):
        logger.info("Removing a waiter with (uuid: %s)" % waiter.uuid)

        with (yield lock.acquire()):
            if waiter in EspSocketHandler.waiters:
                EspSocketHandler.waiters.remove(waiter)
            else:
                logger.critical(
                    8 * "^" + "There is no waiter with (uuid: %s)!" % waiter.uuid
                )

    @classmethod
    def decode_waiter_message(cls, waiter, request):
        if "TYPE" not in request.keys():
            logger.exception('Unknown message format! "TYPE" field is missing.')
        elif request["TYPE"] not in [0, 1, 2, 3]:
            logger.exception("Unknown TYPE! ({})".format(request["TYPE"]))
        else:
            if request["TYPE"] == 2:
                id_ = list(
                    cls.mongo_client["coreDb"]["websocketids"].find(
                        {"ApiKey": request["Key"], "BuildingName": request["BN"]},
                        {"Id": 1, "UserId": 1, "_id": 0},
                    )
                )
                if len(id_) == 0:
                    logger.exception(
                        "No such building and apiKey! ({}, {})".format(
                            request["BN"], request["Key"]
                        )
                    )
                else:
                    waiter.clientId = id_[0]["Id"]
                    waiter.clientDB = (
                        "sims-" + str(id_[0]["UserId"]) + "_" + request["BN"]
                    )
                    waiter.clientZone = int(request["RX"])
                    if "Floor" in request.keys():
                        waiter.clientFloor = int(request["Floor"])
                    if "Version" in request.keys():
                        waiter.clientVersion = str(request["Version"])
                    if "AP" in request.keys():
                        waiter.clientAPid = request["AP"]

                    cls.mongo_client[waiter.clientDB]["zones"].update_one(
                        {"ZoneNumber": waiter.clientZone},
                        {
                            "$set": {
                                "Version": waiter.clientVersion,
                                "APid": waiter.clientAPid,
                            }
                        },
                    )

                    now = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
                    timeMessage = (
                        '{"Id": "'
                        + str(waiter.clientId)
                        + '", "Datetime": "'
                        + now
                        + '"}'
                    )
                    EspSocketHandler.send_message(waiter, timeMessage)
                    logger.debug(
                        "Waiter (v={}) ({}) {} from {} requested time and got {}".format(
                            waiter.clientVersion,
                            waiter.uuid,
                            waiter.clientZone,
                            request["BN"],
                            now,
                        )
                    )

            elif request["TYPE"] in [0, 1] and waiter.clientDB is not None:
                if waiter.clientFloor is None:
                    waiter.clientFloor = int(request.pop("Floor"))

                request.pop("Floor", None)
                request.pop("RX", None)
                request.pop("Id", None)
                request["START"] = datetime.datetime.strptime(
                    request["START"], "%Y/%m/%d %H:%M:%S.%f"
                )

                EspSocketHandler.add_record(waiter, request)

            elif request["TYPE"] == 3:
                if "Batt" in request.keys():
                    waiter.clientBattery = int(request["Batt"])
                if "Light" in request.keys():
                    waiter.clientLight = int(request["Light"])
                if "Temp" in request.keys():
                    waiter.clientTemperature = int(request["Temp"])

                cls.mongo_client[waiter.clientDB]["zones"].update_one(
                    {"ZoneNumber": waiter.clientZone},
                    {
                        "$set": {
                            "Battery": waiter.clientBattery,
                            "Light": waiter.clientLight,
                            "Temperature": waiter.clientTemperature,
                        }
                    },
                )
                cls.mongo_client[waiter.clientDB]["zonesDetails"].insert_one(
                    {
                        "Battery": waiter.clientBattery,
                        "Light": waiter.clientLight,
                        "Temperature": waiter.clientTemperature,
                    },
                )

            else:
                logger.exception("Proper Id and TYPE 2 data not received yet!")

    @classmethod
    def add_record(cls, waiter, data):
        check, occupancy, activity = (
            waiter.clientMode,
            waiter.clientOccupancy,
            waiter.clientActivity,
        )
        if check:
            typeVal = data.pop("TYPE", -1)
            data["FloorNumber"] = waiter.clientFloor
            data["RX"] = waiter.clientZone
            data["Occupancy"] = occupancy
            data["Activity"] = activity

            if typeVal == 0:
                data["TS"] = datetime.datetime.strptime(
                    data["TS"], "%Y/%m/%d %H:%M:%S.%f"
                )
                waiter.csiBuffer.append(data)

                if len(waiter.csiBuffer) >= cls.csi_buffer_length:
                    try:
                        cls.mongo_client[waiter.clientDB]["wificsis"].insert_many(
                            waiter.csiBuffer
                        )
                    except Exception:
                        logger.critical(
                            "Could not insert csi buffer to {} - error msg: {}".format(
                                waiter.clientDB, sys.exc_info()[1]
                            )
                        )
                    waiter.csiBuffer = []
            elif typeVal == 1:
                waiter.bleBuffer.append(data)
                if len(waiter.bleBuffer) >= cls.ble_buffer_length:
                    try:
                        cls.mongo_client[waiter.clientDB]["blerssis"].insert_many(
                            waiter.bleBuffer
                        )
                    except Exception:
                        logger.critical(
                            "Could not insert ble buffer to {} - error msg: {}".format(
                                waiter.clientDB, sys.exc_info()[1]
                            )
                        )
                    waiter.bleBuffer = []
            else:
                logger.critical(
                    "This should not happen at all-> TYPE: {} from user: {}".format(
                        typeVal, waiter.uuid
                    )
                )

        elif len(waiter.csiBuffer) > 0:
            try:
                cls.mongo_client[waiter.clientDB]["wificsis"].insert_many(
                    waiter.csiBuffer
                )
            except Exception:
                logger.critical(
                    "Could not insert remaining csi buffer to {} - error msg: {}".format(
                        waiter.clientDB, sys.exc_info()[1]
                    )
                )
            waiter.csiBuffer = []
        elif len(waiter.bleBuffer) > 0:
            try:
                cls.mongo_client[waiter.clientDB]["blerssis"].insert_many(
                    waiter.bleBuffer
                )
            except Exception:
                logger.critical(
                    "Could not insert remaining ble buffer to {} - error msg: {}".format(
                        waiter.clientDB, sys.exc_info()[1]
                    )
                )
            waiter.bleBuffer = []

    def get_compression_options(self):
        return {}

    def open(self, token=None):
        logging.info("A new websocket has opened (token: {}).".format(token))
        self.uuid = str(uuid4())[:5]
        EspSocketHandler.add_waiter(self)
        self.set_nodelay(True)

        if EspSocketHandler.working_async is False:
            EspSocketHandler.working_async = True
            tornado.ioloop.IOLoop.current().spawn_callback(
                EspSocketHandler.update_zone_modes
            )

        logger.info("New waiter with (uuid: {}) added.".format(self.uuid))

    def on_close(self):
        logger.info("Closing a websocket waiter (uuid: %s)..." % self.uuid)
        EspSocketHandler.remove_waiter(self)

    def on_message(self, message):
        logging.info("got message %r", message)
        if message is None or not (
            isinstance(message, bytes) or isinstance(message, str)
        ):
            logging.error("Waiter request is not a string/bytes!")
            response = {
                "status": 400,
                "message": "Your request should be either a string or bytes!",
            }
            EspSocketHandler.send_message(self, response)
            return

        elif isinstance(message, bytes):
            try:
                message = EspSocketHandler.binary_to_json(message)
            except Exception:
                logging.error("Waiter request is not a proper bytes array!")
                response = {
                    "status": 400,
                    "message": "Your request does not have the correct bytes array format!",
                }
                EspSocketHandler.send_message(self, response)
                return

        elif isinstance(message, str):
            try:
                message = json.loads(message)
            except Exception:
                logging.error("Waiter request is not a json string!")
                response = {
                    "status": 400,
                    "message": "Your request should be a json string!",
                }
                EspSocketHandler.send_message(self, response)
                return
        else:
            logging.error("~~~ SHOULD NOT REACH HERE!")

        EspSocketHandler.decode_waiter_message(self, message)

    @classmethod
    def binary_to_json(cls, message):
        try:
            message = np.array(list(message), dtype=np.int8).tolist()

            json_msg = dict()
            json_msg["TYPE"] = int(message[0])
            json_msg["START"] = "{:04}/{:02}/{:02} {:02}:{:02}:{:02}.{:03}".format(
                (message[1] * 128 + message[2]),
                message[3],
                message[4],
                message[5],
                message[6],
                message[7],
                (message[8] * 128 + message[9]),
            )
            csi_r = message[11:138:2]
            del csi_r[27:38]
            json_msg["CSI_R"] = list(csi_r)

            csi_i = message[10:138:2]
            del csi_i[27:38]
            json_msg["CSI_I"] = list(csi_i)

            json_msg["RSSI"] = int(message[138])
            json_msg["TX"] = int(message[139])
            json_msg["TS"] = "{:04}/{:02}/{:02} {:02}:{:02}:{:02}.{:03}".format(
                (message[140] * 128 + message[141]),
                message[142],
                message[143],
                message[144],
                message[145],
                message[146],
                (message[147] * 128 + message[148]),
            )
        except Exception:
            raise Exception("Binary to JSON failed: {}".format(sys.exc_info()[1]))

        return json_msg

    @classmethod
    def check_mode(cls, dbName, floor, zone):
        check, occupancy, activity, ota = False, None, None, None
        if dbName is None or dbName not in cls.zone_modes.keys():
            return (check, occupancy, activity, ota)

        map_zones = cls.zone_modes[dbName]

        try:
            if floor is not None:
                mode = map_zones.loc[
                    (map_zones["FloorNumber"] == int(floor))
                    & (map_zones["ZoneNumber"] == int(zone))
                ].to_dict(orient="records")
            else:
                logger.exception(
                    "Waiting for receiving Floor from waiter of zone {} at {}".format(
                        zone, dbName
                    )
                )
                return check, occupancy, activity, ota
        except Exception:
            logger.exception("Failed at finding zone {} in {}".format(zone, dbName))
            return check, occupancy, activity, ota

        if len(mode) != 0 and len(mode[0]["OTA"]) > 0:
            ota = mode[0]["OTA"][0]["link"]

        if len(mode) == 0:
            pass

        elif mode[0]["Mode"] == "Train":
            check, occupancy, activity = True, mode[0]["Occupancy"], mode[0]["Activity"]

        elif mode[0]["Mode"] == "Operation":
            check, occupancy, activity = True, None, []

        elif dbName == "sims-5f22c19bfd65286f96a90d0a_5gic" and zone == 3:
            try:
                mode_sub = map_zones.loc[
                    (map_zones["FloorNumber"] == int(floor))
                    & (map_zones["ZoneNumber"].isin([4, 6]))
                ]["Mode"].to_list()
                if "Train" in mode_sub or "Operation" in mode_sub:
                    check, occupancy, activity = True, None, []
            except Exception:
                logger.exception(
                    "Failed at finding near zone mode in 5gic for zone {}".format(zone)
                )

        elif dbName == "sims-60d9ecfdede543b29d0fe05c_tb":
            try:
                if zone == 1:
                    nearZone = 4

                elif zone == 2:
                    nearZone = 3

                mode_sub = map_zones.loc[
                    (map_zones["FloorNumber"] == int(floor))
                    & (map_zones["ZoneNumber"] == nearZone)
                ].to_dict(orient="records")[0]
                if mode_sub["Mode"] == "Operation" or mode_sub["Mode"] == "Train":
                    check, occupancy, activity = True, None, []
            except Exception:
                logger.exception(
                    "Failed at finding near zone mode in TB for zone {}".format(zone)
                )

        elif dbName == "sims-609e417146286760c2594098_hm":
            try:
                if zone in [8, 6, 4]:
                    nearZone = int(zone - 2)

                elif zone in [1, 3, 5, 0]:
                    nearZone = int(zone + 2)

                elif zone in [14, 16, 17, 18, 19, 20]:
                    nearZone = int(zone - 1)

                elif zone == 21:
                    nearZone = 14

                mode_sub = map_zones.loc[
                    (map_zones["FloorNumber"] == int(floor))
                    & (map_zones["ZoneNumber"] == nearZone)
                ].to_dict(orient="records")[0]

                if mode_sub["Mode"] == "Train" or mode_sub["Mode"] == "Operation":
                    check, occupancy, activity = True, None, []

            except Exception:
                logger.exception(
                    "Failed at finding near zone mode in HM for zone {}".format(zone)
                )

        elif dbName == "sims-609e417146286760c2594098_hml":
            try:
                if zone in [1, 4]:
                    nearZone = 2 if zone == 1 else 3
                    mode_sub = map_zones.loc[
                        (map_zones["FloorNumber"] == int(floor))
                        & (map_zones["ZoneNumber"] == nearZone)
                    ].to_dict(orient="records")[0]
                    if mode_sub["Mode"] == "Train" or mode_sub["Mode"] == "Operation":
                        check, occupancy, activity = True, None, []
                elif zone in [2, 3]:
                    nearZones = [int(zone - 1), int(zone + 1)]
                    mode_sub = map_zones.loc[
                        (map_zones["FloorNumber"] == int(floor))
                        & (map_zones["ZoneNumber"].isin(nearZones))
                    ]["Mode"].to_list()
                    if "Train" in mode_sub or "Operation" in mode_sub:
                        check, occupancy, activity = True, None, []
            except Exception:
                logger.exception(
                    "Failed at finding near zone mode in HML for zone {}".format(zone)
                )

        return check, occupancy, activity, ota
