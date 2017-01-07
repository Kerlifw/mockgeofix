#!/usr/bin/env python

# GPX from google maps route: http://www.gpsvisualizer.com/convert_input
# Or export directly from http://map.project-osrm.org

### stdlib packages
import os
import socket
import argparse
import sys
import select
import time
import threading
import thread
### external deps
try:
    import dateutil.parser
    assert dateutil.parser  # pyflakes
except ImportError:
    print("package \"python-dateutil\" is required. exiting")
    sys.exit(2)
### bundled packages
import gpxdata
###
import Queue
import uuid

INDEX = "/whereami/whereami.html"
UPDATE_INTERVAL = 0.3

curr_lat = None  # updated by main thread, read by http and geofix threads
curr_lon = None   # updated by main thread, read by http and geofix threads

class QueueWithMark:
    def __init__(self):
        self.q = Queue.Queue()
        self.uuid = uuid.uuid1()

    def clear_and_put_all(self, items):
        self.uuid = uuid.uuid1()
        with self.q.mutex: #!!
            self.q.queue.clear()
        for item in items:
            self.q.put(item)

    def get(self):
        return self.q.get()

    def mark(self):
        return self.uuid

    def empty(self):
        return self.q.empty()

def main(args):
    queue = QueueWithMark()

    if args.listen_ip:
        http_thread = threading.Thread(target=start_http_server, args=(args, queue,))
        http_thread.daemon = True
        http_thread.start()
        time.sleep(1)

    geofix_thread = threading.Thread(target=start_geofix, args=(args,))
    geofix_thread.daemon = True
    geofix_thread.start()

    t_speed = None
    if args.speed:
        t_speed = args.speed / 3.6

    print("Location mocking started.")
    if not t_speed:
        walk_track_interval(queue, float(args.sleep))
    else:
        walk_track_speed(queue, t_speed)

def walk_track_interval(track, t_sleep):
    global curr_lon
    global curr_lat
    while True:
        time.sleep(t_sleep)
        try:
            point = next(track)
        except StopIteration:
            print("done")
            sys.exit(0)
        curr_lon = point.lon
        curr_lat = point.lat

def walk_step(queue, mark_last, p1, p2, speed):
    global curr_lon
    global curr_lat

    distance = p1.distance(p2)
    travel_time = distance / speed  # in seconds

    if travel_time <= UPDATE_INTERVAL:
        time.sleep(travel_time)
    while travel_time > UPDATE_INTERVAL:
        time.sleep(UPDATE_INTERVAL)
        if queue.mark() != mark_last:
            return False
        travel_time -= UPDATE_INTERVAL
        # move GEOFIX_UPDATE_INTERVAL*speed meters
        # in straight line between last_point and point
        course = p1.course(p2)
        distance = UPDATE_INTERVAL * speed
        p1 = p1 + gpxdata.CourseDistance(course, distance)
        curr_lat = p1.lat
        curr_lon = p1.lon
    return True

def walk_track_speed(queue, speed):
    from time import localtime, strftime
    
    global curr_lon
    global curr_lat

    while True:
        p1 = queue.get()
        p2 = queue.get()
        mark_last = queue.mark()
        while True:
            print("%s (%f, %f) -> (%f, %f)" % (strftime("%H:%M:%S", localtime()), p1.lat, p1.lon, p2.lat, p2.lon))

            if not walk_step(queue, mark_last, p1, p2, speed):
                break

            p1 = p2
            curr_lat = p1.lat
            curr_lon = p1.lon
            if queue.empty() or queue.mark() != mark_last:
                print("stop")
                break
            p2 = queue.get()

def start_geofix(args):
    s = socket.socket()
    try:
        s.connect((args.ip, args.port))
    except socket.error as ex:
        print("Error connecting to %s:%s (%s)" % (args.ip, args.port, ex))
        thread.interrupt_main()

    try:
        while True:
            rlist, wlist, _ = select.select([s], [s], [])
            if s in rlist:
                x = s.recv(1024)
                if "KO: password required" in x:
                    s.close()
                    print("Password protection is enabled MockGeoFix settings. This is not supported.")
                    sys.exit(2)
                if x == '':
                    s.close()
                    print("Connection closed.")
                    thread.interrupt_main()
            if s in wlist:
                if curr_lon != None and curr_lat != None:
                    msg = "geo fix %f %f\r\n" % (curr_lon, curr_lat)
                    s.send(msg)
                    #print(msg)
            time.sleep(UPDATE_INTERVAL)
    except socket.error as ex:
        print(ex)
        thread.interrupt_main()


