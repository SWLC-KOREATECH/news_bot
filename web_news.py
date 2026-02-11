# web_news.py
import requests
import pandas as pd
import os
import smtplib
import time
import re
import json
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import trafilatura
import difflib
import urllib3
import xml.etree.ElementTree as ET
from urllib.parse import quote
from googlenewsdecoder import new_decoderv1
from google import genai
from google.genai import types

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ============== 설정 ==============
DATA_DIR = Path("data")
CONFIG_PATH = Path("config.json")

# 신뢰도 점수 시스템
TRUSTED_SOURCES = {
    # 1티어: 통신사/공영방송 (90~100점)
    "연합뉴스": 100, "연합뉴스TV": 100,
    "KBS": 95, "MBC": 95, "SBS": 95, "YTN": 90, "JTBC": 90,
    # 2티어: 종합일간지 (80~89점)
    "조선일보": 85, "중앙일보": 85, "동아일보": 85,
    "한겨레": 85, "경향신문": 85, "한국일보": 85, "국민일보": 80,
    # 3티어: 경제지 (70~79점)
    "매일경제": 80, "한국경제": 80, "서울경제": 75, 
    "머니투데이": 75, "이데일리": 75, "파이낸셜뉴스": 75,
    # 4티어: 인터넷 언론 (60~69점)
    "뉴스1": 70, "뉴시스": 70, "노컷뉴스": 65, "오마이뉴스": 65,
    # 기본값
    "default": 50
}

def load_config():
    """config.json에서 설정을 로드합니다."""
    default_config = {
        "keywords": [
            {"name": "일학습병행", "color": "#3498db", "enabled": True},
            {"name": "직업훈련", "color": "#e67e22", "enabled": True},
            {"name": "고용노동부", "color": "#7f8c8d", "enabled": True},
            {"name": "한국산업인력공단", "color": "#2c3e50", "enabled": True}
        ],
        "receivers": [],
        "settings": {
            "similarity_threshold": 0.5,
            "max_articles_per_keyword": 50
        }
    }
    
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
                for key in default_config:
                    if key not in config:
                        config[key] = default_config[key]
                for key in default_config["settings"]:
                    if key not in config.get("settings", {}):
                        config.setdefault("settings", {})[key] = default_config["settings"][key]
                return config
        except Exception as e:
            print(f"[WARN] config.json 로드 실패: {e}, 기본값 사용")
            return default_config
    return default_config

# 설정 로드
CONFIG = load_config()
KEYWORDS = [kw["name"] for kw in CONFIG["keywords"] if kw.get("enabled", True)]
KEYWORD_COLORS = {kw["name"]: kw["color"] for kw in CONFIG["keywords"]}
SIMILARITY_THRESHOLD = CONFIG["settings"].get("similarity_threshold", 0.5)
MAX_ARTICLES = CONFIG["settings"].get("max_articles_per_keyword", 50)

# 환경변수 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
EMAIL_USER = os.environ.get("EMAIL_USER")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# 이메일 수신자: 환경변수 + config.json 병합
ENV_RECEIVERS = os.environ.get("EMAIL_RECEIVER", "")
CONFIG_RECEIVERS = [r["email"] for r in CONFIG.get("receivers", []) if r.get("enabled", True)]
env_receiver_list = [addr.strip() for addr in ENV_RECEIVERS.split(',') if addr.strip()]
ALL_RECEIVERS = list(set(env_receiver_list + CONFIG_RECEIVERS))

# ============== 유틸 ==============
def clean_html(raw_html):
    """HTML 태그 및 특수문자 제거"""
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.replace("&quot;", "'").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'")

def normalize_title(title):
    """제목 정규화 (중복 방지를 위해 언론사명, 구두점 등 제거)"""
    # 1. [...]나 (...) 형태의 언론사 태그 제거
    title = re.sub(r'\[.*?\]|\(.*?\)', '', title)
    # 2. 특수문자 제거 및 공백 유지 (단어 단위 분절을 위해)
    title = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', title)
    return title.strip()

def is_similar_title(t1, t2, threshold=0.5):
    """두 제목이 실질적으로 같은 내용을 다루는지 검사"""
    if not t1 or not t2: return False
    
    # 순수 문자열 유사도 (difflib)
    ratio = difflib.SequenceMatcher(None, t1.replace(" ", ""), t2.replace(" ", "")).ratio()
    if ratio >= threshold: return True
    
    # 단어 집합 유사도 (Jaccard Similarity 개념 활용)
    # 어순이 다르거나 조사가 달라도 핵심 단어가 겹치면 중복으로 판단
    words1 = set(t1.split())
    words2 = set(t2.split())
    
    if not words1 or not words2: return False
    
    intersection = words1.intersection(words2)
    smaller_set_size = min(len(words1), len(words2))
    
    # 핵심 단어의 60% 이상이 겹치면 중복으로 간주
    if len(intersection) / smaller_set_size >= 0.6:
        return True
        
    return False

