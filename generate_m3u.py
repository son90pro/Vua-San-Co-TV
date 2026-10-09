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

dates_to_fetch = [today_str, tomorrow_str]

m3u_lines = ["#EXTM3U"]
added_urls = set()

with sync_playwright() as p:
  # Khởi tạo Chromium với tham số ẩn danh tránh bị Cloudflare bắt Headless
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

  # Giả lập thuộc tính của trình duyệt người dùng thật
  page.add_init_script(
      "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
  )

  print("-> Đang mở trang chủ Vua Sân Cỏ TV...")
  try:
    page.goto(
        "https://www.livinginterior.in/",
        wait_until="networkidle",
        timeout=45000,
    )
    time.sleep(3)  # Chờ 3 giây để Cloudflare cấp Cookie cf_clearance
  except Exception as e:
    print(f"⚠️ Tải trang chủ có cảnh báo: {e}")

  # Script fetch chạy trực tiếp bên trong Browser Context (đã vượt Cloudflare)
  fetch_js = """
        async (payload) => {
            try {
                const response = await fetch('https://www.livinginterior.in/api/proxy/data/lives/matches', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json, text/plain, */*',
                        'Origin': 'https://www.livinginterior.in',
                        'Referer': 'https://www.livinginterior.in/'
                    },
                    body: JSON.stringify(payload),
                    redirect: 'manual'
                });
                
                if (response.type === 'opaqueredirect' || response.status === 301 || response.status === 302) {
                    return { error: 'REDIRECTED' };
                }
                if (!response.ok) return { error: 'HTTP ' + response.status };
                return await response.json();
            } catch (err) {
                return { error: err.toString() };
            }
        }
    """

  for target_date in dates_to_fetch:
    # Các cấu hình Payload dựa trên trace mạng thực tế
    payload_configs = [
        {
            "date": target_date,
            "pageSize": 50,
            "timezone": "Asia/Ho_Chi_Minh",
            "status": 1,
            "isLive": True,
        },
        {
            "date": target_date,
            "pageSize": 50,
            "timezone": "Asia/Ho_Chi_Minh",
            "status": 1,
        },
        {
            "date": target_date,
            "pageSize": 50,
            "timezone": "Asia/Ho_Chi_Minh",
            "isHot": True,
        },
        {"date": target_date, "pageSize": 50, "timezone": "Asia/Ho_Chi_Minh"},
    ]

    for base_payload in payload_configs:
      page_num = 1
      total_pages = 1

      while page_num <= total_pages:
        payload = {**base_payload, "page": page_num}

        try:
          res_json = page.evaluate(fetch_js, payload)

          # Nếu phát hiện bị Cloudflare Redirect, reload lại trang để lấy Cookie mới
          if res_json and res_json.get("error") in ["REDIRECTED", "HTTP 405"]:
            print(
                f"⚠️ Phát hiện redirect ({res_json.get('error')}), đang làm mới"
                " session..."
            )
            page.goto(
                "https://www.livinginterior.in/",
                wait_until="networkidle",
                timeout=30000,
            )
            time.sleep(3)
            res_json = page.evaluate(fetch_js, payload)

          if res_json and res_json.get("code") == 1000:
            result = res_json.get("result", {})
            total_pages = result.get("totalPages", 1)
            matches = result.get("data") or []

            print(
                f"-> Ngày {target_date} (Trang {page_num}/{total_pages}): Tìm"
                f" thấy {len(matches)} trận"
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

                title = (
                    f"{live_icon}{match_time} {formatted_date} ⚽"
                    f" {home_team} vs {away_team} ({commentator})"
                )

                m3u_lines.append(
                    f'#EXTINF:-1 tvg-logo="{home_logo}"'
                    f' group-title="Vua Sân Cỏ TV" , {title}'
                )
                m3u_lines.append(stream_url)

          else:
            err_detail = res_json.get("error") if res_json else "Không có dữ liệu"
            print(f"⚠️ Thông báo API ngày {target_date}: {err_detail}")
            break

        except Exception as e:
          print(f"❌ Lỗi xử lý ngày {target_date}: {e}")
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
