#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import tqdm
import time
import threading
from nut_impl import config

lst = []
jsonData = []
lock = threading.Lock()
threadRun = True


def print_(s):
    for i in lst:
        if i.isOpen():
            try:
                i.tqdm.write(s)
                return
            except:
                pass
    print(s)


def isActive():
    for i in lst:
        if i.isOpen():
            return True
    return False


def data():
    global jsonData
    return jsonData


def loopThread():
    global threadRun
    global jsonData

    while threadRun and config.isRunning:
        time.sleep(0.5)
        jsonData = []
        for i in lst:
            if i.isOpen():
                try:
                    jsonData.append({
                        'description': i.desc,
                        'i': i.i,
                        'size': i.size,
                        'elapsed': time.process_time() - i.timestamp,
                        'speed': i.a / (time.process_time() - i.ats),
                        'id': i.id
                    })
                    i.a = 0
                    i.ats = time.process_time()
                except:
                    pass


def create(size, desc=None, unit='B'):
    lock.acquire()
    position = len(lst)

    for i, s in enumerate(lst):
        if not s.isOpen():
            position = i
            break

    s = Status(size, position, desc=desc, unit=unit)

    if position >= len(lst):
        lst.append(s)
    else:
        lst[position] = s

    lock.release()
    return s


class Status:
    def __init__(self, size, position=0, desc=None, unit='B'):
        self.position = position
        self.size = size
        self.i = 0
        self.a = 0
        self.id = None
        self.ats = time.process_time()
        self.timestamp = time.process_time()
        self.desc = desc

        self.tqdm = tqdm.tqdm(
            total=size,
            unit=unit,
            unit_scale=True,
            position=position,
            desc=desc,
            leave=False,
            ascii=True
        )

    def add(self, v=1):
        if self.isOpen():
            self.i += v
            self.a += v
            try:
                self.tqdm.update(v)
            except BaseException:
                pass

    def update(self, v=1):
        self.add(v)

    def __del__(self):
        self.close()

    def close(self):
        if self.isOpen():
            try:
                self.tqdm.close()
            except:
                pass
            self.tqdm = None
            self.size = None

    def setDescription(self, desc, refresh=False):
        self.desc = desc
        if self.isOpen():
            try:
                self.tqdm.set_description(desc, refresh=refresh)
            except:
                self.close()

    def isOpen(self):
        return True if self.size is not None else False


def start():
    global threadRun
    threadRun = True
    thread = threading.Thread(target=loopThread)
    thread.start()


def close():
    global threadRun
    threadRun = False
