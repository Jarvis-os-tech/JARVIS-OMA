CC ?= cc
CFLAGS ?= -O2 -g -Wall -Wextra -Werror -std=c11
PW_CFLAGS := $(shell pkg-config --cflags libpipewire-0.3)
PW_LIBS := $(shell pkg-config --libs libpipewire-0.3)

jarvis-audio: companion.c
	$(CC) $(CFLAGS) $(PW_CFLAGS) $< -o $@ $(PW_LIBS) -lm -pthread

check: jarvis-audio
	./jarvis-audio --self-test

.PHONY: check
