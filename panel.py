#!/usr/bin/env python3.13
import os
import subprocess
import sys
import threading
import time
import psutil
from flask import Flask,request,jsonify,Response
from waitress import serve

app=Flask(__name__)

panel_config=None
server_start_time=time.time()

def _get_frontend_dir():
    if getattr(sys,"_MEIPASS",None):
        return os.path.join(sys._MEIPASS,"frontend")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),"frontend")

def _load_html():
    with open(os.path.join(_get_frontend_dir(),"index.html"),"r") as f:
        return f.read()

def get_uptime():
    uptime_seconds=int(time.time()-server_start_time)
    days=uptime_seconds//86400
    hours=(uptime_seconds%86400)//3600
    minutes=(uptime_seconds%3600)//60
    seconds=uptime_seconds%60
    if days>0:
        return f"{days}d {hours}h"
    elif hours>0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m {seconds}s"

def get_os_uptime():
    try:
        boot=psutil.boot_time()
        uptime_seconds=int(time.time()-boot)
        days=uptime_seconds//86400
        hours=(uptime_seconds%86400)//3600
        return f"{days}d {hours}h"
    except:
        return "N/A"

def read_config():
    import tomllib
    with open("/etc/ghostwire/server.toml","rb") as f:
        return tomllib.load(f)

def write_config(config):
    import toml
    with open("/etc/ghostwire/server.toml","w") as f:
        toml.dump(config,f)

def tail_log(lines=100):
    try:
        result=subprocess.run(["tail","-n",str(lines),"/var/log/ghostwire-server.log"],capture_output=True,text=True,timeout=5)
        return result.stdout
    except:
        return "Error reading log file"

def get_connection_status():
    try:
        result=subprocess.run(["systemctl","is-active","ghostwire-server"],capture_output=True,text=True,timeout=5)
        return result.stdout.strip()=="active"
    except:
        return False

def restart_service():
    try:
        subprocess.run(["sudo","systemctl","restart","ghostwire-server"],timeout=10,check=True)
        return True
    except:
        return False

def stop_service():
    try:
        subprocess.run(["sudo","systemctl","stop","ghostwire-server"],timeout=10,check=True)
        return True
    except:
        return False

def get_system_info():
    try:
        cpu_percent=psutil.cpu_percent(interval=0.5)
        cpu_count=psutil.cpu_count()
        mem=psutil.virtual_memory()
        swap=psutil.swap_memory()
        disk=psutil.disk_usage("/")
        net=psutil.net_io_counters()
        load=psutil.getloadavg()
        return {
            "cpu_percent":round(cpu_percent,2),
            "cpu_count":cpu_count,
            "ram_used":round(mem.used/1024/1024,2),
            "ram_total":round(mem.total/1024/1024,2),
            "ram_percent":round(mem.percent,2),
            "swap_used":round(swap.used/1024/1024,2),
            "swap_total":round(swap.total/1024/1024,2),
            "swap_percent":round(swap.percent,2),
            "disk_used":round(disk.used/1024/1024/1024,2),
            "disk_total":round(disk.total/1024/1024/1024,2),
            "disk_percent":round(disk.percent,2),
            "net_sent":net.bytes_sent,
            "net_recv":net.bytes_recv,
            "load_1":round(load[0],2),
            "load_5":round(load[1],2),
            "load_15":round(load[2],2)
        }
    except:
        return {"cpu_percent":0,"cpu_count":1,"ram_used":0,"ram_total":0,"ram_percent":0,"swap_used":0,"swap_total":0,"swap_percent":0,"disk_used":0,"disk_total":0,"disk_percent":0,"net_sent":0,"net_recv":0,"load_1":0,"load_5":0,"load_15":0}

@app.before_request
def check_prefix():
    if not request.path.startswith(f"/{panel_config.panel_path}"):
        return Response("",status=404)

@app.route(f"/<path:panel_path>/")
def index(panel_path):
    return _load_html().replace("{{prefix}}",f"/{panel_path}")

@app.route(f"/<path:panel_path>/api/status")
def api_status(panel_path):
    connected=get_connection_status()
    config=read_config()
    tunnel_count=len(config["tunnels"]["ports"])
    return jsonify({"connected":connected,"uptime":get_uptime(),"tunnel_count":tunnel_count,"os_uptime":get_os_uptime()})

@app.route(f"/<path:panel_path>/api/system")
def api_system(panel_path):
    return jsonify(get_system_info())

@app.route(f"/<path:panel_path>/api/tunnels")
def api_tunnels(panel_path):
    config=read_config()
    return jsonify(config["tunnels"]["ports"])

@app.route(f"/<path:panel_path>/api/tunnels",methods=["POST"])
def api_add_tunnel(panel_path):
    data=request.json
    config=read_config()
    config["tunnels"]["ports"].append(data["tunnel"])
    write_config(config)
    return jsonify({"success":True})

@app.route(f"/<path:panel_path>/api/tunnels/<int:index>",methods=["DELETE"])
def api_remove_tunnel(panel_path,index):
    config=read_config()
    if 0<=index<len(config["tunnels"]["ports"]):
        config["tunnels"]["ports"].pop(index)
        write_config(config)
        return jsonify({"success":True})
    return jsonify({"success":False}),400

@app.route(f"/<path:panel_path>/api/config")
def api_get_config(panel_path):
    with open("/etc/ghostwire/server.toml","r") as f:
        return f.read()

@app.route(f"/<path:panel_path>/api/config",methods=["POST"])
def api_save_config(panel_path):
    try:
        config_text=request.data.decode()
        import tomllib
        tomllib.loads(config_text)
        with open("/etc/ghostwire/server.toml","w") as f:
            f.write(config_text)
        return jsonify({"success":True})
    except Exception as e:
        return jsonify({"success":False,"error":str(e)}),400

@app.route(f"/<path:panel_path>/api/logs")
def api_logs(panel_path):
    return tail_log(200)

@app.route(f"/<path:panel_path>/api/restart",methods=["POST"])
def api_restart(panel_path):
    success=restart_service()
    return jsonify({"success":success})

@app.route(f"/<path:panel_path>/api/stop",methods=["POST"])
def api_stop(panel_path):
    success=stop_service()
    return jsonify({"success":success})

def start_panel(config):
    global panel_config
    panel_config=config
    if not config.panel_enabled:
        return
    def run():
        print(f"Starting web panel on {config.panel_host}:{config.panel_port}")
        print(f"Access panel at: http://{config.panel_host}:{config.panel_port}/{config.panel_path}/")
        serve(app,host=config.panel_host,port=config.panel_port,threads=4)
    thread=threading.Thread(target=run,daemon=True)
    thread.start()
