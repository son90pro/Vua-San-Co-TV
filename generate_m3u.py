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
added_urls = set()


def add_matches_to_m3u(matches):
  count = 0
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
      m3u_lines.append(f"{stream_url}\n")
      count += 1
  return count


with sync_playwright() as p:
  browser = p.chromium.launch(
      headless=True,
      args=[
          "--no-sandbox",
          "--disable-setuid-sandbox",
          "--disable-blink-features=AutomationControlled",
          "--disable-dev-shm-usage",
      ],
  )

  context = browser.new_context(
      user_agent=(
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          " (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
      ),
      viewport={"width": 1280, "height": 720},
      locale="vi-VN",
      timezone_id="Asia/Ho_Chi_Minh",
  )

  page = context.new_page()

  # Giả lập thuộc tính trình duyệt thật
  page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
    """)

  # Bắt tự động response API khi trang web tự gọi
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
            added = add_matches_to_m3u(data)
            print(
                f"-> [Bắt tự động Network] Lấy được {len(data)} trận ({added}"
                " luồng mới)"
            )
      except Exception:
        pass

  page.on("response", handle_response)

  print("-> Đang tải trang chủ Vua Sân Cỏ TV...")
  try:
    page.goto(
        "https://www.livinginterior.in/",
        wait_until="domcontentloaded",
        timeout=45000,
    )
    time.sleep(5)
    print(f"-> Tiêu đề trang web: '{page.title()}'")
  except Exception as e:
    print(f"⚠️ Cảnh báo tải trang: {e}")

  # Kiểm tra nếu dính Cloudflare Challenge
  title = page.title()
  if any(
      kw in title
      for kw in ["Just a moment", "Cloudflare", "Attention Required"]
  ):
    print("⚠️ Trình duyệt đang ở màn hình xác thực Cloudflare, chờ 10s...")
    time.sleep(10)
    print(f"-> Tiêu đề sau khi chờ: '{page.title()}'")

  # JS script gọi fetch trực tiếp từ trong Browser
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
                const text = await res.text();
                try {
                    return { status: res.status, data: JSON.parse(text) };
                } catch (e) {
                    return { status: res.status, rawText: text.substring(0, 200) };
                }
            } catch (err) {
                return { status: 0, error: err.toString() };
            }
        }
    """

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
            added = add_matches_to_m3u(matches)
            print(
                f"-> Ngày {date_str} (isLive={is_live}, Trang"
                f" {page_num}/{total_pages}): Tìm thấy {len(matches)} trận"
                f" ({added} luồng mới)"
            )
          else:
            print(
                f"⚠️ API trả về code {res_json.get('code')} cho ngày {date_str}"
            )
            break
        else:
          err_msg = (
              res_obj.get("error")
              or res_obj.get("rawText")
              or f"HTTP status {status}"
          )
          print(
              f"⚠️ Không thể gọi API ngày {date_str} (isLive={is_live}, Trang"
              f" {page_num}): {err_msg}"
          )
          break

        page_num += 1

  browser.close()

# Ghi file vuasanco.m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines))

print(
    f"\n✅ Hoàn tất! Đã tạo thành công {len(added_urls)} luồng phát vào file"
    " vuasanco.m3u."
)
