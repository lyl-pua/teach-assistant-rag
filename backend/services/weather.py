# -*- coding: utf-8 -*-
"""
天气服务（主：Open-Meteo 免 key，兜底：和风 QWeather 需 Web API 凭据）
Open-Meteo → 汉寿 28.914, 111.976 实测稳定，无绑定、无配额、免费全球。
和风 → 仅在用户显式提供有效 Web API Key 时启用（当前 SDK Key 会 403，不会覆盖主源）。
返回格式统一，前端不用改。
"""
import time
import requests
from datetime import datetime, timedelta

import config


# ========== 和风 QW 图标 → emoji ==========
_QW_ICON = {
    "100": "☀️","101": "⛅","102": "⛅","103": "⛅","104": "☁️",
    "300": "🌧️","301": "🌧️","302": "⛈️","303": "⛈️","304": "🌨️","305": "🌧️",
    "306": "🌧️","307": "🌧️","308": "🌧️","309": "🌧️","310": "🌧️","311": "🌧️",
    "312": "🌧️","313": "❄️","314": "🌧️","315": "🌧️","316": "🌧️","317": "🌧️",
    "318": "🌧️","399": "🌧️",
    "400": "❄️","401": "❄️","402": "❄️","403": "❄️","404": "🌨️","405": "🌨️",
    "406": "🌨️","407": "🌨️","408": "❄️","409": "❄️","410": "❄️","499": "❄️",
    "500": "🌫️","501": "🌫️","502": "🌫️","503": "🌪️","504": "🌪️","507": "🌪️",
    "508": "🌪️","509": "🌫️","510": "🌫️","511": "🌫️","512": "🌫️","513": "🌫️",
    "514": "🌫️","515": "🌫️","599": "🌫️",
    "900": "🌡️","901": "🌡️","999": "🌈",
}
# Open-Meteo WMO weather code → emoji + 中文
_OM_CODE = {
    # code: (icon, 中文)
    0:  ("☀️", "晴"),
    1:  ("🌤️", "晴间多云"), 2: ("⛅", "局部多云"), 3: ("☁️", "阴"),
    45: ("🌫️", "雾"), 48: ("🌫️", "雾凇"),
    51: ("🌦️", "小毛毛雨"), 53: ("🌦️", "毛毛雨"), 55: ("🌧️", "大毛毛雨"),
    56: ("🌨️", "冻毛毛雨"), 57: ("🌨️", "强冻毛毛雨"),
    61: ("🌧️", "小雨"), 63: ("🌧️", "中雨"), 65: ("🌧️", "大雨"),
    66: ("🌨️", "冻雨"), 67: ("🌨️", "强冻雨"),
    71: ("❄️", "小雪"), 73: ("❄️", "中雪"), 75: ("❄️", "大雪"),
    77: ("🌨️", "雪粒"),
    80: ("🌦️", "阵雨小"), 81: ("🌧️", "阵雨"), 82: ("⛈️", "强阵雨"),
    85: ("🌨️", "阵雪小"), 86: ("❄️", "阵雪大"),
    95: ("⛈️", "雷雨"), 96: ("⛈️", "雷雨带小冰雹"), 99: ("⛈️", "雷雨带大冰雹"),
}
def om_icon(code):
    return _OM_CODE.get(int(code), ("🌤️", "未知"))[0]
def om_text(code):
    return _OM_CODE.get(int(code), ("🌤️", "未知"))[1]
def qw_icon(c):
    return _QW_ICON.get(str(c), "🌤️")


# ========== 缓存 ==========
_CACHE: dict = {}
_CACHE_TTL = 1800  # 30 分钟

def _ck(city,lat,lon,days): return (str(city),round(float(lat) if lat else 0,4),round(float(lon) if lon else 0,4),int(days))
def _cg(k):
    if k in _CACHE:
        exp,v=_CACHE[k]
        if time.time()<exp: return v
        del _CACHE[k]
    return None
def _cs(k,v): _CACHE[k]=(time.time()+_CACHE_TTL,v)


# ========== Open-Meteo 主源 ==========
def _fetch_openmeteo(lat, lon, days):
    # 汉寿时区：Asia/Shanghai
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max"
        f"&forecast_days={days}"
        "&timezone=Asia%2FShanghai"
    )
    r = requests.get(url, timeout=15, headers={"User-Agent":"teach-assist/1.0"})
    if r.status_code != 200:
        raise RuntimeError(f"OpenMeteo HTTP {r.status_code}: {r.text[:200]}")
    j = r.json()
    cur = j.get("current", {})
    cur_code = cur.get("weather_code", 0)
    daily = j.get("daily", {})
    times = daily.get("time", [])
    daily_out = []
    for i in range(min(days, len(times))):
        daily_out.append({
            "date": times[i],
            "temp_max": daily.get("temperature_2m_max", [None])[i],
            "temp_min": daily.get("temperature_2m_min", [None])[i],
            "tempMax": daily.get("temperature_2m_max", [None])[i],
            "tempMin": daily.get("temperature_2m_min", [None])[i],
            "precip_prob": daily.get("precipitation_probability_max", [None])[i],
            "wind": daily.get("wind_speed_10m_max", [None])[i],
            "weather": om_text(daily.get("weather_code", [0])[i]),
            "text": om_text(daily.get("weather_code", [0])[i]),
            "icon": om_icon(daily.get("weather_code", [0])[i]),
        })
    current = {
        "temp": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "weather": om_text(cur_code),
        "icon": om_icon(cur_code),
        "wind": cur.get("wind_speed_10m"),
        "windSpeed": cur.get("wind_speed_10m"),
        "text": om_text(cur_code),
        "tempMax": daily_out[0]["tempMax"] if daily_out else None,
        "tempMin": daily_out[0]["tempMin"] if daily_out else None,
        "precipProb": daily_out[0]["precip_prob"] if daily_out else None,
    }
    return current, daily_out


