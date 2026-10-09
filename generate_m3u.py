import requests
import json
from datetime import datetime, timedelta
import pytz

# Cấu hình API
API_URL = "https://www.livinginterior.in/api/proxy/data/lives/matches"
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Android 16; Mobile; rv:156.0) Gecko/156.0 Firefox/156.0",
    "Referer": "https://www.livinginterior.in/"
}

# Lấy múi giờ Việt Nam
tz = pytz.timezone("Asia/Ho_Chi_Minh")
now = datetime.now(tz)
today_str = now.strftime("%Y-%m-%d")
tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")

dates_to_fetch = [today_str, tomorrow_str]

m3u_lines = ["#EXTM3U\n"]

for target_date in dates_to_fetch:
    page = 1
    total_pages = 1
    
    while page <= total_pages:
        payload = {
            "date": target_date,
            "page": page,
            "pageSize": 50,  # Lấy tối đa 50 trận/trang
            "timezone": "Asia/Ho_Chi_Minh",
            "isHot": False  # Lấy toàn bộ trận đấu (cả Hot và thường)
        }
        
        try:
            response = requests.post(API_URL, headers=HEADERS, json=payload, timeout=15)
            if response.status_code == 200:
                res_json = response.json()
                if res_json.get("code") == 1000:
                    result = res_json.get("result", {})
                    total_pages = result.get("totalPages", 1)
                    matches = result.get("data", [])
                    
                    for match in matches:
                        # Thông tin cơ bản của trận đấu
                        match_date = match.get("date", "")  # YYYY-MM-DD
                        match_time = match.get("time", "")  # HH:MM
                        
                        # Chuyển đổi YYYY-MM-DD thành DD/MM
                        try:
                            formatted_date = datetime.strptime(match_date, "%Y-%m-%d").strftime("%d/%m")
                        except:
                            formatted_date = match_date

                        home_team = match.get("home", {}).get("name", "Unknown")
                        away_team = match.get("away", {}).get("name", "Unknown")
                        home_logo = match.get("home", {}).get("logo", "")
                        
                        lives = match.get("lives") or []
                        
                        for live in lives:
                            # Lấy link phát trực tiếp
                            stream_url = live.get("link") or live.get("linkSecure")
                            if not stream_url:
                                continue  # Bỏ qua nếu không có luồng m3u8
                            
                            commentator = live.get("commentator") or live.get("commentatorSource") or "VSC"
                            is_live = live.get("isLive", False) or match.get("status") == 2
                            
                            # Icon trạng thái phát sóng
                            live_icon = "🟢 " if is_live else ""
                            
                            # Tiêu đề hiển thị theo mẫu
                            title = f"{live_icon}{match_time} {formatted_date} ⚽ {home_team} vs {away_team} ({commentator})"
                            
                            # Thêm thẻ EXTFRAME M3U
                            m3u_lines.append(f'#EXTINF:-1 tvg-logo="{home_logo}" group-title="Vua Sân Cỏ TV" , {title}')
                            m3u_lines.append(f'{stream_url}\n')
            page += 1
        except Exception as e:
            print(f"Lỗi khi lấy dữ liệu ngày {target_date}: {e}")
            break

# Ghi nội dung ra file m3u
with open("vuasanco.m3u", "w", encoding="utf-8") as f:
    f.write("\n".join(m3u_lines))

print("Tạo file vuasanco.m3u thành công!")

