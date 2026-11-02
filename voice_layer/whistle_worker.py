"""Private JSON-lines Whistle worker. No microphone, tools or network access."""
import base64
import json
import sys

import numpy as np
from needle import Whistle


def main():
    model = Whistle()
    model.transcribe(np.zeros(3200, dtype=np.float32), language='en')
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin.buffer:
        request = json.loads(line)
        pcm = base64.b64decode(request['pcm'], validate=True)
        if len(pcm) > 160000 or len(pcm) % 2:
            raise ValueError('Invalid bounded PCM input')
        samples = np.frombuffer(pcm, dtype='<i2').astype(np.float32) / 32768
        result = model.transcribe(samples, language='en', word_timestamps=True)
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
