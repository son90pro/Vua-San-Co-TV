from datetime import datetime, timedelta
import json
from curl_cffi import requests
import pytz

# Cấu hình API Vua Sân Cỏ TV
API_URL = "https://www.livinginterior.in/api/proxy/data/lives/matches"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://www.livinginterior.in",
    "Referer": "https://www.livinginterior.in/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Lấy múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

dates_to_fetch = [today_str, tomorrow_str]

m3u_lines = ["#EXTM3U"]
added_urls = set()

for target_date in dates_to_fetch:
  for is_hot in [True, False]:
    page = 1
    total_pages = 1

    while page <= total_pages:
      payload = {
          "date": target_date,
          "page": page,
          "pageSize": 50,
          "timezone": "Asia/Ho_Chi_Minh",
          "isHot": is_hot,
      }

      try:
        # Sử dụng impersonate="chrome120" để vượt Cloudflare
        response = requests.post(
            API_URL,
            headers=HEADERS,
            json=payload,
            impersonate="chrome120",
            timeout=15,
        )

        if response.status_code != 200:
          print(
              f"⚠️ API trả về lỗi HTTP {response.status_code} cho ngày"
              f" {target_date} (isHot={is_hot})"
          )
          break

        res_json = response.json()
        if res_json.get("code") == 1000:
          result = res_json.get("result", {})
          total_pages = result.get("totalPages", 1)
          matches = result.get("data") or []

          print(
              f"-> Ngày {target_date} (isHot={is_hot}, trang {page}/{total_pages}):"
              f" tìm thấy {len(matches)} trận"
          )

          for match in matches:
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
              is_live = live.get("isLive", False) or match.get("status") == 2
              live_icon = "🟢 " if is_live else ""

              title = f"{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs {away_team} ({commentator})"

              m3u_lines.append(
                  f'#EXTINF:-1 tvg-logo="{home_logo}"'
                  f' group-title="Vua Sân Cỏ TV" , {title}'
              )
              m3u_lines.append(stream_url)
        else:
          print(f"⚠️ API trả về code: {res_json.get('code')}")
      except Exception as e:
        print(f"❌ Lỗi kết nối API ngày {target_date}: {e}")
        break

      page += 1

# Ghi dữ liệu ra file m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines) + "\n")

print(
    f"Hoàn tất! Tổng cộng tạo được {len(added_urls)} luồng phát trong file"
    " vuasanco.m3u."
)
