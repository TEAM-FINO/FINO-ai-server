import sys
import os
from typing import Dict, Any

def get_logging_config(log_level: str, env_mode: str) -> Dict[str, Any]:
    """
    환경에 따라 로깅 설정을 반환합니다.
    
    Args:
        log_level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        env_mode: 환경 모드 (development, production)
    
    Returns:
        logging.config.dictConfig에 전달할 딕셔너리
    """
    
    # 개발/프로덕션에 따라 포맷터 선택
    console_formatter = 'json' if env_mode == 'production' else 'detailed'
    
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        
        'formatters': {
            # 개발용: 상세한 포맷
            'detailed': {
                'format': '%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            # 프로덕션용: 간결한 포맷
            'simple': {
                'format': '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S',
            },
            # 프로덕션용: JSON 포맷 (구조화된 로그)
            'json': {
                '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
                'format': '%(asctime)s %(name)s %(levelname)s %(message)s %(pathname)s %(lineno)d',
                'datefmt': '%Y-%m-%dT%H:%M:%S',
            },
        },
        
        'handlers': {
            # 콘솔 출력
            'console': {
                'class': 'logging.StreamHandler',
                'stream': sys.stdout,
                'formatter': console_formatter,
                'level': 'DEBUG',  # 핸들러 레벨은 DEBUG로, 실제 필터링은 로거에서
            },
            # 파일 출력 (선택적, 프로덕션용)
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': '/var/log/fino-ai/app.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'formatter': 'json' if env_mode == 'production' else 'detailed',
                'level': 'INFO',
            },
        },
        
        'loggers': {
            # 애플리케이션 루트 로거
            'app': {
                'handlers': ['console'],
                'level': log_level.upper(),
                'propagate': False,
            },
            
            # 외부 라이브러리 로거 레벨 설정
            'neo4j': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False,
            },
            'httpx': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False,
            },
            'httpcore': {
                'handlers': ['console'],
                'level': 'WARNING',
                'propagate': False,
            },
            'chromadb': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.worker': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'uvicorn': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
            'uvicorn.access': {
                'handlers': ['console'],
                'level': 'WARNING',  # Access 로그는 WARNING 이상만
                'propagate': False,
            },
            'uvicorn.error': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
        },
        
        # Root 로거 (명시적으로 설정되지 않은 모든 로거)
        'root': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
    }
    
    # 파일 로깅은 명시적으로 활성화된 경우에만 추가
    enable_file_logging = os.getenv('ENABLE_FILE_LOGGING', 'false').lower() == 'true'
    
    if enable_file_logging:
        log_dir = '/var/log/fino-ai'
        log_file = os.path.join(log_dir, 'app.log')
        
        # 디렉토리 생성 시도 및 권한 오류 처리
        try:
            os.makedirs(log_dir, exist_ok=True)
            
            config['handlers']['file'] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': log_file,
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'formatter': 'json' if env_mode == 'production' else 'detailed',
                'level': 'INFO',
            }
            
            # 모든 로거에 file 핸들러 추가
            for logger_name in config['loggers']:
                if 'handlers' in config['loggers'][logger_name]:
                    config['loggers'][logger_name]['handlers'].append('file')
            
            # Root 로거에도 추가
            config['root']['handlers'].append('file')
            
        except PermissionError:
            # Docker 컨테이너에서 권한 문제 발생 가능
            print(f"⚠️  Warning: Cannot create log directory {log_dir}. File logging disabled.")
        except Exception as e:
            print(f"⚠️  Warning: Failed to setup file logging: {e}")    
    
    return config