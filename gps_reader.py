import serial
import serial.tools.list_ports
import threading
import time
from datetime import datetime

gps_state = {
    "latitude":   None,
    "longitude":  None,
    "satellites": None,
    "hdop":       None,
    "fix":        False,
    "timestamp":  None,
    "raw":        None
}

gps_lock = threading.Lock()

def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    for port in ports:
        desc = port.description.lower()
        if "arduino" in desc or "ch340" in desc or "ttyusb" in port.device.lower() or "ttyacm" in port.device.lower():
            print(f"[GPS] Arduino found on: {port.device}")
            return port.device
    for fallback in ["/dev/ttyUSB0", "/dev/ttyACM0", "/dev/ttyUSB1", "/dev/ttyACM1"]:
        try:
            s = serial.Serial(fallback, 9600, timeout=1)
            s.close()
            print(f"[GPS] Using fallback port: {fallback}")
            return fallback
        except:
            continue
    return None

# ─────────────────────────────────────────
# Parses BOTH formats:
#
# Format A (new):
#   LAT:31.399822,LON:75.534565,SAT:6,HDOP:1.2
#
# Format B (your working code):
#   Latitude: 31.399822
#   Longitude: 75.534565
#   Satellites: 6
#   Altitude: 191.80 m
#   ------------------
# ─────────────────────────────────────────

# Temporary buffer for Format B multi-line parsing
_buffer = {
    "latitude":   None,
    "longitude":  None,
    "satellites": None,
}

def parse_gps_line(line):
    global _buffer
    line = line.strip()

    # ── NO_FIX ──
    if line == "NO_FIX":
        return {"fix": False}

    # ── Format A: single line ──
    if line.startswith("LAT:"):
        try:
            parts = {}
            for segment in line.split(","):
                key, value = segment.split(":")
                parts[key.strip()] = value.strip()
            return {
                "fix":        True,
                "latitude":   float(parts["LAT"]),
                "longitude":  float(parts["LON"]),
                "satellites": int(parts.get("SAT", 0)),
                "hdop":       float(parts.get("HDOP", 0.0)),
                "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        except Exception as e:
            print(f"[GPS] Format A parse error: {e}")
            return None

    # ── Format B: multi-line ──
    if line.startswith("Latitude:"):
        try:
            _buffer["latitude"] = float(line.split(":")[1].strip())
        except:
            pass
        return None

    if line.startswith("Longitude:"):
        try:
            _buffer["longitude"] = float(line.split(":")[1].strip())
        except:
            pass
        return None

    if line.startswith("Satellites:"):
        try:
            _buffer["satellites"] = int(line.split(":")[1].strip())
        except:
            pass
        return None

    # Separator line — means one full reading is complete
    if line.startswith("---"):
        if _buffer["latitude"] and _buffer["longitude"]:
            result = {
                "fix":        True,
                "latitude":   _buffer["latitude"],
                "longitude":  _buffer["longitude"],
                "satellites": _buffer["satellites"] or 0,
                "hdop":       0.0,
                "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            # Reset buffer
            _buffer = {"latitude": None, "longitude": None, "satellites": None}
            return result

    return None


def gps_reader_thread():
    global gps_state
    port = find_arduino_port()
    if not port:
        print("[GPS] ERROR: Arduino not found. GPS unavailable.")
        return
    while True:
        try:
            print(f"[GPS] Connecting to {port} at 115200 baud...")
            ser = serial.Serial(port, 115200, timeout=5)
            print(f"[GPS] Connected. Waiting for GPS data...")
            while True:
                raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not raw_line:
                    continue
                print(f"[GPS RAW] {raw_line}")
                parsed = parse_gps_line(raw_line)
                if parsed is None:
                    continue
                with gps_lock:
                    if parsed.get("fix"):
                        gps_state.update({
                            "fix":        True,
                            "latitude":   parsed["latitude"],
                            "longitude":  parsed["longitude"],
                            "satellites": parsed["satellites"],
                            "hdop":       parsed["hdop"],
                            "timestamp":  parsed["timestamp"],
                            "raw":        raw_line
                        })
                        print(f"[GPS] Fix: {parsed['latitude']}, {parsed['longitude']} | Sats: {parsed['satellites']}")
                    else:
                        gps_state["fix"] = False
                        gps_state["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        print("[GPS] No fix yet...")
        except serial.SerialException as e:
            print(f"[GPS] Serial error: {e}. Reconnecting in 5s...")
            time.sleep(5)
        except Exception as e:
            print(f"[GPS] Unexpected error: {e}. Reconnecting in 5s...")
            time.sleep(5)

def get_current_gps():
    with gps_lock:
        return dict(gps_state)

def start_gps():
    thread = threading.Thread(target=gps_reader_thread, daemon=True)
    thread.start()
    print("[GPS] Reader thread started.")

if __name__ == "__main__":
    print("[GPS] Running standalone test...")
    start_gps()
    try:
        while True:
            state = get_current_gps()
            if state["fix"]:
                print(f"[TEST] Lat: {state['latitude']} | Lon: {state['longitude']} | Sats: {state['satellites']}")
            else:
                print("[TEST] Waiting for GPS fix...")
            time.sleep(3)
    except KeyboardInterrupt:
        print("[GPS] Stopped.")
