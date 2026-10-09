from datetime import datetime, timedelta
import json
import time
from playwright.sync_api import sync_playwright
import pytz

# Múi giờ Việt Nam
tz = pytz.timezone('Asia/Ho_Chi_Minh')
now = datetime.now(tz)
today_str = now.strftime('%Y-%m-%d')
tomorrow_str = (now + timedelta(days=1)).strftime('%Y-%m-%d')

m3u_lines = ['#EXTM3U\n']
added_urls = set()


def add_matches_to_m3u(matches):
  count = 0
  for match in matches:
    if not isinstance(match, dict):
      continue

    match_date = match.get('date', '')
    match_time = match.get('time', '')

    try:
      formatted_date = datetime.strptime(match_date, '%Y-%m-%d').strftime(
          '%d/%m'
      )
    except Exception:
      formatted_date = match_date

    home_team = match.get('home', {}).get('name', 'Unknown')
    away_team = match.get('away', {}).get('name', 'Unknown')
    home_logo = match.get('home', {}).get('logo', '')

    lives = match.get('lives') or []

    for live in lives:
      if not isinstance(live, dict):
        continue

      stream_url = (
          live.get('link') or live.get('linkSecure') or live.get('streamUrl')
      )
      if not stream_url or stream_url in added_urls:
        continue

      added_urls.add(stream_url)
      commentator = (
          live.get('commentator') or live.get('commentatorSource') or 'VSC'
      )
      is_live = live.get('isLive', False) or match.get('status') == 2
      live_icon = '🟢 ' if is_live else ''

      # Định dạng chuẩn theo mẫu
      title = (
          f'{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs'
          f' {away_team} ({commentator})'
      )

      m3u_lines.append(
          f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Vua Sân Cỏ TV" ,'
          f' {title}'
      )
      m3u_lines.append(f'{stream_url}\n')
      count += 1
  return count


with sync_playwright() as p:
  # Cấu hình Chromium giả lập người dùng thật vượt Cloudflare
  browser = p.chromium.launch(
      headless=True,
      args=[
          '--no-sandbox',
          '--disable-setuid-sandbox',
          '--disable-blink-features=AutomationControlled',
          '--disable-infobars',
          '--window-size=1280,720',
      ],
  )

  context = browser.new_context(
      user_agent=(
          'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
          ' (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
      ),
      viewport={'width': 1280, 'height': 720},
      locale='vi-VN',
      timezone_id='Asia/Ho_Chi_Minh',
  )

  page = context.new_page()

  # Antidetection: Ẩn cờ Automation / Webdriver
  page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        window.chrome = { runtime: {} };
    """)

  # Lắng nghe và bắt tự động các request API do web tự phát
  def handle_response(response):
    if (
        '/api/proxy/data/lives/matches' in response.url
        and response.status == 200
    ):
      try:
        res_json = response.json()
        if res_json.get('code') == 1000:
          data = res_json.get('result', {}).get('data', [])
          if data:
            added = add_matches_to_m3u(data)
            print(
                f'-> [Auto-Intercept] Bắt tự động {len(data)} trận ({added}'
                ' luồng mới)'
            )
      except Exception:
        pass

  page.on('response', handle_response)

  print('-> Đang tải trang chủ Vua Sân Cỏ TV...')
  try:
    page.goto(
        'https://www.livinginterior.in/',
        wait_until='domcontentloaded',
        timeout=45000,
    )
    time.sleep(5)  # Chờ Cloudflare xác thực xong
  except Exception as e:
    print(f'⚠️ Tải trang có thông báo: {e}')

  # Gọi fetch nội bộ trình duyệt
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

  for date_str in [today_str, tomorrow_str]:
    payloads = [
        {
            'date': date_str,
            'page': 1,
            'pageSize': 50,
            'status': 1,
            'timezone': 'Asia/Ho_Chi_Minh',
            'isLive': True,
        },
        {
            'date': date_str,
            'page': 1,
            'pageSize': 50,
            'status': 1,
            'timezone': 'Asia/Ho_Chi_Minh',
            'isLive': False,
        },
        {
            'date': date_str,
            'page': 1,
            'pageSize': 50,
            'timezone': 'Asia/Ho_Chi_Minh',
            'isHot': True,
        },
        {
            'date': date_str,
            'page': 1,
            'pageSize': 50,
            'timezone': 'Asia/Ho_Chi_Minh',
            'isHot': False,
        },
    ]

    for p_data in payloads:
      page_num = 1
      total_pages = 1

      while page_num <= total_pages:
        current_payload = {**p_data, 'page': page_num}
        res_obj = page.evaluate(fetch_js, current_payload)

        if res_obj and res_obj.get('status') == 200:
          res_json = res_obj.get('data', {})
          if res_json.get('code') == 1000:
            result = res_json.get('result', {})
            total_pages = result.get('totalPages', 1)
            matches = result.get('data') or []
            added = add_matches_to_m3u(matches)
            print(
                f'-> Ngày {date_str} (Trang {page_num}/{total_pages}): Lấy'
                f' thành công {len(matches)} trận ({added} luồng mới)'
            )
          else:
            break
        else:
          break

        page_num += 1

  browser.close()

# Ghi file vuasanco.m3u
with open('vuasanco.m3u', 'w', encoding='utf-8') as f:
  f.write('\n'.join(m3u_lines))

print(
    f'\n✅ Hoàn tất! Đã tạo thành công {len(added_urls)} luồng phát vào file'
    ' vuasanco.m3u.'
)
