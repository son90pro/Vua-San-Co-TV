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

m3u_lines = ["#EXTM3U\n"]
seen_urls = set()

with sync_playwright() as p:
  # Mở trình duyệt Chromium thật chạy qua WARP
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
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/128.0.0.0 Safari/537.36"
      ),
      viewport={"width": 1280, "height": 720},
      locale="vi-VN",
      timezone_id="Asia/Ho_Chi_Minh",
  )
  page = context.new_page()

  # Giả lập thuộc tính không phải Bot
  page.add_init_script(
      "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
  )

  print("-> Đang mở trang chủ Vua Sân Cỏ TV qua kết nối WARP...")
  try:
    page.goto(
        "https://www.livinginterior.in/",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    time.sleep(5)  # Chờ trình duyệt vượt qua Cloudflare Challenge
    print(f"-> Tiêu đề trang: '{page.title()}'")
  except Exception as e:
    print(f"⚠️ Cảnh báo tải trang: {e}")

  # Script fetch nội bộ trình duyệt (kế thừa đầy đủ Session/Cookie)
  fetch_js = """
        async (payload) => {
            try {
                const res = await window.fetch('/api/proxy/data/lives/matches', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json, text/plain, */*'
                    },
                    body: JSON.stringify(payload)
                });
                if (!res.ok) return { status: res.status };
                return { status: 200, data: await res.json() };
            } catch (err) {
                return { status: 0, error: err.toString() };
            }
        }
    """

  total_added = 0

  for date_str in [today_str, tomorrow_str]:
    for is_live in [True, False]:
      page_num = 1
      total_pages = 1

      while page_num <= total_pages:
        payload = {
            "date": date_str,
            "page": page_num,
            "pageSize": 18,
            "status": 1,
            "timezone": "Asia/Ho_Chi_Minh",
            "isLive": is_live,
        }

        res_obj = page.evaluate(fetch_js, payload)
        status = res_obj.get("status", 0)

        if status == 200 and "data" in res_obj:
          res_json = res_obj["data"]
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
                f"-> Ngày {date_str} (isLive={is_live}, Trang"
                f" {page_num}/{total_pages}): Lấy thành công {len(matches)} trận"
            )
          else:
            break
        else:
          print(f"⚠️ API status: {status}")
          break

        page_num += 1

  browser.close()

# Ghi file vuasanco.m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines))

print(f"\n✅ Hoàn tất! Đã tạo thành công {total_added} luồng phát.")