# ========== 和风兜底（仅当提供有效 Web API Key 时） ==========
# Key 优先级：config（DB settings 表 / 环境变量） > 空字符串
# 注意：和风 SDK 凭据调 Web API 会 403，必须使用 Web API Key
def _get_hefeng_key() -> str:
    try:
        return config.get_env_or_db("HEFENG_API_KEY", "")
    except Exception:
        return ""

HANSHOU_CITY_ID = "101250907"
QW_HOSTS = ["devapi.qweather.com", "api.qweather.com", "geoapi.qweather.com"]

def _try_qweather(lat, lon, days):
    """如果未配置 Web API Key 或 key 无效会抛异常/403，立即回到主源 Open-Meteo。"""
    hefeng_key = _get_hefeng_key()
    if not hefeng_key:
        raise RuntimeError("未配置 HEFENG_API_KEY，跳过和风兜底")
    location = HANSHOU_CITY_ID
    try:
        f_lat, f_lon = float(lat), float(lon)
        if abs(f_lat - 28.914) > 0.5 or abs(f_lon - 111.976) > 0.5:
            location = f"{f_lon:.3f},{f_lat:.3f}"
    except Exception:
        pass
    last_err = None
    daily_api = "3d" if days <= 3 else "7d"
    for H in QW_HOSTS:
        try:
            rnow = requests.get(f"https://{H}/v7/weather/now?location={location}&key={hefeng_key}", timeout=8)
            r3d  = requests.get(f"https://{H}/v7/weather/{daily_api}?location={location}&key={hefeng_key}", timeout=8)
            jnow = rnow.json(); j3d = r3d.json()
            if str(jnow.get("code")) == "200" and str(j3d.get("code")) == "200":
                # 组装
                n = jnow["now"]
                cur = {
                    "temp": n.get("temp"), "humidity": n.get("humidity"),
                    "weather": n.get("text"), "icon": qw_icon(n.get("icon","999")),
                    "wind": n.get("windSpeed"), "windSpeed": n.get("windSpeed"), "text": n.get("text"),
                    "tempMax": j3d["daily"][0].get("tempMax") if j3d["daily"] else None,
                    "tempMin": j3d["daily"][0].get("tempMin") if j3d["daily"] else None,
                    "precipProb": None,
                }
                dout = []
                for i, d in enumerate(j3d["daily"][:days]):
                    dout.append({
                        "date": d.get("fxDate"),
                        "temp_max": d.get("tempMax"), "temp_min": d.get("tempMin"),
                        "tempMax": d.get("tempMax"), "tempMin": d.get("tempMin"),
                        "precip_prob": d.get("precip"), "wind": d.get("windSpeedDay"),
                        "weather": d.get("textDay"), "text": d.get("textDay"),
                        "icon": qw_icon(d.get("iconDay","999")),
                    })
                if dout:
                    cur["tempMax"] = dout[0]["tempMax"]
                    cur["tempMin"] = dout[0]["tempMin"]
                    cur["precipProb"] = dout[0]["precip_prob"]
                return cur, dout
            last_err = f"{H} code={jnow.get('code')}/{j3d.get('code')}"
        except Exception as e:
            last_err = f"{H} exc={e}"
    raise RuntimeError(last_err or "QWeather no usable host")


# ========== 对外入口 ==========
def get_weather(city=None, lat=None, lon=None, days=3):
    default_city, default_lat, default_lon = config.get_default_city()
    if not city: city = default_city
    if lat is None: lat = default_lat
    if lon is None: lon = default_lon
    days = max(1, min(int(days or 3), 7))

    k = _ck(city, lat, lon, days)
    v = _cg(k)
    if v is not None: return v

    errors = []
    # 主：Open-Meteo
    try:
        current, daily = _fetch_openmeteo(lat, lon, days)
        result = {
            "city": city, "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "source": "open-meteo", "current": current, "daily": daily,
        }
        _cs(k, result)
        return result
    except Exception as e:
        errors.append(f"OpenMeteo: {e}")

    # 兜底：和风
    try:
        current, daily = _try_qweather(lat, lon, days)
        result = {
            "city": city, "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "source": "qweather", "current": current, "daily": daily,
        }
        _cs(k, result)
        return result
    except Exception as e:
        errors.append(f"QWeather: {e}")

    # 全失败：返回占位
    result = {
        "city": city, "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "source": "offline",
        "current": {"temp": None, "humidity": None, "weather": "暂时无法获取", "icon": "⚠️",
                    "wind": None, "tempMax": None, "tempMin": None, "precipProb": None,
                    "error": " | ".join(errors)},
        "daily": [],
        "errors": errors,
    }
    _cs(k, result)
    return result
