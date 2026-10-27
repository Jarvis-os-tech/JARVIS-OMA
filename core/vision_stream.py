"""Optional one-FPS video never queues behind required voice traffic."""
import asyncio
import logging
import time

from core.audio_scheduler import SendStalled, VideoFrameDropped

log = logging.getLogger('gemini_voice')


async def stream_video(voice, session, *, budget, renew_exception):
    from google.genai import types

    last_frame_at = 0.0
    while True:
        if voice.vision_mode == 'off':
            await voice.vision_mode_event.wait()
        delay = 1.0 - (time.monotonic() - last_frame_at)
        if delay > 0:
            await asyncio.sleep(delay)
        if voice.vision_mode == 'off':
            continue
        last_frame_at = time.monotonic()
        generation = voice.sync_audio_generation()
        if voice.send_lock.should_choke_video() or voice.send_lock.locked():
            voice.send_lock.dropped_video_frames += 1
            continue
        try:
            capture = voice._capture_screen_frame if voice.vision_mode == 'screen' else voice._capture_camera_frame
            frame = await capture()
            if not frame or voice.vision_mode == 'off':
                continue
            voice.sync_audio_generation()
            async with voice.send_lock.video(generation, budget=budget):
                if voice.vision_mode == 'off':
                    continue
                await session.send_realtime_input(video=types.Blob(data=frame, mime_type='image/jpeg'))
        except VideoFrameDropped:
            # An unsent optional frame is not a cancelled websocket write.
            continue
        except SendStalled as error:
            raise renew_exception('realtime video send timed out or was interrupted; renewal required') from error
        except asyncio.CancelledError:
            raise
        except Exception as error:
            log.warning('Realtime video unavailable: %s', type(error).__name__)
