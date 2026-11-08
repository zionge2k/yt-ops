# 지금 새로고침 함수

상황판의 "지금 새로고침" 버튼이 부르는 Vercel 함수예요. 비밀번호를 확인한 뒤 GitHub 의 `refresh.yml` 워크플로를 실행해요.
30분 안에 이미 실행했다면 429 로 돌려보내요(전체 수집이 프로젝트당 약 400단위라서)(따로 저장하는 곳 없이 GitHub 의 최근 실행 시각으로 판단).

## 환경변수
- `GITHUB_TOKEN` — fine-grained PAT. 저장소 zionge2k/yt-ops, Actions 읽기+쓰기 권한만.
- `DASH_PASSWORD` — 상황판 비밀번호와 같은 값.
- `ALLOWED_ORIGIN` — 선택. 기본값 `https://zionge2k.github.io`.

## 올리기 (이 폴더에서)
```
npx vercel login
npx vercel env add GITHUB_TOKEN production
npx vercel env add DASH_PASSWORD production
npx vercel --prod
```
나온 주소(`…/api/refresh`)를 `site/app.js` 의 `REFRESH_URL` 에 넣어야 버튼이 보여요.

## 테스트
`node --test`
