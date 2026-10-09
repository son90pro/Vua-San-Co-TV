from datetime import datetime, timedelta
import json
import pytz
from curl_cffi import requests

# API URL Bóng đá của Vua Sân Cỏ TV
API_URL = "https://www.livinginterior.in/api/proxy/data/lives/matches"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.livinginterior.in/",
}

# Lấy múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

m3u_lines = ["#EXTM3U\n"]
added_urls = set()

# Khởi tạo Session giả lập TLS Chrome
session = requests.Session(impersonate="chrome120")

for date_str in [today_str, tomorrow_str]:
  page = 1
  total_pages = 1

  while page <= total_pages:
    # Truyền tham số dưới dạng Query String cho GET request
    params = {
        "date": date_str,
        "page": page,
        "pageSize": 50,
        "timezone": "Asia/Ho_Chi_Minh",
    }

    try:
      response = session.get(
          API_URL, headers=HEADERS, params=params, timeout=15
      )

      if response.status_code != 200:
        print(f"⚠️ API GET HTTP {response.status_code} cho ngày {date_str}")
        break

      res_json = response.json()
      if res_json.get("code") == 1000:
        result = res_json.get("result", {})
        total_pages = result.get("totalPages", 1)
        matches = result.get("data") or []

        print(
            f"-> Ngày {date_str} (Trang {page}/{total_pages}): Tìm thấy"
            f" {len(matches)} trận"
        )

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

            # Ưu tiên lấy link stream
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

            # Icon 🟢 cho trận đang phát trực tiếp
            is_live = live.get("isLive", False) or match.get("status") == 2
            live_icon = "🟢 " if is_live else ""

            # Hiển thị đúng định dạng hình mẫu
            title = (
                f"{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs"
                f" {away_team} ({commentator})"
            )

            m3u_lines.append(
                f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Vua Sân Cỏ TV"'
                f" , {title}"
            )
            m3u_lines.append(f"{stream_url}\n")
      else:
        print(f"⚠️ API trả về code {res_json.get('code')} cho ngày {date_str}")
        break

    except Exception as e:
      print(f"❌ Lỗi khi lấy dữ liệu ngày {date_str}: {e}")
      break

    page += 1

# Ghi file vuasanco.m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines))

print(
    f"\n✅ Hoàn tất! Đã tạo thành công {len(added_urls)} luồng phát trong file"
    " vuasanco.m3u."
)
