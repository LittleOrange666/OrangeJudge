import os
from threading import Timer

import redis

redis_host = os.environ.get("REDIS_HOST", "localhost")
r = redis.Redis(host=redis_host, port=6379, decode_responses=True)

PROGRESS_MSG = "progress"
COMPLETED_MSG = "completed"

def pub_submission_info(submission_id: int, info: str):
    r.publish(f"submission_info:{submission_id}", info)

def submission_info_cleaner(submission_id: int):
    pub_submission_info(submission_id, COMPLETED_MSG)

def create_submission_info_cleaner(submission_id: int, timeout) -> Timer:
    cleaner_thread = Timer(timeout, submission_info_cleaner, (submission_id, ))
    cleaner_thread.daemon = True
    cleaner_thread.start()
    return cleaner_thread

def submission_info_receiver(submission_id: int):
    cleaner_thread = create_submission_info_cleaner(submission_id, 60)
    pubsub = r.pubsub()
    pubsub.subscribe(f"submission_info:{submission_id}")
    try:
        yield f"info: connected\n\n"

        for message in pubsub.listen():
            if message['type'] == 'message':
                payload = message['data']
                yield f"data: {payload}\n\n"
                if COMPLETED_MSG in payload:
                    break
    finally:
        pubsub.unsubscribe(f"submission_info:{submission_id}")
        pubsub.close()
        cleaner_thread.cancel()

def end_sender():
    yield f"info: connected\n\n"
    yield f"data: {COMPLETED_MSG}\n\n"