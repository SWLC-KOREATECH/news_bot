# 📰 뉴스봇 - 키워드 뉴스 자동 알림 시스템

매일 아침, 설정한 키워드의 뉴스를 **AI가 요약**하여 이메일로 받아보세요!

---

## ✨ 주요 기능

- 🔍 **키워드 뉴스 수집**: 구글 뉴스 RSS로 관심 키워드 뉴스 자동 수집
- 🤖 **AI 요약**: Groq AI가 기사를 3줄로 요약 (핵심/배경/영향)
- 📧 **이메일 알림**: 매일 오전 8:30(KST)에 리포트 발송
- 🏆 **신뢰도 필터**: 주요 언론사 기사 우선 표시
- 🔄 **중복 제거**: 유사 기사 자동 필터링

---

## 🏗️ 시스템 구조

```
┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
│   구글 뉴스 RSS  │ ──→ │   GitHub Actions │ ──→ │    이메일 발송   │
│   (뉴스 수집)    │      │   (매일 08:30)   │      │   (Gmail SMTP)  │
└─────────────────┘      └────────┬────────┘      └─────────────────┘
                                  │
                                  ↓
                         ┌─────────────────┐
                         │    Groq AI      │
                         │  (기사 요약)     │
                         └─────────────────┘
```

### 📊 처리 흐름 (토큰 효율화)

AI 토큰을 효율적으로 사용하기 위해 다음 순서로 처리됩니다:

```
1. 뉴스 수집 (구글 RSS)
        ↓
2. 중복 제거 (제목 유사도 50%)
        ↓
3. 신뢰도 순 정렬 (연합뉴스 > KBS > ... > 기타)
        ↓
4. 키워드 관련성 체크 (본문에 키워드 포함?)
        ↓                             ← 여기까지 AI 토큰 0
────────────────────────────────────────────────
        ↓                             ← 여기서부터 토큰 사용
5. AI 요약 생성 (3줄: 핵심/배경/영향)
        ↓
6. 이메일 발송 + CSV 저장
```

---

## 🚀 시작하기 (약 10분 소요)

### 📋 준비물

| 항목 | 용도 | 비용 |
|------|------|------|
| GitHub 계정 | 코드 저장 및 자동 실행 | 무료 |
| Groq 계정 | AI 요약 API | 무료 |
| Gmail 계정 | 이메일 발송 | 무료 |

---

## 📝 설정 가이드

### 1단계: 레포지토리 복사

1. 이 레포지토리 상단의 **[Use this template]** 버튼 클릭
2. Repository name 입력 (예: `my-news-bot`)
3. **Public/Private 선택**
   > [!IMPORTANT]
   > **개인정보 보호(이메일 주소 등)를 위해 `Private` 레포지토리로 생성하는 것을 강력히 권장합니다.** `Public`으로 생성 시 `config.json`에 기입한 이메일 주소가 공개될 수 있습니다.
4. **Create repository** 클릭

> 💡 Template을 사용하면 대시보드, 설정 파일 등 모든 파일이 복사됩니다!

---

### 2단계: API 키 발급

#### 🔑 2-1. Groq API (AI 요약용)

