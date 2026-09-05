"""Serve a cached, authenticated dashboard snapshot without exposing source APIs."""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Iterable, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen


# Live-only dependencies deliberately live under the ignored runtime directory so
# this small service remains usable with the Mac's system Python 3.9.
_VENDOR = Path(__file__).resolve().parents[1] / ".runtime" / "vendor"
if _VENDOR.is_dir() and str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))


SHANGHAI = dt.timezone(dt.timedelta(hours=8), "Asia/Shanghai")
WEATHER_SECONDS = 30 * 60
EXPORT_SECONDS = 60
REQUEST_TIMEOUT = 8
EMPTY_ALMANAC = {"yi": "暂无", "ji": "暂无"}


def _epoch() -> int:
    return int(time.time())


def _date_range(today: Optional[dt.date] = None) -> tuple[dt.date, dt.date]:
    """First of previous month through first of the month after next."""
    today = today or dt.datetime.now(SHANGHAI).date()
    this_month = today.replace(day=1)
    end = (this_month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    end = (end.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
    previous = (this_month - dt.timedelta(days=1)).replace(day=1)
    return previous, end


def _as_date(value: Any, fallback: dt.date) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return fallback


def _calendar_day(day: dt.date) -> Dict[str, Any]:
    unavailable = {
        "lunar": "暂无",
        "solar_term": "暂无",
        "next_solar_term": "暂无",
        "almanac": copy.deepcopy(EMPTY_ALMANAC),
    }
    try:
        from lunar_python import Solar  # type: ignore

        lunar = Solar.fromYmd(day.year, day.month, day.day).getLunar()
        previous_jie_qi = lunar.getPrevJieQi()
        jie_qi = lunar.getJieQi() or (previous_jie_qi.getName() if previous_jie_qi else "暂无")
        next_jie_qi = lunar.getNextJieQi()
        next_name = next_jie_qi.getName() if next_jie_qi else "暂无"
        yi = lunar.getDayYi() or "暂无"
        ji = lunar.getDayJi() or "暂无"
        return {
            "lunar": "农历%s月%s · %s%s年 · %s" % (
                lunar.getMonthInChinese(), lunar.getDayInChinese(),
                lunar.getYearInGanZhi(), lunar.getYearShengXiao(), jie_qi),
            "solar_term": jie_qi,
            "next_solar_term": next_name or "暂无",
            "almanac": {"yi": yi, "ji": ji},
        }
    except Exception:
        return unavailable


def _weather_icon(code: Optional[int]) -> str:
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "cloud-sun"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "cloud-fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "cloud-rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snowflake"
    if code in (95, 96, 99):
        return "cloud-lightning"
    return "cloud"


def _weather_condition(code: Optional[int]) -> Optional[str]:
    values = {0: "晴", 1: "大部晴朗", 2: "局部多云", 3: "阴", 45: "雾", 48: "雾凇",
              51: "毛毛雨", 53: "毛毛雨", 55: "毛毛雨", 61: "小雨", 63: "中雨", 65: "大雨",
              71: "小雪", 73: "中雪", 75: "大雪", 80: "阵雨", 81: "阵雨", 82: "强阵雨",
              95: "雷暴", 96: "雷暴", 99: "雷暴"}
    return values.get(code)


def _empty_weather(location: str) -> Dict[str, Any]:
    return {"location": location, "condition": None, "icon": "cloud", "temperature": None,
            "low": None, "high": None, "rain_probability": None, "uv": None,
            "wind_level": None, "updated_at": None, "ok": False}


class SnapshotHub:
    def __init__(self, data_dir: Path | str, exporter: Optional[Path | str] = None,
                 city: str = "上海", now=time.time) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.city = city
        self.latitude, self.longitude = 31.2304, 121.4737
        self.location_path = self.data_dir / "weather-location.json"
        self.now = now
        self.exporter = Path(exporter) if exporter else Path(__file__).resolve().parents[1] / "connectors" / "macos" / "export_snapshot.py"
        self.export_path = self.data_dir / "apple.json"
        self.state_path = self.data_dir / "snapshot-cache.json"
        self.lock = threading.RLock()
        self.token = self._load_token()
        start, end = _date_range()
        self.state: Dict[str, Any] = {
            "events": [], "tasks": [], "range_start": start.isoformat(), "range_end": end.isoformat(),
            "timezone": "Asia/Shanghai", "generated_at": None,
            "sources": {"calendar": {"ok": False, "updated_at": None, "count": 0, "error": "not yet refreshed"},
                        "reminders": {"ok": False, "updated_at": None, "count": 0, "error": "not yet refreshed"}},
            "weather": _empty_weather(city),
        }
        self._load_state()
        self._load_location()

    def _load_location(self) -> bool:
        try:
            config = json.loads(self.location_path.read_text(encoding="utf-8"))
            city = str(config["city"]).strip()
            latitude, longitude = float(config["latitude"]), float(config["longitude"])
            if not city or len(city) > 30 or not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                return False
        except (OSError, ValueError, TypeError, KeyError):
            return False
        changed = (city, latitude, longitude) != (self.city, self.latitude, self.longitude)
        self.city, self.latitude, self.longitude = city, latitude, longitude
        if changed and self.state["weather"].get("location") != city:
            self.state["weather"] = _empty_weather(city)
        return changed

    def _load_token(self) -> str:
        path = self.data_dir / "device-token"
        if path.exists():
            try:
                token = path.read_text(encoding="utf-8").strip()
                if token:
                    os.chmod(path, 0o600)
                    return token
            except OSError:
                pass
        token = secrets.token_urlsafe(32)
        descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
        return token

    def _load_state(self) -> None:
        try:
            cached = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(cached, dict):
                self.state.update({key: cached[key] for key in self.state if key in cached})
        except (OSError, ValueError, TypeError):
            return

    def _save_state(self) -> None:
        temporary = self.state_path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(self.state, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.state_path)
        os.chmod(self.state_path, 0o600)

    def _mark_export_failure(self, message: str) -> None:
        for source in ("calendar", "reminders"):
            previous = self.state["sources"].get(source, {})
            self.state["sources"][source] = {"ok": False, "updated_at": previous.get("updated_at"),
                                               "count": previous.get("count", 0), "error": message}

    def refresh_export(self) -> bool:
        failure = None
        try:
            completed = subprocess.run([sys.executable, str(self.exporter), "--output", str(self.export_path)],
                                       capture_output=True, text=True, timeout=30, check=False)
            if completed.returncode != 0:
                raise ValueError("exporter failed")
            incoming = json.loads(self.export_path.read_text(encoding="utf-8"))
            if not isinstance(incoming, dict):
                raise ValueError("invalid exporter document")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            failure = "exporter unavailable"
        with self.lock:
            if failure:
                self._mark_export_failure(failure)
                self._save_state()
                return False
            self._merge_export(incoming)
            self._save_state()
            return True

    def _merge_export(self, incoming: Dict[str, Any]) -> None:
        sources = incoming.get("sources") if isinstance(incoming.get("sources"), dict) else {}
        for name, key in (("calendar", "events"), ("reminders", "tasks")):
            source = sources.get(name) if isinstance(sources.get(name), dict) else {}
            ok = bool(source.get("ok"))
            if ok and isinstance(incoming.get(key), list):
                self.state[key] = incoming[key]
            previous = self.state["sources"].get(name, {})
            self.state["sources"][name] = {
                "ok": ok,
                "updated_at": source.get("updated_at") if ok else previous.get("updated_at"),
                "count": len(self.state[key]),
            }
            if source.get("error"):
                self.state["sources"][name]["error"] = str(source["error"])
        for name in ("generated_at", "timezone", "range_start", "range_end"):
            if incoming.get(name) is not None:
                self.state[name] = incoming[name]

    def refresh_weather(self) -> bool:
        try:
            query = urlencode({"latitude": self.latitude, "longitude": self.longitude, "timezone": "Asia/Shanghai",
                               "current": "temperature_2m,weather_code",
                               "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,uv_index_max,wind_speed_10m_max,weather_code"})
            request = Request("https://api.open-meteo.com/v1/forecast?" + query, headers={"User-Agent": "kindle-snapshot-hub/1"})
            with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                doc = json.loads(response.read().decode("utf-8"))
            current, daily = doc.get("current", {}), doc.get("daily", {})
            code = current.get("weather_code")
            wind = (daily.get("wind_speed_10m_max") or [None])[0]
            weather = {"location": self.city, "condition": _weather_condition(code),
                "icon": _weather_icon(code), "temperature": current.get("temperature_2m"),
                "low": (daily.get("temperature_2m_min") or [None])[0], "high": (daily.get("temperature_2m_max") or [None])[0],
                "rain_probability": (daily.get("precipitation_probability_max") or [None])[0], "uv": (daily.get("uv_index_max") or [None])[0],
                "wind_speed_kmh": wind, "updated_at": _epoch(), "ok": True}
        except Exception:
            with self.lock:
                self.state["weather"]["ok"] = False
                self._save_state()
            return False
        with self.lock:
            self.state["weather"] = weather
            self._save_state()
        return True

    def refresh_due_weather(self) -> None:
        changed = self._load_location()
        weather_at = self.state["weather"].get("updated_at")
        if changed or not weather_at or self.now() - weather_at >= WEATHER_SECONDS:
            self.refresh_weather()

    def build_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            start, end = _date_range()
            range_start = _as_date(self.state.get("range_start"), start)
            range_end = _as_date(self.state.get("range_end"), end)
            if range_end <= range_start:
                range_start, range_end = start, end
            days: Dict[str, Dict[str, Any]] = {}
            cursor = range_start
            while cursor < range_end:
                days[cursor.isoformat()] = _calendar_day(cursor)
                cursor += dt.timedelta(days=1)
            weather = copy.deepcopy(self.state["weather"])
            weather["location"] = self.city
            # Open-Meteo supplies wind speed in km/h, not Beaufort levels.
            speed = weather.pop("wind_speed_kmh", None)
            if speed is None:
                speed = weather.get("wind_level")
            if isinstance(speed, (int, float)):
                weather["wind_level"] = sum(speed >= limit for limit in (1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118))
            sources = copy.deepcopy(self.state["sources"])
            sources["weather"] = {"ok": bool(weather.get("ok")), "updated_at": weather.get("updated_at")}
            return {"schema_version": 1, "version": 1, "generated_at": self.state.get("generated_at") or 0, "timezone": "Asia/Shanghai",
                    "range_start": range_start.isoformat(), "range_end": range_end.isoformat(),
                    "utc_offset": 28800, "events": copy.deepcopy(self.state["events"]), "tasks": copy.deepcopy(self.state["tasks"]),
                    "days": days, "weather": weather, "sources": sources}

    def health(self) -> Dict[str, Any]:
        with self.lock:
            return {"ok": True, "events": len(self.state["events"]), "tasks": len(self.state["tasks"]),
                    "calendar_ok": bool(self.state["sources"]["calendar"].get("ok")),
                    "reminders_ok": bool(self.state["sources"]["reminders"].get("ok")),
                    "weather_ok": bool(self.state["weather"].get("ok"))}


class SnapshotHandler(BaseHTTPRequestHandler):
    hub: SnapshotHub
    log_path: Optional[Path] = None
    server_version = "KindleSnapshotHub/1"

    def log_message(self, format: str, *args: Any) -> None:
        # Request paths and status are safe; never log response bodies or credentials.
        line = "hub %s\n" % (format % args)
        if self.log_path:
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write(line)
            os.chmod(self.log_path, 0o600)
        else:
            sys.stderr.write(line)

    def _json(self, status: int, document: Dict[str, Any]) -> None:
        payload = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, self.hub.health())
            return
        if self.path != "/api/v1/snapshot":
            self._json(404, {"error": "not found"})
            return
        expected = "Bearer " + self.hub.token
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
            self.send_response(401)
            self.send_header("WWW-Authenticate", "Bearer")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        self._json(200, self.hub.build_snapshot())


def _worker(hub: SnapshotHub, stop: threading.Event) -> None:
    while not stop.is_set():
        hub.refresh_export()
        hub.refresh_due_weather()
        stop.wait(EXPORT_SECONDS)


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Local read-only Kindle snapshot hub")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=18501)
    parser.add_argument("--data-dir", default=".runtime/hub")
    args = parser.parse_args(argv)
    hub = SnapshotHub(args.data_dir)
    pid_path = hub.data_dir / "server.pid"
    pid_path.write_text(str(os.getpid()) + "\n", encoding="ascii")
    os.chmod(pid_path, 0o600)
    SnapshotHandler.hub = hub
    SnapshotHandler.log_path = hub.data_dir / "server.log"
    server = ThreadingHTTPServer((args.host, args.port), SnapshotHandler)
    stop = threading.Event()
    thread = threading.Thread(target=_worker, args=(hub, stop), daemon=True)
    thread.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
