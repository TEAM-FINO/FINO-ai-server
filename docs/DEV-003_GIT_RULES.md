# Git 규칙

> **문서 번호**: DEV-003
> **버전**: 1.0
> **최종 수정일**: 2025-01-13
> **작성자**: FINO AI Team
> **검토자**: -

## 변경 이력

| 버전 | 날짜 | 작성자 | 변경 내용 |
|------|------|--------|----------|
| 1.0 | 2025-01-13 | FINO AI Team | 최초 작성 |

---

## 1. 개요

이 문서는 FINO AI Server 프로젝트의 Git 사용 규칙을 정의합니다. 일관된 브랜치 전략과 커밋 메시지 규칙을 통해 협업 효율성을 높이고 변경 이력을 명확하게 관리합니다.

---

## 2. 브랜치 전략

### 2.1 브랜치 구조

```
main                           # 프로덕션 배포 (보호됨)
│
├── develop                    # 개발 통합
│   │
│   ├── feat/#이슈번호_기능명     # 새 기능 개발
│   ├── fix/#이슈번호_버그명      # 버그 수정
│   ├── refactor/#이슈번호_대상   # 리팩토링
│   ├── docs/#이슈번호_문서명     # 문서 작성/수정
│   ├── test/#이슈번호_테스트명   # 테스트 추가
│   └── chore/#이슈번호_작업명    # 빌드, 설정 변경
│
└── hotfix/#이슈번호_긴급수정     # 프로덕션 긴급 수정
```

### 2.2 브랜치 명명 규칙

```
<type>/#<이슈번호>_<간단한_설명>
```

**예시**:
```
feat/#123_weekly_report_scheduling
fix/#124_celery_retry_logic
refactor/#125_report_chain_optimization
docs/#126_api_documentation
test/#127_workflow_integration_test
chore/#128_docker_compose_update
hotfix/#129_critical_db_connection
```

### 2.3 브랜치 설명

| 브랜치 | 용도 | 병합 대상 |
|--------|------|----------|
| `main` | 프로덕션 배포 코드 | - |
| `develop` | 개발 통합 브랜치 | main |
| `feat/*` | 새 기능 개발 | develop |
| `fix/*` | 버그 수정 | develop |
| `refactor/*` | 코드 리팩토링 | develop |
| `docs/*` | 문서 작업 | develop |
| `test/*` | 테스트 추가 | develop |
| `chore/*` | 빌드/설정 변경 | develop |
| `hotfix/*` | 긴급 수정 | main, develop |

---

## 3. 커밋 메시지

### 3.1 커밋 메시지 형식

```
[<type>]: <subject>

<body>

<footer>
```

### 3.2 Type 종류

| Type | 설명 | 예시 |
|------|------|------|
| `Feat` | 새로운 기능 추가 | 주간 리포트 스케줄링 기능 구현 |
| `Fix` | 버그 수정 | Celery 재시도 로직 오류 수정 |
| `Refactor` | 코드 리팩토링 | 리포트 체인 구조 개선 |
| `Docs` | 문서 수정 | API 문서 업데이트 |
| `Test` | 테스트 코드 추가/수정 | 워크플로우 통합 테스트 추가 |
| `Chore` | 빌드, 설정 변경 | Docker Compose 설정 수정 |
| `Style` | 코드 포맷팅, 세미콜론 누락 등 | 코드 스타일 정리 |
| `Perf` | 성능 개선 | LLM 응답 캐싱 적용 |

### 3.3 커밋 메시지 예시

**기본 형식**:
```
[Feat]: 주기적 리포트 생성 및 운영 고도화 기능 구현
```

**상세 형식**:
```
[Feat]: 주기적 리포트 생성 및 운영 고도화 기능 구현

- Celery Beat 스케줄러 추가 (주간/월간)
- 지역별 병렬 디스패치 로직 구현
- 재시도 전략 개선 (지수 백오프)

Closes #123
```

**버그 수정**:
```
[Fix]: LLM JSON 파싱 실패 시 재시도 로직 추가

- extract_json_from_text() 함수 개선
- 최대 3회 재시도 로직 추가
- 한국어 검증 로직 강화

Fixes #124
```

### 3.4 커밋 메시지 규칙

```
1. 제목은 50자 이내
2. 제목 끝에 마침표 금지
3. 제목과 본문 사이 빈 줄 추가
4. 본문은 72자마다 줄바꿈
5. "어떻게"보다 "무엇을", "왜"에 집중
6. 이슈 번호 연결 (Closes #123, Fixes #124)
```

---

## 4. Pull Request

### 4.1 PR 템플릿

```markdown
## Summary
<!-- 변경 사항을 간략하게 설명해주세요 -->

## Changes
<!-- 주요 변경 내용을 목록으로 작성해주세요 -->
-
-
-

## Test
<!-- 테스트 방법을 설명해주세요 -->
- [ ] 단위 테스트 통과
- [ ] 통합 테스트 통과
- [ ] 수동 테스트 완료

## Related Issues
<!-- 관련 이슈를 링크해주세요 -->
Closes #

## Checklist
- [ ] 코드 스타일 가이드 준수
- [ ] 문서 업데이트 (필요시)
- [ ] 테스트 추가 (필요시)
- [ ] 리뷰어 지정
```

