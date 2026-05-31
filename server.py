from flask import Flask, render_template, jsonify, request, Response
from datetime import datetime
import subprocess
import threading
import queue
import json
from gps_reader import start_gps, get_current_gps
import cv2



app = Flask(__name__)
start_gps()

camera = None

# ── Vision SSE pub-sub ────────────────────────────────────────────────────────
_vision_subscribers: list[queue.Queue] = []
_vision_lock = threading.Lock()


def _broadcast_vision(text: str):
    """Push a Gemini result to every connected browser tab."""
    payload = json.dumps({"text": text})
    with _vision_lock:
        for q in _vision_subscribers:
            q.put(payload)
# ─────────────────────────────────────────────────────────────────────────────


DESTINATIONS = {
    "main building":                          (31.395803, 75.536444),
    "ece department":                         (31.395803, 75.536444),
    "electronics department":                 (31.395803, 75.536444),
    "ice department":                         (31.395803, 75.536444),
    "instrumentation and control department": (31.395803, 75.536444),
    "campus cafe":                            (31.396506591277284, 75.5367096915818),
    "cc":                                     (31.396506591277284, 75.5367096915818),
    "new gym":                                (31.39675376993198, 75.53432403830317),
    "gym":                                    (31.39675376993198, 75.53432403830317),
    "snackers":                               (31.397033086170545, 75.5339485290579),
    "sac":                                    (31.397033086170545, 75.5339485290579),
    "rhimjhim shop":                          (31.397781741169936, 75.53391634255115),
    "rimjhim":                                (31.397781741169936, 75.53391634255115),
    "rhimjhim":                               (31.397781741169936, 75.53391634255115),
    "barber shop":                            (31.397781741169936, 75.53391634255115),
    "barber":                                 (31.397781741169936, 75.53391634255115),
    "juice shop near rhimjhim":               (31.397781741169936, 75.53391634255115),
    "juice shop":                             (31.397781741169936, 75.53391634255115),
    "juice":                                  (31.397781741169936, 75.53391634255115),
    "science block":                          (31.39730597893472, 75.53451200316812),
    "new library":                            (31.396839695616013, 75.53455782535035),
    "reading hall":                           (31.396737831660626, 75.53486278793471),
    "new lecture hall":                       (31.397126953549293, 75.53531065916098),
    "akam lt":                                (31.397126953549293, 75.53531065916098),
    "new lt":                                 (31.397126953549293, 75.53531065916098),
    "akam lecture theatre":                   (31.397126953549293, 75.53531065916098),
    "nitj library":                           (31.39649303467398, 75.53527138368831),
    "library":                                (31.39649303467398, 75.53527138368831),
    "yadav canteen":                          (31.397746408859057, 75.53660394291427),
    "yadav":                                  (31.397746408859057, 75.53660394291427),
    "workshop":                               (31.39786997835437, 75.53465075248918),
    "biotechnology department":               (31.398059208538044, 75.5355241168865),
    "bt department":                          (31.398059208538044, 75.5355241168865),
    "bh1":                                    (31.39716074055119, 75.5335839270609),
    "boys hostel 1":                          (31.39716074055119, 75.5335839270609),
    "bh2":                                    (31.397921428320927, 75.53316868712795),
    "boys hostel 2":                          (31.397921428320927, 75.53316868712795),
    "bh3":                                    (31.39797975563799, 75.53321439252568),
    "boys hostel 3":                          (31.39797975563799, 75.53321439252568),
    "bh4":                                    (31.398415719363125, 75.53287729422081),
    "boys hostel 4":                          (31.398415719363125, 75.53287729422081),
    "bh5":                                    (31.398573919957006, 75.53261883430451),
    "boys hostel 5":                          (31.398573919957006, 75.53261883430451),
    "bh6":                                    (31.398470014970883, 75.53636604746389),
    "boys hostel 6":                          (31.398470014970883, 75.53636604746389),
    "bh7":                                    (31.398946443393303, 75.53710828764628),
    "boys hostel 7":                          (31.398946443393303, 75.53710828764628),
    "bh7e":                                   (31.398946443393303, 75.53710828764628),
    "boys hostel 7e":                         (31.398946443393303, 75.53710828764628),
    "mbh b":                                  (31.399260682093164, 75.5360869651553),
    "mega hostel boys b":                     (31.399260682093164, 75.5360869651553),
    "mbh a":                                  (31.399108631240708, 75.53523784238664),
    "mega hostel boys a":                     (31.399108631240708, 75.53523784238664),
    "mbh f":                                  (31.39980806312265, 75.5346321743978),
    "mega hostel boys f":                     (31.39980806312265, 75.5346321743978),
    "mega guest house":                       (31.399488757910042, 75.5350418909785),
    "night canteen":                          (31.39874370818996, 75.53551692469523),
    "nc":                                     (31.39874370818996, 75.53551692469523),
    "nescafe":                                (31.39845480976864, 75.53555255222399),
    "badminton court":                        (31.395561280369648, 75.5327687906816),
    "gymnasium":                              (31.395561280369648, 75.5327687906816),
    "oat":                                    (31.394684150549345, 75.5336941311968),
    "open air theatre":                       (31.394684150549345, 75.5336941311968),
    "it building":                            (31.395028760848973, 75.53577258628128),
    "it department":                          (31.395028760848973, 75.53577258628128),
    "admin block":                            (31.396053444727368, 75.53737962484885),
    "administrative block":                   (31.396053444727368, 75.53737962484885),
    "dispensary":                             (31.394328002865603, 75.53772426688454),
    "guest house":                            (31.39394787252591, 75.53649672179611),
    "director bungalow":                      (31.393395854405455, 75.53744932778478),
    "community centre":                       (31.392909943564913, 75.53631859221795),
    "nitj temple":                            (31.391951336564222, 75.53592748162728),
    "mandir":                                 (31.391951336564222, 75.53592748162728),
    "temple":                                 (31.391951336564222, 75.53592748162728),
    "mega girls hostel":                      (31.39450020380706, 75.53967271134556),
    "lecture theatre":                        (31.396759406931427, 75.53707257705503),
    "lt":                                     (31.396759406931427, 75.53707257705503),
    "main ground":                            (31.396647680131572, 75.53229887191691),
    "mbh ground":                             (31.39836300081259, 75.53480121730836),
}

