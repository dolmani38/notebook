import asyncio
import inspect
import os
import subprocess
import html as htmlconverter
import webbrowser

import pandas
import tornado.httpserver
import tornado.websocket
import tornado.ioloop
import tornado.web
import socket
import threading
import time
import traceback
import io
import base64
import sys
import uuid
import ctypes
import matplotlib
import matplotlib.pyplot as plt
import json
from gevent import wsgi
from flask import Flask, Response, send_file
from flask_cors import CORS
from flask_restful import Api,Resource
from werkzeug.debug import DebuggedApplication
matplotlib.use('Agg')
from contextlib import redirect_stdout, redirect_stderr
from tornado.platform.asyncio import AnyThreadEventLoopPolicy
import builtin_methods as module

app = Flask(__name__)
api = Api(app)
# cross domain 호출을 허용한다.
CORS(app)


class Statics(Resource):
    """
    WSGIServer 에서 Static에 해당하는 Resource를 Web serving 처리 한다.
    """
    def get(self,path):
        #print('path:',path)

        try:
            mimetypes = {
                ".css": "text/css",
                ".html": "text/html",
                ".txt": "text/plain",
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".ico": "image/ico",
                ".js": "application/javascript",
                ".ttf":"application/x-font-ttf",
                ".woff":"application/x-font-woff",
                ".woff2": "application/x-font-woff2",
                ".map":"application/x-navimap"
            }
            #print('complete_path:', complete_path)
            ext = os.path.splitext(path)[1]
            mimetype = mimetypes.get(ext, "text/html")
            #print('ext:', ext, 'minetype:', mimetype)
            #content = self.get_file(complete_path,ext)
            #return Response(content, mimetype=mimetype)
            return send_file(path,mimetype=mimetype)
        except Exception as e:
            print(e, file=sys.stderr)

