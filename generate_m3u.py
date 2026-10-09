from datetime import datetime, timedelta
import json
import pytz
from curl_cffi import requests

# API Endpoint
API_URL = "https://www.livinginterior.in/api/proxy/data/lives/matches"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://www.livinginterior.in",
    "referer": "https://www.livinginterior.in/",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
}

# Lấy ngày hôm nay và ngày mai theo múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

m3u_lines = ["#EXTM3U\n"]
seen_urls = set()

# Khởi tạo Session giả lập Chrome 120
session = requests.Session(impersonate="chrome120")

# Khởi tạo session qua trang chủ
try:
  session.get("https://www.livinginterior.in/", headers=HEADERS, timeout=10)
except Exception:
  pass

for date_str in [today_str, tomorrow_str]:
  # Quét qua các bộ lọc status/isHot để không bỏ sót trận nào
  for status_val in [1, 2, None]:
    page = 1
    total_pages = 1

    while page <= total_pages:
      payload = {
          "date": date_str,
          "page": page,
          "pageSize": 50,
          "timezone": "Asia/Ho_Chi_Minh",
      }
      if status_val is not None:
        payload["status"] = status_val

      try:
        res = session.post(
            API_URL,
            headers=HEADERS,
            json=payload,
            timeout=15,
            allow_redirects=False,
        )

        if res.status_code != 200:
          break

        res_json = res.json()
        if res_json.get("code") == 1000:
          result = res_json.get("result", {})
          total_pages = result.get("totalPages", 1)
          matches = result.get("data") or []

          for match in matches:
            if not isinstance(match, dict):
              continue

            match_date = match.get("date", "")  # YYYY-MM-DD
            match_time = match.get("time", "")  # HH:MM

            # Định dạng lại ngày sang DD/MM (VD: 09/10)
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

              # Ưu tiên lấy link sạch (không chứa token) giống file mẫu
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

              # Kiểm tra trạng thái đang đá
              is_live = live.get("isLive", False) or match.get("status") == 2
              live_icon = "🟢 " if is_live else ""

              # Tạo tiêu đề kênh CHUẨN XÁC theo mẫu anh cung cấp
              title = (
                  f"{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs"
                  f" {away_team} ({commentator})"
              )

              # Format thẻ EXTINF khớp chuẩn từng khoảng trắng
              extinf = (
                  f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Vua Sân Cỏ'
                  f' TV" , {title}'
              )

              m3u_lines.append(extinf)
              m3u_lines.append(f"{stream_url}\n")
        else:
          break

      except Exception as e:
        print(f"Lỗi kết nối ngày {date_str}: {e}")
        break

      page += 1

# Ghi danh sách ra file vuasanco.m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines))

print(
    f"✅ Hoàn tất! Đã xuất {len(seen_urls)} luồng phát chuẩn định dạng vào file"
    " vuasanco.m3u."
)