def get_camera():
    global camera
    if camera is None:
        camera = cv2.VideoCapture(0)  # 0 = first webcam; try /dev/video0 if this fails
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    return camera

def generate_frames():
    cam = get_camera()
    while True:
        success, frame = cam.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )

@app.route('/capture')
def capture():
    """Return a single JPEG frame from the camera (used by button_vision.py)."""
    cam = get_camera()
    ok, frame = cam.read()
    if not ok:
        return Response("Camera error", status=503)
    ret, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ret:
        return Response("Encode error", status=500)
    return Response(buf.tobytes(), mimetype='image/jpeg')

def resolve_destination(spoken_text):
    query = spoken_text.lower().strip()
    filler = ["take me to", "go to", "navigate to", "i want to go to",
              "please go to", "directions to", "how to reach", "where is"]
    for f in filler:
        query = query.replace(f, "").strip()
    print(f"[RESOLVE] Cleaned query: {query}")
    if query in DESTINATIONS:
        coords = DESTINATIONS[query]
        print(f"[RESOLVE] Exact: {query} -> {coords}")
        return coords[0], coords[1], query
    for key, coords in DESTINATIONS.items():
        if query in key or key in query:
            print(f"[RESOLVE] Partial: {query} -> {key}")
            return coords[0], coords[1], key
    query_words = set(query.split())
    best_key = None
    best_score = 0
    for key, coords in DESTINATIONS.items():
        key_words = set(key.split())
        shared = query_words & key_words
        if shared and len(shared) > best_score:
            best_score = len(shared)
            best_key = key
    if best_key:
        coords = DESTINATIONS[best_key]
        print(f"[RESOLVE] Fuzzy: {query} -> {best_key}")
        return coords[0], coords[1], best_key
    print(f"[RESOLVE] No match: {query}")
    return None

def get_battery():
    try:
        result = subprocess.run(
            ["cat", "/sys/class/power_supply/BAT0/capacity"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
    except:
        pass
    return None

def build_maps_url(dest_lat, dest_lon, start_lat, start_lon):
    # comgooglemaps:// = opens Google Maps APP directly on Android
    # ?saddr = start, &daddr = destination, &directionsmode=walking
    # This URL format skips the Maps browser page entirely
    # and launches straight into turn-by-turn navigation in the app
    return (
        "https://www.google.com/maps/dir/?api=1"
        f"&origin={start_lat},{start_lon}"
        f"&destination={dest_lat},{dest_lon}"
        "&travelmode=walking"
        "&dir_action=navigate"
    )

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/guardian")
def guardian():
    return render_template("guardian.html")

@app.route("/destination", methods=["POST"])
def destination():
    data = request.get_json()
    raw_destination = data.get("destination", "").strip()
    print(f"\n[DESTINATION] Received: {raw_destination}")
    gps = get_current_gps()
    if gps["fix"]:
        start_lat = gps["latitude"]
        start_lon = gps["longitude"]
        print(f"[GPS] Live fix: {start_lat}, {start_lon}")
    else:
        start_lat = 31.3968
        start_lon = 75.5353
        print("[GPS] No fix. Using fallback.")
    result = resolve_destination(raw_destination)
    if result is None:
        return jsonify({"status": "not_found", "destination": raw_destination})
    dest_lat, dest_lon, matched_name = result
    maps_url = build_maps_url(dest_lat, dest_lon, start_lat, start_lon)
    print(f"[DESTINATION] Matched: {matched_name}")
    print(f"[MAPS URL] {maps_url}")
    return jsonify({
        "status":       "success",
        "destination":  raw_destination,
        "matched_name": matched_name,
        "latitude":     dest_lat,
        "longitude":    dest_lon,
        "start_lat":    start_lat,
        "start_lon":    start_lon,
        "maps_url":     maps_url,
        "gps_fix":      gps["fix"]
    })

@app.route("/guardian/location")
def guardian_location():
    gps = get_current_gps()
    battery = get_battery()
    return jsonify({
        "fix":        gps["fix"],
        "latitude":   gps["latitude"],
        "longitude":  gps["longitude"],
        "satellites": gps["satellites"],
        "hdop":       gps["hdop"],
        "timestamp":  gps["timestamp"] or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "battery":    battery
    })

@app.route("/vision/result", methods=["POST"])
def vision_result():
    """button_vision.py POSTs the Gemini description here."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if text:
        _broadcast_vision(text)
    return jsonify({"status": "ok"})


@app.route("/vision/stream")
def vision_stream():
    """Browser connects here via EventSource to receive Gemini descriptions."""
    q: queue.Queue = queue.Queue()
    with _vision_lock:
        _vision_subscribers.append(q)

    def generate():
        try:
            while True:
                try:
                    payload = q.get(timeout=25)
                    yield f"data: {payload}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"   # prevents proxy timeouts
        finally:
            with _vision_lock:
                if q in _vision_subscribers:
                    _vision_subscribers.remove(q)

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
