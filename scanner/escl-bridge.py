# SPDX-License-Identifier: GPL-2.0-or-later
"""eSCL (AirScan) bridge for the Canon PIXMA MG8150 scanner.

macOS Image Capture and Preview find eSCL scanners over Bonjour (_uscan._tcp).
The MG8150 predates eSCL, so this serves the eSCL HTTP API on the Mac and runs
SANE's `scanimage` (pixma backend, BJNP over Wi-Fi) for each scan.

Usage: python3 escl-bridge.py [--port 8090] [--device pixma:MG8100_192.168.1.191]
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

NAME = "Canon PIXMA MG8150"
UUID = "4d8e1c2a-8150-4b1f-9c3e-6d1a2b3c8150"
SCANIMAGE = "/opt/homebrew/bin/scanimage"
RESOLUTIONS = (75, 150, 300, 600)
MAX_W, MAX_H = 2550, 3508  # platen in 1/300 inch (216 x 297 mm)

NS = {"scan": "http://schemas.hp.com/imaging/escl/2011/05/03",
      "pwg": "http://www.pwg.org/schemas/2010/12/sm"}
XMLNS = ' xmlns:scan="%s" xmlns:pwg="%s"' % (NS["scan"], NS["pwg"])

class Job:
    """One eSCL scan job. The scan starts as soon as the job is created, like
    a real AirScan scanner; Apple's client polls ScannerStatus for the job's
    state and only then fetches NextDocument."""

    def __init__(self, settings):
        self.id = str(uuid.uuid4())
        self.settings = settings
        self.created = time.time()
        self.state = "Processing"     # -> Completed / Aborted / Canceled
        self.data = None
        self.ctype = None
        self.delivered = False
        self.done = threading.Event()


jobs = {}                             # job id -> Job
scan_lock = threading.Lock()


def capabilities(host):
    res = "".join(
        "<scan:DiscreteResolution><scan:XResolution>%d</scan:XResolution>"
        "<scan:YResolution>%d</scan:YResolution></scan:DiscreteResolution>" % (r, r)
        for r in RESOLUTIONS)
    fmts = "".join("<pwg:DocumentFormat>%s</pwg:DocumentFormat>"
                   "<scan:DocumentFormatExt>%s</scan:DocumentFormatExt>" % (f, f)
                   for f in ("image/jpeg", "application/pdf"))
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<scan:ScannerCapabilities{XMLNS}>
<pwg:Version>2.63</pwg:Version>
<pwg:MakeAndModel>{NAME}</pwg:MakeAndModel>
<pwg:SerialNumber>MG8150</pwg:SerialNumber>
<scan:UUID>{UUID}</scan:UUID>
<scan:AdminURI>http://{host}/</scan:AdminURI>
<scan:Platen><scan:PlatenInputCaps>
<scan:MinWidth>16</scan:MinWidth><scan:MaxWidth>{MAX_W}</scan:MaxWidth>
<scan:MinHeight>16</scan:MinHeight><scan:MaxHeight>{MAX_H}</scan:MaxHeight>
<scan:MaxScanRegions>1</scan:MaxScanRegions>
<scan:SettingProfiles><scan:SettingProfile>
<scan:ColorModes><scan:ColorMode>RGB24</scan:ColorMode><scan:ColorMode>Grayscale8</scan:ColorMode></scan:ColorModes>
<scan:DocumentFormats>{fmts}</scan:DocumentFormats>
<scan:SupportedResolutions><scan:DiscreteResolutions>{res}</scan:DiscreteResolutions></scan:SupportedResolutions>
<scan:ColorSpaces><scan:ColorSpace>sRGB</scan:ColorSpace></scan:ColorSpaces>
</scan:SettingProfile></scan:SettingProfiles>
<scan:SupportedIntents><scan:Intent>Document</scan:Intent><scan:Intent>TextAndGraphic</scan:Intent>
<scan:Intent>Photo</scan:Intent><scan:Intent>Preview</scan:Intent></scan:SupportedIntents>
<scan:MaxOpticalXResolution>600</scan:MaxOpticalXResolution>
<scan:MaxOpticalYResolution>600</scan:MaxOpticalYResolution>
</scan:PlatenInputCaps></scan:Platen>
</scan:ScannerCapabilities>"""


def status():
    busy = any(j.state == "Processing" and not j.done.is_set() for j in jobs.values())
    infos = []
    for j in sorted(jobs.values(), key=lambda j: j.created):
        to_transfer = 1 if j.done.is_set() and j.data and not j.delivered else 0
        completed = 1 if j.delivered else 0
        state = j.state
        if state == "Processing":
            reason = "JobScanningAndTransferring" if to_transfer else "JobScanning"
        else:
            reason = {"Completed": "JobCompletedSuccessfully", "Aborted": "AbortedBySystem",
                      "Canceled": "JobCanceledByUser"}[state]
        infos.append(
            f"<scan:JobInfo><pwg:JobUri>/eSCL/ScanJobs/{j.id}</pwg:JobUri>"
            f"<pwg:JobUuid>{j.id}</pwg:JobUuid><scan:Age>{int(time.time() - j.created)}</scan:Age>"
            f"<pwg:ImagesCompleted>{completed}</pwg:ImagesCompleted>"
            f"<pwg:ImagesToTransfer>{to_transfer}</pwg:ImagesToTransfer>"
            f"<pwg:JobState>{state}</pwg:JobState>"
            f"<pwg:JobStateReasons><pwg:JobStateReason>{reason}</pwg:JobStateReason></pwg:JobStateReasons>"
            f"</scan:JobInfo>")
    return (f'<?xml version="1.0" encoding="UTF-8"?>\n<scan:ScannerStatus{XMLNS}>'
            f"<pwg:Version>2.63</pwg:Version><pwg:State>{'Processing' if busy else 'Idle'}</pwg:State>"
            f"<scan:Jobs>{''.join(infos)}</scan:Jobs></scan:ScannerStatus>")


