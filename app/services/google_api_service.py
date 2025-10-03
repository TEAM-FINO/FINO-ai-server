from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from app.core.config import settings

class GoogleApiService:
    _cache = {} # 인메모리 캐시

    def __init__(self):
        self.service: Resource = None
        # ENABLE_GOOGLE_API=true 일때만 서비스 초기화
        if settings.ENABLE_GOOGLE_API:
            try:
                self.service = build("customsearch", "v1", developerKey=settings.GOOGLE_API_KEY)
                print("Google Custom Search API service initialized.")
            except Exception as e:
                print(f"Failed to initialize Google API service: {e}")

    def get_search_trend_score(self, keyword: str) -> int:
        # ENABLE_GOOGLE_API 확인
        if not settings.ENABLE_GOOGLE_API or self.service is None:
            return 0 

        # 캐시 확인
        if keyword in self._cache:
            print(f"Cache hit for '{keyword}'. Returning cached score.")
            return self._cache[keyword]
            
        try:
            query = f'"{keyword}"'
            result = self.service.cse().list(
                q=query,
                cx=settings.GOOGLE_CSE_ID,
                fields="searchInformation/totalResults" # totalResults 필드만 요청
            ).execute()

            trend_score = int(result.get('searchInformation', {}).get('totalResults', 0))
            print(f"Google Search Trend for '{keyword}': {trend_score} results.")
            
            self._cache[keyword] = trend_score
            return trend_score
            
        except HttpError as e:
            if e.resp.status == 429:
                print(f"Google API Quota Exceeded for keyword '{keyword}'!")
            else:
                print(f"An HttpError occurred for keyword '{keyword}': {e}")
            return 0
        except Exception as e:
            print(f"An unexpected error occurred for keyword '{keyword}': {e}")
            return 0

google_api_service = GoogleApiService()