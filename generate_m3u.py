from datetime import datetime, timedelta
import json
import pytz
from curl_cffi import requests

# URL chuẩn KHÔNG CÓ www (tránh bị Nginx 301 redirect đổi POST thành GET)
API_URL = "https://livinginterior.in/api/proxy/data/lives/matches"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://livinginterior.in",
    "referer": "https://livinginterior.in/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}

tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

m3u_lines = ["#EXTM3U\n"]
seen_urls = set()

session = requests.Session(impersonate="chrome120")

# Khởi tạo session với trang chủ
try:
  session.get("https://livinginterior.in/", headers=HEADERS, timeout=10)
except Exception:
  pass

total_added = 0

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

      try:
        res = session.post(
            API_URL, headers=HEADERS, json=payload, timeout=15
        )

        if res.status_code == 200:
          res_json = res.json()
          if res_json.get("code") == 1000:
            result = res_json.get("result", {})
            total_pages = result.get("totalPages", 1)
            matches = result.get("data") or []

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
                if not stream_url or stream_url in seen_urls:
                  continue

                seen_urls.add(stream_url)

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
                    f"{live_icon}{match_time} {formatted_date} ⚽ {home_team}"
                    f" vs {away_team} ({commentator})"
                )
                extinf = (
                    f'#EXTINF:-1 tvg-logo="{home_logo}"'
                    f' group-title="Vua Sân Cỏ TV" , {title}'
                )

                m3u_lines.append(extinf)
                m3u_lines.append(f"{stream_url}\n")
                total_added += 1

            print(
                f"-> Ngày {date_str} (isLive={is_live}, Page"
                f" {page}/{total_pages}): Lấy thành công {len(matches)} trận"
            )
          else:
            break
        else:
          print(f"⚠️ API trả về status: {res.status_code}")
          break

      except Exception as e:
        print(f"❌ Lỗi kết nối: {e}")
        break

      page += 1

with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines))

print(f"\n✅ Hoàn tất! Đã tạo thành công {total_added} luồng phát.")
