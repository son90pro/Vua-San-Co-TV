import json
from datetime import datetime, timedelta
import pytz
import requests

# Cấu hình API Vua Sân Cỏ TV
API_URL = "https://www.livinginterior.in/api/proxy/data/lives/matches"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0"
    ),
    "Referer": "https://www.livinginterior.in/",
}

# Lấy múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

dates_to_fetch = [today_str, tomorrow_str]

m3u_lines = ["#EXTM3U"]
added_urls = set()  # Dùng để lọc các link trùng lặp

for target_date in dates_to_fetch:
  # Lấy cả trận Hot và trận thường để không bỏ sót trận nào
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
        response = requests.post(
            API_URL, headers=HEADERS, json=payload, timeout=15
        )
        if response.status_code == 200:
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
              match_date = match.get("date", "")  # YYYY-MM-DD
              match_time = match.get("time", "")  # HH:MM

              # Định dạng DD/MM
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
                # Ưu tiên lấy link luồng m3u8
                stream_url = (
                    live.get("link")
                    or live.get("linkSecure")
                    or live.get("streamUrl")
                )
                if not stream_url:
                  continue

                # Bỏ qua nếu luồng này đã thêm rồi
                if stream_url in added_urls:
                  continue
                added_urls.add(stream_url)

                commentator = (
                    live.get("commentator")
                    or live.get("commentatorSource")
                    or "VSC"
                )

                # Icon live nếu trận đang đá (isLive=True hoặc status=2)
                is_live = live.get("isLive", False) or match.get("status") == 2
                live_icon = "🟢 " if is_live else ""

                # Định dạng tên hiển thị chuẩn mẫu
                title = f"{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs {away_team} ({commentator})"

                # Thêm vào m3u
                m3u_lines.append(
                    f'#EXTINF:-1 tvg-logo="{home_logo}"'
                    f' group-title="Vua Sân Cỏ TV" , {title}'
                )
                m3u_lines.append(stream_url)
        page += 1
      except Exception as e:
        print(f"Lỗi khi gọi API {target_date}: {e}")
        break

# Ghi file vuasanco.m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines) + "\n")

print(
    f"Hoàn tất! Tổng cộng tạo được {len(added_urls)} luồng phát trong file"
    " vuasanco.m3u."
)