def filter_unique_articles_with_llm(articles):
    """LLM을 사용하여 서로 다른 언론사의 비슷한 기사들을 그룹화하고 대표 기사만 선정"""
    if len(articles) <= 1:
        return articles

    # 제목 리스트 생성 (번호 포함)
    titles_list = "\n".join([f"{i+1}. {a['제목']}" for i, a in enumerate(articles)])
    
    prompt = (
        "아래 뉴스 제목들을 읽고, 서로 다른 언론사에서 보도했지만 사실상 같은 소식이나 사건을 다루는 기사들을 그룹화해줘.\n"
        "각 그룹 내에서는 가장 대표성이 있는 기사 번호 하나만 선택해.\n"
        "최종적으로 선택된 기사 번호들만 쉼표로 구분해서 보내줘. 다른 설명은 하지 마.\n"
        "예시: 1, 4, 7\n\n"
        f"뉴스 제목 리스트:\n{titles_list}"
    )
    
    print(f"   [AI 그룹화] {len(articles)}건 분석 중...")
    response = call_gemini_api(prompt)
    time.sleep(6) # API Rate Limit 준수
    
    if not response:
        return articles
        
    try:
        # 응답에서 숫자만 추출 (예: "1, 4, 7" -> [0, 3, 6])
        indices = [int(idx) - 1 for idx in re.findall(r'\d+', response)]
        # 유효한 범위 내의 인덱스만 선택
        unique_indices = [i for i in indices if 0 <= i < len(articles)]
        
        if not unique_indices:
            return articles
            
        # 선택된 기사들만 반환 (순서 유지)
        seen = set()
        chosen_articles = []
        for i in unique_indices:
            if i not in seen:
                chosen_articles.append(articles[i])
                seen.add(i)
        
        return chosen_articles
    except Exception as e:
        print(f"   [WARN] AI 그룹화 분석 실패: {e}")
        return articles

def get_source_score(url, title):
    """출처 신뢰도 점수 반환"""
    text_to_check = url + " " + title
    for source, score in TRUSTED_SOURCES.items():
        if source == "default":
            continue
        if source in text_to_check:
            return score, source
    return TRUSTED_SOURCES["default"], "기타"

# ============== AI 기능 (Gemini API) ==============
def call_gemini_api(prompt):
    """Gemini API 호출"""
    if not GEMINI_API_KEY: 
        print("[ERROR] GEMINI_API_KEY가 없습니다.")
        return ""
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.5,
                max_output_tokens=500
            )
        )
        return response.text.strip()
    except Exception as e:
        print(f"[WARN] Gemini API 오류: {e}")
        return ""

def summarize_article(text: str) -> str:
    """기사 요약 (3줄 형식, 말머리 제거)"""
    prompt = (
        "아래 뉴스 기사를 읽고 중요한 내용을 딱 3문장으로 요약해줘.\n"
        "조건:\n"
        "1. 각 문장은 가독성 좋게 불렛포인트(-)로 시작할 것.\n"
        "2. '핵심:', '배경:' 같은 말머리 단어는 절대 넣지 말고 내용만 작성할 것.\n"
        "3. 한국어로 정중하게 작성할 것.\n\n"
        f"기사 내용:\n{text[:3500]}"
    )
    return call_gemini_api(prompt)

# ============== 구글 뉴스 URL 변환 ==============
def resolve_google_news_url(google_url: str) -> str:
    """구글 뉴스 리다이렉트 URL을 실제 기사 URL로 변환"""
    if not google_url or "news.google.com" not in google_url:
        return google_url
    
    try:
        # googlenewsdecoder 라이브러리 사용
        result = new_decoderv1(google_url)
        if result.get("status"):
            return result["decoded_url"]
        return google_url
    except Exception as e:
        print(f"[WARN] URL 변환 실패: {e}")
        return google_url

