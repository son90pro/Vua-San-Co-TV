from datetime import datetime, timedelta
import json
import pytz
from curl_cffi import requests

# API URL Bóng đá của Vua Sân Cỏ TV
API_URL = "https://www.livinginterior.in/api/proxy/data/lives/matches"

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    "content-type": "application/json",
    "origin": "https://www.livinginterior.in",
    "referer": "https://www.livinginterior.in/",
    "sec-ch-ua": (
        '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"'
    ),
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}

# Lấy múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

dates_to_fetch = [today_str, tomorrow_str]

m3u_lines = ["#EXTM3U\n"]
added_urls = set()

# Khởi tạo Session giả lập Chrome 120
session = requests.Session(impersonate="chrome120")

# Bước 1: Khởi tạo session qua trang chủ để nhận Cookie Cloudflare
print("-> Đang khởi tạo session qua trang chủ...")
try:
  init_res = session.get(
      "https://www.livinginterior.in/", headers=HEADERS, timeout=15
  )
  print(f"-> Kết nối trang chủ HTTP Status: {init_res.status_code}")
except Exception as e:
  print(f"⚠️ Cảnh báo khởi tạo: {e}")


def send_post(url, payload):
  """Gửi POST request và duy trì phương thức POST nếu gặp Redirect"""
  res = session.post(
      url, headers=HEADERS, json=payload, allow_redirects=False, timeout=15
  )
  if res.status_code in (301, 302, 307, 308):
    redirect_url = res.headers.get("Location", "")
    if redirect_url.startswith("/"):
      redirect_url = "https://www.livinginterior.in" + redirect_url
    print(
        f"-> Phát hiện Redirect {res.status_code}, gửi lại POST tới:"
        f" {redirect_url}"
    )
    res = session.post(
        redirect_url,
        headers=HEADERS,
        json=payload,
        allow_redirects=False,
        timeout=15,
    )
  return res


for date_str in dates_to_fetch:
  for is_hot in [True, False]:
    page = 1
    total_pages = 1

    while page <= total_pages:
      payload = {
          "date": date_str,
          "page": page,
          "pageSize": 50,
          "timezone": "Asia/Ho_Chi_Minh",
          "isHot": is_hot,
      }

      try:
        response = send_post(API_URL, payload)

        if response.status_code != 200:
          print(
              f"⚠️ API POST HTTP {response.status_code} cho ngày {date_str}"
              f" (isHot={is_hot}, page={page})"
          )
          break

        res_json = response.json()
        if res_json.get("code") == 1000:
          result = res_json.get("result", {})
          total_pages = result.get("totalPages", 1)
          matches = result.get("data") or []

          print(
              f"-> Ngày {date_str} (isHot={is_hot}, trang {page}/{total_pages}):"
              f" Tìm thấy {len(matches)} trận"
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

              title = (
                  f"{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs"
                  f" {away_team} ({commentator})"
              )

              m3u_lines.append(
                  f'#EXTINF:-1 tvg-logo="{home_logo}"'
                  f' group-title="Vua Sân Cỏ TV" , {title}'
              )
              m3u_lines.append(f"{stream_url}\n")
        else:
          print(f"⚠️ API code {res_json.get('code')} cho ngày {date_str}")
          break

      except Exception as e:
        print(f"❌ Lỗi xử lý ngày {date_str}: {e}")
        break

      page += 1

# Ghi file vuasanco.m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines))

print(
    f"\n✅ Hoàn tất! Tạo được {len(added_urls)} luồng phát trong file"
    " vuasanco.m3u."
)