def parse_settings(body):
    root = ET.fromstring(body)

    def find(path, default=None):
        el = root.find(path, NS)
        return el.text.strip() if el is not None and el.text else default

    res = int(find("scan:XResolution", "300"))
    res = min(RESOLUTIONS, key=lambda r: abs(r - res))
    fmt = find("scan:DocumentFormatExt") or find("pwg:DocumentFormat") or "image/jpeg"
    region = "pwg:ScanRegions/pwg:ScanRegion/pwg:"
    return {
        "res": res,
        "gray": find("scan:ColorMode", "RGB24").startswith("Grayscale"),
        "pdf": fmt == "application/pdf",
        "w": int(find(region + "Width", str(MAX_W))),
        "h": int(find(region + "Height", str(MAX_H))),
        "x": int(find(region + "XOffset", "0")),
        "y": int(find(region + "YOffset", "0")),
    }


def run_scan(device, s):
    mm = lambda v: "%.2f" % (v / 300 * 25.4)
    fmt = "pdf" if s["pdf"] else "jpeg"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "page." + fmt)
        cmd = [SCANIMAGE, "-d", device, "--resolution", str(s["res"]),
               "--mode", "Gray" if s["gray"] else "Color",
               "-l", mm(s["x"]), "-t", mm(s["y"]), "-x", mm(s["w"]), "-y", mm(s["h"]),
               "--format=" + fmt, "-o", out]
        with scan_lock:
            subprocess.run(cmd, check=True, timeout=600, capture_output=True)
        with open(out, "rb") as f:
            return f.read(), ("application/pdf" if s["pdf"] else "image/jpeg")


def scan_job(device, job):
    try:
        job.data, job.ctype = run_scan(device, job.settings)
    except Exception as e:  # scanner busy / offline
        sys.stderr.write("scan failed: %r\n" % e)
        job.state = "Aborted"
    finally:
        job.done.set()
    # Forget finished jobs after a while so the status list stays short.
    for old in [j for j in jobs.values() if time.time() - j.created > 600]:
        jobs.pop(old.id, None)


class Handler(BaseHTTPRequestHandler):
    device = None

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.address_string(), fmt % args))

    def send(self, code, body=b"", ctype="text/xml", headers=()):
        if isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path == "/eSCL/ScannerCapabilities":
            return self.send(200, capabilities(self.headers.get("Host", "localhost")))
        if path == "/eSCL/ScannerStatus":
            return self.send(200, status())
        m = re.fullmatch(r"/eSCL/ScanJobs/([\w-]+)/NextDocument", path)
        if m:
            job = jobs.get(m.group(1))
            if job is None or job.delivered or job.state != "Processing":
                return self.send(404)          # no (more) pages: the client stops here
            job.done.wait(timeout=600)
            if not job.data:
                return self.send(503)
            job.delivered = True
            job.state = "Completed"
            return self.send(200, job.data, job.ctype)
        if path in ("", "/"):
            return self.send(200, f"<html><body>{NAME} eSCL bridge</body></html>", "text/html")
        self.send(404)

    def do_POST(self):
        if self.path.rstrip("/") != "/eSCL/ScanJobs":
            return self.send(404)
        length = int(self.headers.get("Content-Length", 0))
        if length > 64 * 1024:  # ScanSettings is ~1 KB; refuse anything big
            return self.send(413)
        body = self.rfile.read(length)
        try:
            settings = parse_settings(body)
        except Exception as e:
            sys.stderr.write("bad ScanSettings: %r\n" % e)
            return self.send(400)
        if any(j.state == "Processing" for j in jobs.values()):
            return self.send(503)              # one scan at a time
        job = Job(settings)
        jobs[job.id] = job
        threading.Thread(target=scan_job, args=(self.device, job), daemon=True).start()
        host = self.headers.get("Host", "localhost")
        self.send(201, headers=[("Location", f"http://{host}/eSCL/ScanJobs/{job.id}")])

    def do_DELETE(self):
        m = re.fullmatch(r"/eSCL/ScanJobs/([\w-]+)", self.path.rstrip("/"))
        if m:
            job = jobs.get(m.group(1))
            if job and job.state == "Processing" and not job.delivered:
                job.state = "Canceled"
            return self.send(200)
        self.send(404)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--device", default="pixma:MG8100_192.168.1.191")
    args = ap.parse_args()
    Handler.device = args.device

    server = ThreadingHTTPServer(("", args.port), Handler)
    txt = ["txtvers=1", "vers=2.63", "rs=eSCL", f"ty={NAME}", "note=",
           "pdl=application/pdf,image/jpeg", f"uuid={UUID}", "cs=color,grayscale",
           "is=platen", "duplex=F", f"adminurl=http://{socket.gethostname()}:{args.port}/"]
    # dns-sd stays running for as long as the advertisement should exist.
    advert = subprocess.Popen(["/usr/bin/dns-sd", "-R", NAME, "_uscan._tcp", "local",
                               str(args.port), *txt], stdout=subprocess.DEVNULL)
    try:
        server.serve_forever()
    finally:
        advert.terminate()


if __name__ == "__main__":
    main()