def start_http_server(args, queue):
    import SocketServer
    from StringIO import StringIO

    import BaseHTTPServer
    import mimetypes
    from os import curdir, sep
    import json 
    from gpxdata import TrackPoint

    mimetypes.init()

    class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.strip() == "/":
                self.send_response(301)
                self.send_header("Location", INDEX)
                self.end_headers()
            elif self.path.strip() == "/getpos":
                self.get_position()
            else:
                path = self.path.strip();
                filename, file_extension = os.path.splitext(path)
                if "" == file_extension:
                    self.send_error(404, 'File Not Found: %s' % self.path)
                    return

                local_path = curdir + sep + path;
                if not os.path.exists(local_path):
                    self.send_error(404, 'File Not Found: %s' % self.path)
                    return

                mimetype = mimetypes.types_map[file_extension]
                self.send_response(200)
                self.send_header('Content-type', mimetype)
                self.end_headers()
                with open(local_path, 'rb') as f:
                    self.wfile.write(f.read())
                    
        def do_POST(self):
            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write("ok")

        def do_PUT(self):
            length = int(self.headers.getheader('Content-Length'))
            data = json.loads(self.rfile.read(length))
            points = []
            for latlng in data:
                points.append(TrackPoint(latlng[u'lat'], latlng[u'lng']))
            queue.clear_and_put_all(points)

            self.send_response(200)
            self.send_header('Content-type','text/html')
            self.end_headers()
            self.wfile.write("ok")

        def get_position(self):
            f = StringIO()
            if curr_lat == None or curr_lon == None:
                f.write("""{
                    "status": "WAIT",
                    "accuracy": 10.0
                }""")
            else:
                f.write("""{
                    "status": "OK",
                    "accuracy": 10.0,
                    "location": {"lat": %f, "lng": %f}
                }""" % (curr_lat, curr_lon))
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            length = f.tell()
            f.seek(0)
            self.send_header("Content-Length", str(length))
            self.end_headers()
            self.wfile.write(f.read(length))

        def list_directory(self, _):
            self.path = "/"
            return self.do_GET()

        def log_message(self, *_):
            return

    class TCPServer(SocketServer.TCPServer):
        def server_bind(self):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(self.server_address)

        def handle_error(self, request, client_address):
            if sys.exc_info()[0] == socket.error:
                return  # client probably closed connection
            return SocketServer.TCPServer.handle_error(self, request, client_address)

    try:
        httpd = TCPServer((args.listen_ip, args.listen_port), Handler)
    except Exception as ex:
        print("Error starting HTTP server: %s" % ex)
        thread.exit()

    print("Open http://%s:%s in your web browser." % (args.listen_ip, args.listen_port))
    httpd.serve_forever()

if __name__ == '__main__':
    args_parser = argparse.ArgumentParser()
    args_parser.add_argument("-i", "--ip", help="connect to MockGeoFix using this IP address",
                             required=True)
    args_parser.add_argument("-p", "--port", default=5554, help="default: 5554", type=int)
    args_parser.add_argument("-S", "--sleep", help="sleep between track points (default: 0.5)",
                             required=False, default=0.5, type=float)
    args_parser.add_argument("-s", "--speed", help="speed in km/h (takes precedence over -S)",
                             required=False, type=float)
    args_parser.add_argument("-I", "--listen-ip",
                             help="Run a HTTP server visualizing mocked location on this ip.",
                             required=False)
    args_parser.add_argument("-P", "--listen-port", help="HTTP server's port (default: 80)",
                             required=False, default=80, type=int)

    args = args_parser.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try:
        main(args)
    except KeyboardInterrupt:
        print("Exiting.")