1. [Groq Console](https://console.groq.com/) 접속
2. Google 또는 이메일로 회원가입
3. 좌측 메뉴 **API Keys** 클릭
4. **Create API Key** → 이름 입력 → 생성
5. 생성된 API 키 복사 (한 번만 표시됨!)

#### 🔑 2-2. Gmail 앱 비밀번호

> ⚠️ 일반 비밀번호가 아닌 **앱 비밀번호**가 필요합니다.

1. [Google 계정 관리](https://myaccount.google.com/) 접속
2. **보안** 탭 클릭
3. **2단계 인증** 활성화 (이미 되어있으면 건너뛰기)
4. 2단계 인증 설정 페이지 하단의 **앱 비밀번호** 클릭
5. 앱: `메일`, 기기: `Windows 컴퓨터` 선택
6. **생성** → 16자리 비밀번호 복사

---

### 3단계: GitHub Secrets 설정

생성한 레포지토리에서:

1. **Settings** 탭 클릭
2. 좌측 **Secrets and variables** → **Actions** 클릭
3. **New repository secret** 버튼으로 아래 항목 추가:

| Name | Value |
|------|-------|
| `GROQ_API_KEY` | Groq에서 발급받은 API Key |
| `EMAIL_USER` | 발신용 Gmail 주소 (예: `your@gmail.com`) |
| `EMAIL_PASSWORD` | Gmail 앱 비밀번호 (16자리) |
| `EMAIL_RECEIVER` | 수신자 이메일 (쉼표로 구분 가능) |

---

### 4단계: 테스트 실행

1. **Actions** 탭 클릭
2. 좌측에서 **Daily News** 워크플로우 선택
3. **Run workflow** 버튼 클릭 → **Run workflow**
4. 실행 완료 후 이메일 수신 확인!

---

## 🖥️ 웹 대시보드 (선택)

GitHub Pages를 활성화하면 웹에서 키워드와 수신자를 관리할 수 있습니다.

### 대시보드 설정 방법

1. **Settings** → **Pages** 이동
2. Source를 `main` 브랜치로 설정
3. **Save** 클릭
4. 약 1분 후 `https://내아이디.github.io/레포지토리명/dashboard/` 접속

### 대시보드 기능

| 기능 | 설명 |
|------|------|
| 키워드 관리 | 추가, 삭제, ON/OFF, 색상 변경 |
| 수신자 관리 | 이메일 추가, 삭제, ON/OFF |
| 고급 설정 | 유사도 임계값, 최대 기사 수 |
| GitHub 저장 | 설정을 config.json에 자동 저장 |

> 💡 대시보드 최초 접속 시 GitHub Personal Access Token을 1회 입력해야 합니다.

---

## ⚙️ 키워드 직접 수정 (대안)

`config.json` 파일을 직접 편집해도 됩니다:

```json
{
  "keywords": [
    {"name": "일학습병행", "color": "#3498db", "enabled": true},
    {"name": "직업훈련", "color": "#e67e22", "enabled": true},
    {"name": "새로운키워드", "color": "#9b59b6", "enabled": true}
  ],
  "receivers": [
    {"email": "additional@example.com", "enabled": true}
  ],
  "settings": {
    "similarity_threshold": 0.5,
    "max_articles_per_keyword": 50
  }
}
```

---

## 📁 파일 구조

```
news_bot/
├── .github/workflows/
│   └── daily.yml           🔄 GitHub Actions 스케줄 (매일 08:30)
├── dashboard/              🖥️ 웹 대시보드 (선택)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── data/                   📊 데이터 저장 (자동 생성)
│   ├── ALL.csv             - 전체 뉴스 기록
│   └── NEW_latest.csv      - 최신 뉴스
├── config.json             ⚙️ 설정 (키워드, 수신자)
├── web_news.py             🐍 메인 스크립트
├── requirements.txt        📦 Python 의존성
└── README.md               📖 사용 가이드
```

---

## ⏰ 실행 스케줄

- **자동 실행**: 매일 오전 08:30 (한국 시간)
- **수동 실행**: Actions 탭에서 언제든 가능

---

## 💰 비용

| 항목 | 비용 |
|------|------|
| GitHub Actions | 무료 (월 2,000분) |
| 구글 뉴스 RSS | 무료 |
| Groq AI | 무료 (일 14,400건 요청) |
| Gmail SMTP | 무료 |
| **총 비용** | **0원** |

---

## 🔧 문제 해결

### 이메일이 안 와요
- `EMAIL_PASSWORD`가 **앱 비밀번호**인지 확인
- Gmail 보안 설정에서 앱 접근 허용 확인

### Actions가 실패해요
- Actions 탭에서 실패한 워크플로우 클릭 → 로그 확인
- Secrets 이름이 정확한지 대소문자 확인

### 뉴스가 0건이에요
- 해당 날짜에 관련 뉴스가 없을 수 있음
- 키워드를 더 일반적인 것으로 변경해 보기

---

## 📄 라이선스

MIT License - 자유롭게 사용, 수정, 배포 가능합니다.
