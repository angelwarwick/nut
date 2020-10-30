#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
Copyright (c) 2018 Blake Warner
Copyright (c) 2017-2018 Adubbz

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

import json
import time
import struct
import server
import usb.core
import usb.util
from nut_impl import nsps
from nut_impl import printer
import server.controller.api
from urllib.parse import urlparse
from urllib.parse import parse_qs

status = 'initializing'


def getFiles():
    o = []
    for k, f in nsps.files.items():
        if f:
            o.append({
                'id': f.id,
                'name': f.name,
                'version': int(f.version) if f.version else None,
                'size': f.getFileSize(),
                'mtime': f.getFileModified()
            })

    return json.dumps(o)


class UsbResponse(server.NutResponse):
    def __init__(self, packet):
        super(UsbResponse, self).__init__(None)
        self.packet = packet

    def sendHeader(self):
        pass

    def _write(self, data):
        printer.info('usbresponse write')
        if self.bytesSent == 0 and not self.headersSent:
            self.sendHeader()

        if type(data) == str:
            data = data.encode('utf-8')

        if not len(data):
            return

        self.bytesSent += len(data)
        self.packet.payload = data
        self.packet.send(10 * 60 * 1000)


class UsbRequest(server.NutRequest):
    def __init__(self, url):
        self.headers = {}
        self.path = url
        self.head = False
        self.url = urlparse(self.path)

        printer.info('url ' + self.path)

        self.bits = [x for x in self.url.path.split('/') if x]
        self.query = parse_qs(self.url.query)

        try:
            for k, v in self.query.items():
                self.query[k] = v[0]
        except:
            pass

        self.user = None


class Packet:
    def __init__(self, i, o):
        self.size = 0
        self.payload = b''
        self.command = 0
        self.threadId = 0
        self.packetIndex = 0
        self.packetCount = 0
        self.timestamp = 0
        self.i = i
        self.o = o

    def recv(self, timeout=60000):
        printer.info('begin recv')
        header = bytes(self.i.read(32, timeout=timeout))
        printer.info('read complete')
        magic = header[:4]
        self.command = int.from_bytes(header[4:8], byteorder='little')
        self.size = int.from_bytes(header[8:16], byteorder='little')
        self.threadId = int.from_bytes(header[16:20], byteorder='little')
        self.packetIndex = int.from_bytes(header[20:22], byteorder='little')
        self.packetCount = int.from_bytes(header[22:24], byteorder='little')
        self.timestamp = int.from_bytes(header[24:32], byteorder='little')

        if magic != b'\x12\x12\x12\x12':
            printer.error('invalid magic! ' + str(magic))
            return False

        printer.info('receiving %d bytes' % self.size)
        self.payload = bytes(self.i.read(self.size, timeout=0))
        return True

    def send(self, timeout=60000):
        printer.info('sending %d bytes' % len(self.payload))
        self.o.write(
            b'\x12\x12\x12\x12',
            timeout=timeout
        )
        self.o.write(
            struct.pack('<I', self.command),
            timeout=timeout
        )
        self.o.write(
            struct.pack('<Q', len(self.payload)),
            timeout=timeout
        )  # size
        self.o.write(
            struct.pack('<I', 0),
            timeout=timeout
        )  # threadId
        self.o.write(
            struct.pack('<H', 0),
            timeout=timeout
        )  # packetIndex
        self.o.write(
            struct.pack('<H', 0),
            timeout=timeout
        )  # packetCount
        self.o.write(
            struct.pack('<Q', 0),
            timeout=timeout
        )  # timestamp
        self.o.write(
            self.payload,
            timeout=timeout
        )


def poll_commands(in_ep, out_ep):
    p = Packet(in_ep, out_ep)
    while True:
        if p.recv(0):
            if p.command == 1:
                printer.debug('Recv command! %d' % p.command)
                req = UsbRequest(p.payload.decode('utf-8'))
                with UsbResponse(p) as resp:
                    server.route(req, resp)
            else:
                printer.error('Unknown command! %d' % p.command)
        else:
            printer.error('failed to read!')


def getDevice():
    while True:
        devs = usb.core.find(idVendor=0x16C0, idProduct=0x27E2, find_all=True)

        if devs is not None:
            for dev in devs:
                return dev

        devs = usb.core.find(idVendor=0x057E, idProduct=0x3000, find_all=True)

        if devs is not None:
            for dev in devs:
                return dev

        time.sleep(1)


def daemon():
    global status
    while True:
        try:
            status = 'disconnected'

            dev = getDevice()

            printer.info('USB Connected')
            status = 'connected'

            dev.reset()
            dev.set_configuration()
            cfg = dev.get_active_configuration()

            def is_out_ep(ep):
                return usb.util.endpoint_direction(ep.bEndpointAddress) == \
                    usb.util.ENDPOINT_OUT

            def is_in_ep(ep):
                return usb.util.endpoint_direction(ep.bEndpointAddress) == \
                    usb.util.ENDPOINT_IN

            out_ep = usb.util.find_descriptor(
                cfg[(0, 0)],
                custom_match=is_out_ep
            )
            in_ep = usb.util.find_descriptor(
                cfg[(0, 0)],
                custom_match=is_in_ep
            )

            assert out_ep is not None
            assert in_ep is not None

            poll_commands(in_ep, out_ep)
        except BaseException as e:
            printer.error('usb exception: ' + str(e))
        time.sleep(1)
