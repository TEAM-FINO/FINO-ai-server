import logging
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from app.core.config import settings
import redis 
import json

logger = logging.getLogger(__name__)

# Redis 클라이언트 초기화
# settings.CELERY_RESULT_BACKEND에서 Redis 주소를 가져와 재사용할 수 있습니다.
redis_client = redis.from_url(settings.CELERY_RESULT_BACKEND)
CACHE_EXPIRATION_SECONDS = 3600 # 캐시 유효 시간: 1시간

class GoogleApiService:
    def __init__(self):
        self.service: Resource = None
        # ENABLE_GOOGLE_API=true 일때만 서비스 초기화
        if settings.ENABLE_GOOGLE_API:
            try:
                self.service = build("customsearch", "v1", developerKey=settings.GOOGLE_API_KEY)
                logger.info("Google Custom Search API service initialized")
            except Exception as e:
                logger.error("Failed to initialize Google API service", exc_info=True)

    def get_search_trend_score(self, keyword: str) -> int:
        # ENABLE_GOOGLE_API 확인
        if not settings.ENABLE_GOOGLE_API or self.service is None:
            return 0 

        # Redis 캐시 확인
        cache_key = f"google_trend:{keyword}"
        cached_result = redis_client.get(cache_key)
        if cached_result:
            logger.debug(f"Redis cache hit for '{keyword}'.")
            return json.loads(cached_result)
            
        try:
            query = f'"{keyword}"'
            result = self.service.cse().list(
                q=query,
                cx=settings.GOOGLE_CSE_ID,
                fields="searchInformation/totalResults" # totalResults 필드만 요청
            ).execute()

            trend_score = int(result.get('searchInformation', {}).get('totalResults', 0))
            logger.info(f"Google Search Trend for '{keyword}': {trend_score} results.")
            
            # Redis에 결과 저장
            redis_client.set(cache_key, json.dumps(trend_score), ex=CACHE_EXPIRATION_SECONDS)

            return trend_score
        except HttpError as e:
            if e.resp.status == 429:
                logger.warning(f"Google API Quota Exceeded for keyword '{keyword}'!")
            else:
                logger.error(f"Google API HttpError occurred for keyword '{keyword}': {e}", exc_info=True)
            return 0
        except Exception as e:
            logger.error(f"Unexpected error in Google API for keyword '{keyword}': {e}", exc_info=True)
            return 0

google_api_service = GoogleApiService()