"""Playback coordination without media imports; used by the actual voice worker."""
import time


def play_response_audio(job, motion, motion_error, allow_audio_only,
                        play_motion, play_audio_only, on_started=None,
                        on_delivered=None, token=None):
    token = token if token is not None else {}
    started = False

    def notify_started():
        nonlocal started
        if started:
            return
        started = True
        token['audio_started'] = True
        token['audio_started_at'] = time.time()
        print(f'[AUDIO START] job={job.job_id}', flush=True)
        if on_started:
            try:
                on_started(job)
            except Exception as exc:
                token['panel_error'] = type(exc).__name__
                print(f'[DISPLAY ERROR] {type(exc).__name__}', flush=True)

    try:
        if motion is not None:
            try:
                play_motion(notify_started)
            except Exception as exc:
                # Never replay audio after it has started: this would duplicate speech.
                if started or not allow_audio_only:
                    raise
                token['motion_error'] = type(exc).__name__
                token['audio_only'] = True
                print(f'[AUDIO FALLBACK] motion playback failed before audio: {type(exc).__name__}', flush=True)
                play_audio_only(notify_started)
        elif allow_audio_only:
            token['motion_error'] = str(motion_error or 'Motion unavailable')
            token['audio_only'] = True
            print(f'[AUDIO FALLBACK] job={job.job_id}: {token["motion_error"]}', flush=True)
            play_audio_only(notify_started)
        else:
            token['playback_error'] = 'MOTION_REQUIRED'
            print(f'[AUDIO SKIPPED] job={job.job_id}: motion required', flush=True)
            return False
        if not started:
            raise RuntimeError('Audio backend returned without confirming start')
        token['audio_completed'] = True
        if on_delivered:
            on_delivered(job)
        return True
    except Exception as exc:
        token['playback_error'] = type(exc).__name__
        print(f'[AUDIO ERROR] job={job.job_id}: {type(exc).__name__}: {exc}', flush=True)
        return False