def terminate_thread(thread):
    if not thread.isAlive():
        print("is not alive:",thread)
        return

    exc = ctypes.py_object(SystemExit)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_long(thread.ident), exc)
    if res == 0:
        raise ValueError("nonexistent thread id")
    elif res > 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(thread.ident, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

def fig_to_img_tag(fig):
    img = io.BytesIO()
    fig.savefig(img, format='png',
                bbox_inches='tight')
    img.seek(0)
    encoded = base64.b64encode(img.getvalue())
    return '<img src="data:image/png;base64, {}">'.format(encoded.decode('utf-8'))

def disply_last_code(obj=None):
    if not obj is None:
        class_name = type(obj).__name__
        if class_name == "DataFrame":
            if obj.shape[0] > 20:
                a = obj.head(5)
                b = pandas.DataFrame(data=[['...' for i in range(len(a.columns))]], columns=a.columns)
                b.rename(index={0: '...'}, inplace=True)
                rm = pandas.concat([a,b,obj.tail(5)], sort=False)
                print(rm.to_html())
                print("{} rows x {} columns".format(obj.shape[0],obj.shape[1]))
            else:
                print(obj.to_html())
        else:
            if not obj is None:
                print(obj)

    if plt.get_fignums():
        for n in plt.get_fignums():
            fig = plt.figure(n)
            print(fig_to_img_tag(fig))
            plt.close(fig)


global_env = {'fig_to_img_tag': fig_to_img_tag, 'disply_last_code': disply_last_code}
local_env = {}
global_thread = {}

functions = inspect.getmembers(module, inspect.isfunction)
for fnc in functions:
    print("builtin method:",fnc[0])
    global_env[fnc[0]] = fnc[1]

class WSHandler(tornado.websocket.WebSocketHandler):

    def open(self):
        print('\nnew connection')

    def on_message(self, message):
        # Reverse Message and send it back
        print(message)
        data = json.loads(message)
        self.__action(data)

    def on_close(self):
        print('connection closed')

    def check_origin(self, origin):
        return True

    def __action(self,data):

        if data["cmd"] == "save":
            file_name = data["file_name"]
            html = data["html"]
            if not file_name.endswith(".alnb"):
                file_name += ".alnb"
            with open(file_name, 'w', encoding="utf-8") as f:
                f.write(html)
                f.close()
                self.write_message("Save!")
            self.close()
        elif data["cmd"] == "list":
            ls = []
            for s in os.listdir('.'):
                if s.endswith(".alnb"):
                   ls.append("<a href=\"javascript:open('"+s+"')\">"+s+"</a><br>")
            self.write_message(''.join(ls))
            self.close()
        elif data["cmd"] == "open":
            file_name = data["file_name"]
            with open(file_name, 'r', encoding="utf-8") as f:
                html = f.read()
                f.close()
                self.write_message(html)
            self.close()
        elif data["cmd"] == "stop":
            script_code = data["code"]
            print("stop_", script_code,file=sys.stderr)
            if script_code in global_thread:
                terminate_thread(global_thread[script_code])
            self.close()
        elif data["cmd"] == "run":
            codes = []
            cmds = []
            script = data["script"]
            for l in script.strip().split('\n'):
                if l.startswith("!"):
                    cmds.append(l[1:len(l)])
                else:
                    codes.append(l)
            lc = codes.pop()
            if lc[0] in [" ","\t","#","\""]:
                codes.append(lc)
                codes.append('disply_last_code(None)')
            else:
                f1 = lc.find("=")
                f2 = lc.find(".")
                if f1 > 0 and f2 > 0 and f2 < f1:
                    #ok - function
                    codes.append('zxsc = ' + lc)
                    codes.append('disply_last_code(zxsc)')
                elif f1 > 0 and f2 < 0:
                    #no - define
                    codes.append(lc)
                    codes.append('disply_last_code(None)')
                else:
                    # variables
                    codes.append('zxsc = ' + lc)
                    codes.append('disply_last_code(zxsc)')

            script = '\n'.join(codes)

            t = threading.Thread(target=self.__exec,args=(cmds,script,))
            t.start()
        else:
            try:
                method_to_call = getattr(module, data["cmd"])
                result = method_to_call(data["param"])
                member_name = "_" + data["param"].split("/")[-1].replace(".","_")
                self.write_message("The variable '<font color='red'>{}</font>' has been created.\n".format(member_name))
                global_env[member_name] = result
            except Exception as e:
                err = traceback.format_exc()
                self.write_message("<font color='red'>" + htmlconverter.escape(err) + "</font>\n")

    def __exec(self,cmds,script):
        try:
            file_name = 'python_' + str(uuid.uuid1())
            self.write_message(file_name)

            for cmd in cmds:
                ls = cmd.split(' ')
                temp_out = ""
                temp_err = ""
                seek_out = 0
                seek_err = 0
                with subprocess.Popen(ls,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, bufsize=0, shell=True, universal_newlines=True) as p:
                    while p.poll() is None:
                        time.sleep(0.01)
                        if p.stdout.readable():
                            out = p.stdout.read()
                            if not temp_out == out:
                                temp_out = out
                                s = len(temp_out)
                                t = temp_out[seek_out:s]
                                seek_out = s
                                self.write_message(htmlconverter.escape(t))
                            p.stdout.flush()

                        if p.stderr.readable():
                            err = p.stderr.read()
                            if not temp_err == err:
                                temp_err = err
                                s = len(temp_err)
                                t = temp_err[seek_err:s]
                                seek_err = s
                                self.write_message("<font color='red'>" + htmlconverter.escape(t) + "</font>\n")
                            p.stderr.flush()

            plt.show = disply_last_code

            codeObejct = compile(script, file_name, 'exec')
            stdout = io.StringIO()
            stderr = io.StringIO()
            global_env.update(local_env)

            with redirect_stdout(stdout),redirect_stderr(stderr):
                try:
                    global_thread[file_name] = threading.Thread(target=self.__exec_int,args=(codeObejct,))
                    global_thread[file_name].start()
                    self.__stdout_pipe2(global_thread[file_name], stdout,stderr)
                except Exception as e:
                    err = traceback.format_exc()
                    # err = err[err.find("python_") - 6:len(err)]
                    #print("Error:", err, file=sys.stderr)
                    self.write_message("<font color='red'>" + htmlconverter.escape(err) + "</font>\n")

            print('End of ', file_name)

        except Exception as e:
            # traceback.print_exc()
            err = traceback.format_exc()
            #err = err[err.find("python_") - 6:len(err)]
            print("Error:", err,file=sys.stderr)
            self.write_message("<font color='red'>"+htmlconverter.escape(err)+"</font>\n")
        self.close()

    def __exec_int(self,codeObejct):
        if 'tensorflow' in sys.modules.keys():
            import keras.backend.tensorflow_backend as tb
            tb._SYMBOLIC_SCOPE.value = True
        exec(codeObejct, global_env, global_env)#local_env)

    def __stdout_pipe2(self,x,stdout,stderr):
        temp_out = ""
        temp_err = ""
        seek_out = 0
        seek_err = 0
        while x.isAlive():
            out = stdout.getvalue()
            err = stderr.getvalue()
            if not temp_out == out:
                temp_out = out
                s = len(temp_out)
                t = temp_out[seek_out:s]
                seek_out = s
                self.write_message(t)

            if not temp_err == err:
                temp_err = err
                s = len(temp_err)
                t = temp_err[seek_err:s]
                seek_err = s
                if not t.find("base_events.py:509:") > 0:
                    self.write_message("<font color='red'>" + t + "</font>\n")

            time.sleep(0.01)

        out = stdout.getvalue()
        err = stderr.getvalue()
        if not temp_out == out:
            temp_out = out
            s = len(temp_out)
            t = temp_out[seek_out:s]
            seek_out = s
            self.write_message(t)

        if not temp_err == err:
            temp_err = err
            s = len(temp_err)
            t = temp_err[seek_err:s]
            seek_err = s
            if not t.find("base_events.py:509:") > 0:
                self.write_message("<font color='red'>"+t+"</font>\n")

        del x


application = tornado.web.Application([
    (r'/', WSHandler),
])

if __name__ == "__main__":
    web_port = 9999
    runtime_port = 8888
    api.add_resource(Statics().__class__,'/<path:path>')
    asyncio.set_event_loop_policy(AnyThreadEventLoopPolicy())
    runtime_server = tornado.httpserver.HTTPServer(application)
    runtime_server.listen(runtime_port)
    myIP = socket.gethostbyname(socket.gethostname())

    print("Ready to listen python runtime {}:{}".format(myIP,runtime_port))

    def http_serve_forever(myIP,web_port,app):
        http_server = wsgi.WSGIServer((myIP, web_port), DebuggedApplication(app))
        print("Ready to listen http://{}:{}/analyca_notebook_test1.html".format(myIP, web_port))
        http_server.serve_forever()


    daemon = threading.Thread(target=http_serve_forever,
                              args=(myIP,web_port,app,))
    daemon.setDaemon(True)  # Set as a daemon so it will be killed once the main thread is dead.
    daemon.start()
    # Open the web browser
    #webbrowser.open("http://{}:{}/analyca_notebook_test1.html".format(myIP, web_port))
    tornado.ioloop.IOLoop.instance().start()
