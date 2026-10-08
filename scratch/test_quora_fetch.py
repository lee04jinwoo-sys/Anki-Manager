import urllib.request
import xml.etree.ElementTree as ET
import re
import html

def clean_html(text):
    if not text:
        return ""
    # Unescape HTML entities
    text = html.unescape(text)
    # Remove HTML tags
    clean = re.compile('<.*?>')
    cleaned = re.sub(clean, '', text)
    # Normalize spacing
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def fetch_medium_rss(tag="self-improvement"):
    url = f"https://medium.com/feed/tag/{tag}"
    print(f"📡 Medium RSS 요청 중 (Tag: {tag}, URL: {url})...")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            xml_data = response.read()
            
        print("✅ 성공적으로 데이터를 수신했습니다. XML 파싱 중...")
        
        # Parse XML
        root = ET.fromstring(xml_data)
        
        # Find all <item> tags
        items = root.findall(".//item")
        print(f"📊 발견된 에세이 포스트 개수: {len(items)}개\n")
        
        # Display top 3 entries for verification
        for idx, item in enumerate(items[:3]):
            title = item.find("title").text if item.find("title") is not None else "제목 없음"
            
            # Medium uses content:encoded for body, but we can look at description or content:encoded namespaces
            # Find description first as it holds summary
            description_raw = item.find("description").text if item.find("description") is not None else ""
            if not description_raw:
                # Fallback to look at namespaces or other children
                description_raw = ""
                
            link = item.find("link").text if item.find("link") is not None else ""
            
            cleaned_desc = clean_html(description_raw)
            preview_text = cleaned_desc[:400] + "..." if len(cleaned_desc) > 400 else cleaned_desc
            
            print(f"🔥 [{idx + 1}] 에세이 제목: {title}")
            print(f"🔗 링크: {link}")
            print(f"✍️ 요약 내용:")
            print(f"   \"{preview_text}\"")
            print("-" * 80)
            
    except Exception as e:
        print(f"❌ Medium 데이터 가져오기 실패: {e}")

if __name__ == "__main__":
    fetch_medium_rss("self-improvement")
