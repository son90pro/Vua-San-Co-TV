from datetime import datetime, timedelta
import json
import time
import pytz
from curl_cffi import requests

# API URL
API_URL = "https://www.livinginterior.in/api/proxy/data/lives/matches"

# Giả lập IP Việt Nam (Quảng Trị / TP.HCM) và Header Chrome thật
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://www.livinginterior.in",
    "referer": "https://www.livinginterior.in/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "x-forwarded-for": "113.160.225.18",
    "x-real-ip": "113.160.225.18",
    "cf-connecting-ip": "113.160.225.18",
}

# Lấy múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

m3u_lines = ["#EXTM3U\n"]
added_urls = set()

# Danh sách Proxy dự phòng (Châu Á / Việt Nam)
PROXIES = [
    None,  # Thử kết nối trực tiếp trước với Header Fake IP
    "http://103.152.118.38:80",
    "http://103.179.189.106:8080",
    "http://117.2.193.18:8080",
    "http://103.9.159.214:8080",
]


def fetch_api_data(session, payload):
  """Gửi POST request qua các Proxy cho đến khi thành công"""
  for proxy in PROXIES:
    try:
      kwargs = {
          "headers": HEADERS,
          "json": payload,
          "timeout": 10,
          "allow_redirects": False,
      }
      if proxy:
        kwargs["proxies"] = {"http": proxy, "https": proxy}

      res = session.post(API_URL, **kwargs)

      # Nếu dính redirect Nginx, thử gọi lại đường dẫn có dấu gạch chéo cuối
      if res.status_code in (301, 302, 307, 308, 405):
        alt_url = "https://www.livinginterior.in/api/proxy/data/lives/matches/"
        res = session.post(alt_url, **kwargs)

      if res.status_code == 200:
        return res.json()
    except Exception:
      continue
  return None


session = requests.Session(impersonate="chrome120")

for date_str in [today_str, tomorrow_str]:
  for is_live in [True, False]:
    page = 1
    total_pages = 1

    while page <= total_pages:
      payload = {
          "date": date_str,
          "page": page,
          "pageSize": 18,
          "status": 1,
          "timezone": "Asia/Ho_Chi_Minh",
          "isLive": is_live,
      }

      res_json = fetch_api_data(session, payload)

      if res_json and res_json.get("code") == 1000:
        result = res_json.get("result", {})
        total_pages = result.get("totalPages", 1)
        matches = result.get("data") or []

        count = 0
        for match in matches:
          if not isinstance(match, dict):
            continue

          match_date = match.get("date", "")
          match_time = match.get("time", "")

          try:
            formatted_date = datetime.strptime(
                match_date, "%Y-%m-%d"
            ).strftime("%d/%m")
          except Exception:
            formatted_date = match_date

          home_team = match.get("home", {}).get("name", "Unknown")
          away_team = match.get("away", {}).get("name", "Unknown")
          home_logo = match.get("home", {}).get("logo", "")

          lives = match.get("lives") or []

          for live in lives:
            if not isinstance(live, dict):
              continue

            stream_url = (
                live.get("link")
                or live.get("linkSecure")
                or live.get("streamUrl")
            )
            if not stream_url or stream_url in added_urls:
              continue

            added_urls.add(stream_url)
            commentator = (
                live.get("commentator")
                or live.get("commentatorSource")
                or "VSC"
            )
            is_match_live = (
                live.get("isLive", False) or match.get("status") == 2
            )
            live_icon = "🟢 " if is_match_live else ""

            title = (
                f"{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs"
                f" {away_team} ({commentator})"
            )

            m3u_lines.append(
                f'#EXTINF:-1 tvg-logo="{home_logo}"'
                f' group-title="Vua Sân Cỏ TV" , {title}'
            )
            m3u_lines.append(f"{stream_url}\n")
            count += 1

        print(
            f"-> Ngày {date_str} (isLive={is_live}, Trang {page}/{total_pages}):"
            f" Lấy được {len(matches)} trận ({count} luồng mới)"
        )
      else:
        print(
            f"⚠️ Không lấy được dữ liệu ngày {date_str} (isLive={is_live}, Trang"
            f" {page})"
        )
        break

      page += 1

# Ghi file vuasanco.m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines))

print(
    f"\n✅ Hoàn tất! Đã tạo thành công {len(added_urls)} luồng phát vào file"
    " vuasanco.m3u."
)
