import os
import json
import uuid
import subprocess
import sys
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, redirect, url_for

app = Flask(__name__)

SCRAPER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraper.py")
UPGRADE_CLASSES = {"PZ", "PN", "RN", "IN", "XN", "ZN"}
JOBS = {}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/search", methods=["POST"])
def search():
    form = request.form
    origin      = form.get("origin", "").upper().strip()
    destination = form.get("destination", "").upper().strip()
    depart_date = form.get("depart_date", "").strip()
    end_date    = form.get("end_date", "").strip()
    return_date = form.get("return_date", "").strip()
    trip_type   = form.get("trip_type", "oneway")
    fare_filter = form.get("fare_filter", "").upper().strip()
    username    = form.get("username", "").strip()
    password    = form.get("password", "").strip()

    cmd = [sys.executable, SCRAPER,
           "--origin", origin,
           "--destination", destination,
           "--date", depart_date,
           "--username", username,
           "--password", password]

    if trip_type == "roundtrip" and return_date:
        cmd += ["--return-date", return_date]

    if end_date and end_date > depart_date:
        cmd += ["--end-date", end_date]

    # Build list of dates the scraper will produce files for
    start_dt = datetime.strptime(depart_date, "%Y-%m-%d")
    end_dt   = datetime.strptime(end_date, "%Y-%m-%d") if end_date and end_date > depart_date else start_dt
    dates = []
    d = start_dt
    while d <= end_dt:
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)

    job_id = uuid.uuid4().hex[:8]
    proc   = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    JOBS[job_id] = {
        "proc":        proc,
        "dates":       dates,
        "origin":      origin,
        "destination": destination,
        "date":        depart_date,
        "return_date": return_date if trip_type == "roundtrip" else "",
        "fare_filter": fare_filter,
    }

    return redirect(url_for("running", job_id=job_id))


@app.route("/running/<job_id>")
def running(job_id):
    job = JOBS.get(job_id, {})
    return render_template("running.html", job_id=job_id, job=job)


def _out_file(job, date_str):
    suffix = f"_{job['return_date']}" if job.get("return_date") else ""
    return os.path.join(
        os.path.dirname(SCRAPER),
        f"results_{job['origin']}_{job['destination']}_{date_str}{suffix}.json"
    )


@app.route("/status/<job_id>")
def status(job_id):
    job = JOBS.get(job_id)
    if not job:
        return jsonify({"status": "error", "message": "Unknown job."})

    retcode = job["proc"].poll()
    if retcode is None:
        return jsonify({"status": "running"})
    if retcode != 0:
        return jsonify({"status": "error", "message": "Scraper exited with an error."})

    for date_str in job["dates"]:
        if not os.path.exists(_out_file(job, date_str)):
            return jsonify({"status": "error", "message": f"Results file not found for {date_str}."})

    return jsonify({"status": "done"})


@app.route("/results/<job_id>")
def results(job_id):
    job = JOBS.get(job_id)
    if not job:
        return redirect(url_for("index"))

    fare_filter = job["fare_filter"]
    results_by_date = []
    for date_str in job["dates"]:
        path = _out_file(job, date_str)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            data = json.load(f)
        if fare_filter:
            data = [r for r in data if any(seg["classes"].get(fare_filter, 0) > 0 for seg in r["segments"])]
        results_by_date.append({"date": date_str, "flights": data})

    return render_template("results.html",
                           results_by_date=results_by_date,
                           job=job,
                           fare_filter=fare_filter,
                           upgrade_classes=UPGRADE_CLASSES)


if __name__ == "__main__":
    app.run(debug=True)
