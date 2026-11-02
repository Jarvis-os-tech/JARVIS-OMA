# Voice regression tests

The unchanged newer test file is copied from `tests/test_core/test_voice_regression_review.py`. It covers reconnect policy, quiet-frame VAD handling and cancellation during playback drain. Its six cases previously failed in the isolated working-status review; copying it does not fix those failures. Original package imports are preserved.
