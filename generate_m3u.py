from datetime import datetime, timedelta
import json
import time
from playwright.sync_api import sync_playwright
import pytz

# Múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

m3u_lines = ["#EXTM3U"]
added_urls = set()


def process_match_list(matches):
  """Hàm xử lý và thêm danh sách trận đấu vào m3u"""
  for match in matches:
    if not isinstance(match, dict):
      continue

    match_date = match.get("date", "")
    match_time = match.get("time", "")

    try:
      formatted_date = datetime.strptime(match_date, "%Y-%m-%d").strftime(
          "%d/%m"
      )
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
          live.get("link") or live.get("linkSecure") or live.get("streamUrl")
      )
      if not stream_url or stream_url in added_urls:
        continue

      added_urls.add(stream_url)
      commentator = (
          live.get("commentator") or live.get("commentatorSource") or "VSC"
      )
      is_live = live.get("isLive", False) or match.get("status") == 2
      live_icon = "🟢 " if is_live else ""

      title = (
          f"{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs"
          f" {away_team} ({commentator})"
      )

      m3u_lines.append(
          f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Vua Sân Cỏ TV" ,'
          f" {title}"
      )
      m3u_lines.append(stream_url)


with sync_playwright() as p:
  # Mở trình duyệt Chromium giả lập người dùng thật
  browser = p.chromium.launch(
      headless=True,
      args=[
          "--no-sandbox",
          "--disable-setuid-sandbox",
          "--disable-blink-features=AutomationControlled",
      ],
  )
  context = browser.new_context(
      user_agent=(
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
      ),
      viewport={"width": 1280, "height": 720},
  )
  page = context.new_page()

  # Lắng nghe và bắt tự động mọi response API mà trang web tự gọi
  def handle_response(response):
    if (
        "/api/proxy/data/lives/matches" in response.url
        and response.status == 200
    ):
      try:
        res_json = response.json()
        if res_json.get("code") == 1000:
          data = res_json.get("result", {}).get("data", [])
          if data:
            print(f"-> Bắt tự động từ trang web: {len(data)} trận")
            process_match_list(data)
      except Exception:
        pass

  page.on("response", handle_response)

  print("-> Đang mở trang chủ Vua Sân Cỏ TV...")
  try:
    page.goto(
        "https://www.livinginterior.in/",
        wait_until="networkidle",
        timeout=60000,
    )
    time.sleep(3)
  except Exception as e:
    print(f"⚠️ Cảnh báo tải trang: {e}")

  # Thử cả 2 dạng đường dẫn tương đối
  endpoints = [
      "/api/proxy/data/lives/matches",
      "/api/proxy/data/lives/matches/",
  ]

  fetch_js = """
        async ([url, payload]) => {
            try {
                const res = await window.fetch(url, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json, text/plain, */*'
                    },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) return { error: 'HTTP ' + res.status };
                return await res.json();
            } catch (e) {
                return { error: e.toString() };
            }
        }
    """

  for target_date in [today_str, tomorrow_str]:
    for is_live in [True, False]:
      page_num = 1
      total_pages = 1

      while page_num <= total_pages:
        payload = {
            "date": target_date,
            "page": page_num,
            "pageSize": 50,
            "timezone": "Asia/Ho_Chi_Minh",
            "status": 1,
            "isLive": is_live,
        }

        fetched_success = False
        for ep in endpoints:
          try:
            res_json = page.evaluate(fetch_js, [ep, payload])

            if res_json and res_json.get("code") == 1000:
              result = res_json.get("result", {})
              total_pages = result.get("totalPages", 1)
              matches = result.get("data") or []
              print(
                  f"-> Ngày {target_date} (trang {page_num}/{total_pages}):"
                  f" Lấy thành công {len(matches)} trận"
              )
              process_match_list(matches)
              fetched_success = True
              break
          except Exception as e:
            pass

        if not fetched_success:
          break
        page_num += 1

  browser.close()

# Ghi dữ liệu ra file m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines) + "\n")

print(
    f"Hoàn tất! Tổng cộng tạo được {len(added_urls)} luồng phát trong file"
    " vuasanco.m3u."
)