# ============== 본문 추출 ==============
def extract_article_content(url: str) -> str:
    """URL에서 기사 본문 추출"""
    if not url: 
        return ""
    
    # 구글 뉴스 URL이면 실제 URL로 변환
    actual_url = resolve_google_news_url(url)
    if actual_url != url:
        print(f"   [URL 변환] {url[:50]}... -> {actual_url[:50]}...")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        # Trafilatura 시도 (변환된 URL 사용)
        downloaded = trafilatura.fetch_url(actual_url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if text and len(text) >= 100: 
                return text

        # Requests 시도 (변환된 URL 사용)
        resp = requests.get(actual_url, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200:
            text = trafilatura.extract(resp.text, include_comments=False)
            if text and len(text) >= 100: 
                return text
        return ""
    except Exception as e:
        print(f"[WARN] 본문 추출 실패: {e}")
        return ""

# ============== 구글 뉴스 RSS ==============
def crawl_google_news(keyword, target_date_str):
    """구글 뉴스 RSS로 기사 수집"""
    encoded_keyword = quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded_keyword}+when:1d&hl=ko&gl=KR&ceid=KR:ko"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        items = root.findall('.//item')
    except Exception as e:
        print(f"[WARN] [{keyword}] 구글 뉴스 RSS 오류: {e}")
        return []
    
    rows = []
    collected_at = pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M")
    
    for item in items:
        try:
            title_elem = item.find('title')
            link_elem = item.find('link')
            pub_date_elem = item.find('pubDate')
            source_elem = item.find('source')
            
            if title_elem is None or link_elem is None:
                continue
                
            title = clean_html(title_elem.text or "")
            link = link_elem.text or ""
            source_name = source_elem.text if source_elem is not None else "기타"
            
            # 날짜 파싱
            pub_date_str = collected_at
            if pub_date_elem is not None and pub_date_elem.text:
                try:
                    pub_date_dt = datetime.strptime(pub_date_elem.text, "%a, %d %b %Y %H:%M:%S %Z")
                    pub_date_str = pub_date_dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            
            # 중복 비교용 제목 정규화
            norm_title = normalize_title(title)
            for k in KEYWORDS:
                norm_title = norm_title.replace(k, "")
            
            # 신뢰도 점수 계산
            score, detected_source = get_source_score(link, title + " " + source_name)
            if detected_source == "기타":
                detected_source = source_name
            
            rows.append({
                "키워드": keyword,
                "제목": title,
                "원문링크": link,
                "출처": detected_source,
                "신뢰도": score,
                "발행일(KST)": pub_date_str,
                "수집시각(KST)": collected_at,
                "요약": "",
                "_title_norm": norm_title
            })
            
        except Exception as e:
            continue
    
    print(f"   [{keyword}] {len(rows)}건 수집")
    return rows

# ============== 이메일 발송 ==============
def send_email_report(df_new, target_date_str):
    """이메일 리포트 발송"""
    if not EMAIL_USER or not EMAIL_PASSWORD or not ALL_RECEIVERS: 
        print("[INFO] 이메일 설정 없음, 발송 건너뜀")
        return
    if df_new.empty: 
        return

    receivers = ALL_RECEIVERS
    subject = f"[뉴스리포트] {target_date_str} 주요 뉴스 알림"

    html_body = f"""
    <div style="font-family: 'Malgun Gothic', sans-serif; background-color: #f4f4f4; padding: 20px; color: #333;">
        <div style="max-width: 700px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
            <div style="text-align: center; margin-bottom: 30px; border-bottom: 2px solid #555; padding-bottom: 20px;">
                <h1 style="color: #2c3e50; font-size: 24px; margin: 0;">{target_date_str} 뉴스 리포트</h1>
                <p style="color: #7f8c8d; font-size: 14px; margin-top: 10px;">
                    총 <span style="color:#e67e22; font-weight:bold;">{len(df_new)}</span>건의 기사 요약
                </p>
            </div>
    """

    grouped = df_new.groupby("키워드")
    for kw in KEYWORDS:
        if kw in grouped.groups:
            group_df = grouped.get_group(kw)
            group_df = group_df.sort_values("신뢰도", ascending=False)
            kw_color = KEYWORD_COLORS.get(kw, "#333333")
            
            html_body += f"""
            <div style="margin-bottom: 30px;">
                <div style="background-color: {kw_color}; color: white; padding: 6px 15px; display: inline-block; border-radius: 15px; font-weight: bold; font-size: 16px; margin-bottom: 15px;">
                    # {kw}
                </div>
            """
            for idx, row in group_df.iterrows():
                title = row['제목']
                link = row['원문링크']
                date = row['발행일(KST)']
                summary = row['요약']
                source = row.get('출처', '기타')
                score = row.get('신뢰도', 50)
                summary_html = summary.replace('\n', '<br>')
                
                if score >= 90:
                    badge_color = "#27ae60"
                elif score >= 70:
                    badge_color = "#3498db"
                else:
                    badge_color = "#95a5a6"
                
                html_body += f"""
                <div style="border: 1px solid #e0e0e0; border-radius: 8px; padding: 20px; margin-bottom: 15px; background-color: #fff;">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 8px;">
                        <a href="{link}" target="_blank" style="font-size: 18px; font-weight: bold; color: #2c3e50; text-decoration: none; line-height: 1.4; flex: 1;">
                            {title}
                        </a>
                        <span style="background-color: {badge_color}; color: white; padding: 2px 8px; border-radius: 10px; font-size: 11px; margin-left: 10px; white-space: nowrap;">
                            {source}
                        </span>
                    </div>
                    <div style="font-size: 12px; color: #95a5a6; margin-bottom: 15px;">{date}</div>
                    <div style="background-color: #f9f9f9; padding: 15px; border-left: 4px solid {kw_color}; color: #555; font-size: 14px; line-height: 1.6; border-radius: 4px;">
                        {summary_html}
                    </div>
                    <div style="text-align: right; margin-top: 10px;">
                        <a href="{link}" target="_blank" style="display: inline-block; background-color: #ecf0f1; color: #555; padding: 5px 12px; border-radius: 4px; text-decoration: none; font-size: 12px;">
                            원문 보기
                        </a>
                    </div>
                </div>
                """
            html_body += '</div>'

    html_body += """
            <div style="text-align: center; margin-top: 40px; font-size: 12px; color: #bdc3c7; border-top: 1px solid #eee; padding-top: 20px;">
                Automated by GitHub Actions
            </div>
        </div>
    </div>
    """

    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = EMAIL_USER
        msg['To'] = ", ".join(receivers) 
        msg.attach(MIMEText(html_body, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_USER, receivers, msg.as_string())
            
        print(f"[OK] 이메일 발송 성공 (수신자: {len(receivers)}명)")
    except Exception as e:
        print(f"[ERROR] 이메일 발송 실패: {e}")

# ============== 메인 ==============
def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    now_kst = pd.Timestamp.now(tz="Asia/Seoul")
    yesterday_kst = now_kst - pd.Timedelta(days=1)
    target_date_str = yesterday_kst.strftime("%Y-%m-%d")
    print(f"[INFO] 타겟 날짜: {target_date_str}")

    all_path = DATA_DIR / "ALL.csv"
    req_cols = ["키워드","제목","원문링크","출처","신뢰도","발행일(KST)","수집시각(KST)","요약","_title_norm"]
    
    if all_path.exists():
        df_existing = pd.read_csv(all_path, dtype=str, encoding="utf-8-sig")
        for c in req_cols: 
            if c not in df_existing.columns: 
                df_existing[c] = ""
        existing_titles = list(df_existing["_title_norm"].dropna().astype(str))
        existing_urls = list(df_existing["원문링크"].dropna().astype(str))
    else:
        df_existing = pd.DataFrame(columns=req_cols)
        existing_titles = []
        existing_urls = []

    # === 1단계: 뉴스 수집 (구글 RSS) ===
    print("[STEP 1] 뉴스 수집 중...")
    raw_rows = []
    for kw in KEYWORDS:
        raw_rows.extend(crawl_google_news(kw, target_date_str))
        time.sleep(0.3)
    
    if not raw_rows: 
        print(f"[INFO] {target_date_str} 날짜에 해당하는 기사가 없습니다.")
        return

    print(f"   총 {len(raw_rows)}건 수집 완료")

    # === 2단계: 중복 제거 (URL + 제목 유사도) ===
    print(f"[STEP 2] 중복 제거 (URL 매칭 및 유사도 {int(SIMILARITY_THRESHOLD*100)}%)...")
    unique_rows = []
    
    for row in raw_rows:
        new_title_norm = row["_title_norm"]
        new_url = row["원문링크"]
        is_duplicate = False
        
        # 1. URL 기반 중복 체크 (가장 정확)
        if new_url in existing_urls:
            is_duplicate = True
        
        # 2. 제목 유사도 기반 체크 (이미 URL로 발견되지 않은 경우)
        if not is_duplicate:
            for exist_title in existing_titles:
                if is_similar_title(new_title_norm, exist_title, SIMILARITY_THRESHOLD):
                    is_duplicate = True
                    break
        
        if is_duplicate: 
            continue
        
        # 3. 현재 수집된 기사 내에서 중복 체크
        for accepted in unique_rows:
            # URL 중복
            if new_url == accepted["원문링크"]:
                is_duplicate = True
                break
            # 제목 유사도 중복
            if is_similar_title(new_title_norm, accepted["_title_norm"], SIMILARITY_THRESHOLD):
                is_duplicate = True
                break
        
        if not is_duplicate:
            unique_rows.append(row)

    # === 2.5단계: AI 기반 고도화 중복 제거 (LLM Grouping) ===
    if unique_rows:
        print(f"[STEP 2.5] AI 기반 고도화 중복 제거...")
        final_unique_rows = []
        # 키워드별로 묶어서 AI에게 전달 (API 효율성 및 컨택스트 유지)
        for kw_info in CONFIG.get("keywords", []):
            if not kw_info.get("enabled", True): continue
            kw = kw_info["name"]
            kw_articles = [r for r in unique_rows if r["키워드"] == kw]
            
            if len(kw_articles) > 1:
                grouped = filter_unique_articles_with_llm(kw_articles)
                final_unique_rows.extend(grouped)
            else:
                final_unique_rows.extend(kw_articles)
        
        unique_rows = final_unique_rows

    # === 3단계: 신뢰도 순 정렬 및 상위 N개 선택 ===
    print(f"[STEP 3] 신뢰도 순 정렬...")
    unique_rows = sorted(unique_rows, key=lambda x: x.get("신뢰도", 50), reverse=True)
    
    # 키워드당 최대 기사 수 제한
    keyword_count = {}
    filtered_rows = []
    for row in unique_rows:
        kw = row["키워드"]
        keyword_count[kw] = keyword_count.get(kw, 0) + 1
        if keyword_count[kw] <= MAX_ARTICLES:
            filtered_rows.append(row)
    
    unique_rows = filtered_rows
    print(f"   {len(raw_rows)}건 -> 중복제거/필터 후 {len(unique_rows)}건")

    if not unique_rows:
        print("[INFO] 처리할 신규 기사가 없습니다.")
        return

    # === 4단계: 본문 추출 + 키워드 관련성 체크 ===
    print(f"[STEP 4] 본문 추출 및 관련성 체크...")
    relevant_rows = []
    for row in unique_rows:
        keyword = row["키워드"]
        content = extract_article_content(row["원문링크"])
        
        if content:
            # 키워드 관련성 체크
            if keyword in content or keyword in row['제목']:
                row["_content"] = content
                relevant_rows.append(row)
            else:
                print(f"   [제외] 본문에 '{keyword}' 없음: {row['제목'][:30]}...")
        else:
            # 본문 추출 실패해도 제목에 키워드 있으면 포함
            if keyword in row['제목']:
                row["_content"] = ""
                relevant_rows.append(row)
    
    print(f"   관련성 체크 후 {len(relevant_rows)}건")

    if not relevant_rows:
        print("[INFO] 관련 기사가 없습니다.")
        return

    # === 5단계: AI 요약 (최종 필터된 기사만) ===
    print(f"[STEP 5] AI 요약 생성 중 ({len(relevant_rows)}건)...")
    processed_rows = []
    for i, row in enumerate(relevant_rows):
        print(f"   ({i+1}/{len(relevant_rows)}) [{row.get('출처', '?')}] {row['제목'][:25]}...")
        
        content = row.get("_content", "")
        summary = ""
        
        if content:
            summary = summarize_article(content)
            time.sleep(6)  # Gemini API Rate Limit (분당 10 요청)
        
        if not summary:
            summary = "- 요약을 생성할 수 없습니다."
            
        row["요약"] = summary
        if "_content" in row:
            del row["_content"]
        processed_rows.append(row)

    # === 6단계: 저장 및 이메일 발송 ===
    if processed_rows:
        df_new_processed = pd.DataFrame(processed_rows)
        
        print(f"[STEP 6] 이메일 발송...")
        send_email_report(df_new_processed, target_date_str)
        
        # CSV 저장
        df_final_new = df_new_processed[req_cols]
        combined = pd.concat([df_existing, df_final_new], ignore_index=True)
        combined = combined.drop_duplicates(subset=["_title_norm"], keep="last")
        combined = combined.sort_values("수집시각(KST)", ascending=False)

        display_cols = ["키워드","제목","출처","요약","원문링크","발행일(KST)","수집시각(KST)"]
        combined[display_cols].to_csv(DATA_DIR / "ALL.csv", index=False, encoding="utf-8-sig")
        df_final_new[display_cols].to_csv(DATA_DIR / "NEW_latest.csv", index=False, encoding="utf-8-sig")
        
        print("[DONE] 완료!")
    else:
        print("[INFO] 처리할 기사가 없습니다.")

if __name__ == "__main__":
    main()
