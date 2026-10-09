from datetime import datetime, timedelta
import json
from playwright.sync_api import sync_playwright
import pytz

# Lấy múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

dates_to_fetch = [today_str, tomorrow_str]

m3u_lines = ["#EXTM3U"]
added_urls = set()

with sync_playwright() as p:
  # Mở trình duyệt Chromium ngầm
  browser = p.chromium.launch(headless=True)
  context = browser.new_context(
      user_agent=(
          "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
          " like Gecko) Chrome/120.0.0.0 Safari/537.36"
      )
  )
  page = context.new_page()

  print("-> Đang truy cập Vua Sân Cỏ TV...")
  try:
    page.goto(
        "https://www.livinginterior.in/",
        wait_until="domcontentloaded",
        timeout=30000,
    )
    page.wait_for_timeout(3000)  # Chờ 3 giây để vượt Cloudflare
  except Exception as e:
    print(f"⚠️ Tải trang chủ có cảnh báo: {e}")

  for target_date in dates_to_fetch:
    for is_hot in [True, False]:
      page_num = 1
      total_pages = 1

      while page_num <= total_pages:
        payload = {
            "date": target_date,
            "page": page_num,
            "pageSize": 50,
            "timezone": "Asia/Ho_Chi_Minh",
            "isHot": is_hot,
        }

        try:
          # Gọi fetch() trực tiếp từ trong Browser
          res_json = page.evaluate(
              """
                        async (payload) => {
                            try {
                                const res = await fetch('/api/proxy/data/lives/matches', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                        'Accept': 'application/json, text/plain, */*'
                                    },
                                    body: JSON.stringify(payload)
                                });
                                if (!res.ok) return { error: `HTTP ${res.status}` };
                                return await res.json();
                            } catch (e) {
                                return { error: e.toString() };
                            }
                        }
                    """,
              payload,
          )

          if not res_json or "error" in res_json:
            err_msg = res_json.get("error") if res_json else "No response"
            print(
                f"⚠️ Lỗi API ngày {target_date} (isHot={is_hot},"
                f" page={page_num}): {err_msg}"
            )
            break

          if res_json.get("code") == 1000:
            result = res_json.get("result", {})
            total_pages = result.get("totalPages", 1)
            matches = result.get("data") or []

            print(
                f"-> Ngày {target_date} (isHot={is_hot}, trang"
                f" {page_num}/{total_pages}): tìm thấy {len(matches)} trận"
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
          print(f"❌ Lỗi xử lý ngày {target_date}: {e}")
          break

        page_num += 1

  browser.close()

# Ghi file vuasanco.m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
  f.write("\n".join(m3u_lines) + "\n")

print(
    f"Hoàn tất! Tổng cộng tạo được {len(added_urls)} luồng phát trong file"
    " vuasanco.m3u."
)