### 4.2 PR 규칙

```
1. 하나의 PR은 하나의 기능/수정에 집중
2. PR 제목은 커밋 메시지 형식 따름
3. 최소 1명의 리뷰어 승인 필요
4. CI 테스트 통과 필수
5. 충돌 해결 후 머지
```

### 4.3 PR 크기 가이드

| 크기 | 변경 라인 수 | 권장 여부 |
|------|-------------|----------|
| XS | 0-10 | ✅ 이상적 |
| S | 10-50 | ✅ 좋음 |
| M | 50-200 | ⚠️ 주의 |
| L | 200-500 | ⚠️ 분할 권장 |
| XL | 500+ | ❌ 반드시 분할 |

---

## 5. Git 워크플로우

### 5.1 기능 개발 플로우

```bash
# 1. develop 브랜치에서 시작
git checkout develop
git pull origin develop

# 2. 기능 브랜치 생성
git checkout -b feat/#123_weekly_report

# 3. 작업 수행 및 커밋
git add .
git commit -m "[Feat]: 주간 리포트 스케줄링 기능 구현"

# 4. 원격 저장소에 푸시
git push origin feat/#123_weekly_report

# 5. PR 생성 (develop ← feat/#123_weekly_report)

# 6. 리뷰 후 머지

# 7. 로컬 브랜치 정리
git checkout develop
git pull origin develop
git branch -d feat/#123_weekly_report
```

### 5.2 핫픽스 플로우

```bash
# 1. main 브랜치에서 시작
git checkout main
git pull origin main

# 2. 핫픽스 브랜치 생성
git checkout -b hotfix/#129_critical_fix

# 3. 수정 및 커밋
git add .
git commit -m "[Fix]: 긴급 DB 연결 오류 수정"

# 4. main에 머지
git checkout main
git merge hotfix/#129_critical_fix
git push origin main

# 5. develop에도 머지
git checkout develop
git merge hotfix/#129_critical_fix
git push origin develop

# 6. 핫픽스 브랜치 삭제
git branch -d hotfix/#129_critical_fix
```

---

## 6. 금지 사항

### 6.1 절대 금지

```bash
# [X] main 브랜치에 직접 커밋
git checkout main
git commit -m "직접 커밋"  # 금지

# [X] force push to main/develop
git push --force origin main     # 금지
git push --force origin develop  # 금지

# [X] 민감 정보 커밋
git add .env                     # 금지
git add credentials.json         # 금지

# [X] 대용량 파일 커밋 (모델 파일 등)
git add models/llama-8b.bin      # 금지
```

### 6.2 주의 사항

```bash
# [!] 머지 전 리베이스
git rebase develop  # 충돌 주의

# [!] 커밋 수정
git commit --amend  # 푸시 전에만

# [!] 히스토리 변경
git rebase -i HEAD~3  # 푸시 전에만
```

---

## 7. .gitignore

### 7.1 필수 제외 항목

```gitignore
# 환경 설정
.env
.env.local
.env.*.local

# 파이썬
__pycache__/
*.py[cod]
*$py.class
.Python
venv/
.venv/

# IDE
.idea/
.vscode/
*.swp
*.swo

# 테스트
.coverage
htmlcov/
.pytest_cache/

# 빌드
dist/
build/
*.egg-info/

# 로그
*.log
logs/

# 모델 파일
models/
*.bin
*.safetensors

# 시크릿
*.pem
*.key
credentials.json

# OS
.DS_Store
Thumbs.db
```

---

## 8. 유용한 Git 명령어

### 8.1 자주 사용하는 명령어

```bash
# 상태 확인
git status
git log --oneline -10

# 브랜치 관리
git branch -a                    # 모든 브랜치 목록
git branch -d <branch>           # 로컬 브랜치 삭제
git push origin --delete <branch> # 원격 브랜치 삭제

# 변경 취소
git checkout -- <file>           # 파일 변경 취소
git reset HEAD <file>            # 스테이징 취소
git reset --soft HEAD~1          # 마지막 커밋 취소 (변경 유지)

# 스태시
git stash                        # 임시 저장
git stash pop                    # 복원
git stash list                   # 목록 확인

# 충돌 해결
git mergetool                    # 머지 도구 실행
```

### 8.2 Git Alias 권장

```bash
# ~/.gitconfig
[alias]
    st = status
    co = checkout
    br = branch
    ci = commit
    lg = log --oneline --graph --decorate
    unstage = reset HEAD --
    last = log -1 HEAD
```

---

## 관련 문서

- [DEV-001 코딩 컨벤션](./DEV-001_CODING_CONVENTION.md)
- [DEV-002 로그 규칙](./DEV-002_LOGGING_RULES.md)
