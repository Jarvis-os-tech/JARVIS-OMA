#define _POSIX_C_SOURCE 200809L
/* Device callbacks never enter Python, allocate, log, or perform pipe I/O.
 * Rings each have exactly one producer and one consumer. The control/main
 * thread owns stdin/stdout; the PipeWire data thread owns device callbacks.
 * Local protocol v1 is explicitly little endian; no native structs on wire. */
#include <pipewire/pipewire.h>
#include <spa/param/audio/format-utils.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <time.h>
#include <unistd.h>
#include <assert.h>
#include <math.h>
#include "webrtc_gain.h"

#define CAPACITY 262144u
#define MASK (CAPACITY - 1u)
#define MAGIC 0x3141564au
#define MAX_PAYLOAD 32768u
_Static_assert(ATOMIC_LLONG_LOCK_FREE == 2 && ATOMIC_INT_LOCK_FREE == 2 &&
               ATOMIC_BOOL_LOCK_FREE == 2, "native callback atomics must be lock free");
enum { AUDIO=1, FLUSH=2, MUTE=3, COMPLETE=4, STOP=5,
       CAPTURE=101, READY=102, STATS=103 };
struct ring { int16_t data[CAPACITY]; _Atomic uint64_t read, write; };
struct runtime {
    struct pw_thread_loop *loop;
    struct pw_stream *input, *output;
    struct spa_hook in_listener, out_listener;
    struct ring capture, playback;
    _Atomic uint32_t generation;
    _Atomic uint64_t flush_boundary;
    _Atomic bool muted, complete, failed, in_ready, out_ready;
    _Atomic uint64_t capture_end_ns, captured, rendered, starved, dropped, capture_max_ns, render_max_ns;
    _Atomic uint32_t applied_generation, stats_sequence;
    _Atomic bool playing;
    uint32_t render_generation, prebuffer;
    bool primed;
    uint32_t fade_left;
    int16_t last;
};
static uint32_t get32(const uint8_t *p) {
    return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static void put32(uint8_t *p, uint32_t n) {
    for (int i=0;i<4;i++) p[i]=(uint8_t)(n>>(8*i));
}
static void put64(uint8_t *p, uint64_t n) {
    for (int i=0;i<8;i++) p[i]=(uint8_t)(n>>(8*i));
}
static uint64_t now_ns(void) {
    struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec*1000000000u + ts.tv_nsec;
}
static uint64_t available(struct ring *r) {
    uint64_t rd=atomic_load_explicit(&r->read, memory_order_acquire);
    return atomic_load_explicit(&r->write, memory_order_acquire) - rd;
}
static bool push(struct ring *r, const int16_t *data, uint32_t n) {
    uint64_t w=atomic_load_explicit(&r->write,memory_order_relaxed);
    uint64_t rd=atomic_load_explicit(&r->read,memory_order_acquire);
    if(n > CAPACITY-(w-rd)) return false;
    uint32_t first=SPA_MIN(n,CAPACITY-(uint32_t)(w&MASK));
    memcpy(r->data+(w&MASK),data,first*sizeof(int16_t));
    memcpy(r->data,data+first,(n-first)*sizeof(int16_t));
    atomic_store_explicit(&r->write,w+n,memory_order_release);
    return true;
}
static uint32_t pop(struct ring *r, int16_t *data, uint32_t n) {
    uint64_t rd=atomic_load_explicit(&r->read,memory_order_relaxed);
    uint64_t w=atomic_load_explicit(&r->write,memory_order_acquire);
    n=SPA_MIN(n,w-rd);
    uint32_t first=SPA_MIN(n,CAPACITY-(uint32_t)(rd&MASK));
    memcpy(data,r->data+(rd&MASK),first*sizeof(int16_t));
    memcpy(data+first,r->data,(n-first)*sizeof(int16_t));
    atomic_store_explicit(&r->read,rd+n,memory_order_release);
    return n;
}
static void timing(_Atomic uint64_t *maximum, uint64_t begin) {
    uint64_t elapsed=now_ns()-begin;
    uint64_t old=atomic_load_explicit(maximum,memory_order_relaxed);
    /* Each direction owns its own maximum even with separate PW data loops. */
    if(elapsed>old) atomic_store_explicit(maximum,elapsed,memory_order_relaxed);
}
static void capture_process(void *userdata) {
    struct runtime *r=userdata; uint64_t begin=now_ns();
    struct pw_buffer *b=pw_stream_dequeue_buffer(r->input);
    if(!b) return;
    struct spa_data *d=&b->buffer->datas[0];
    if(d->data && d->chunk) {
        uint32_t offset=SPA_MIN(d->chunk->offset,d->maxsize);
        uint32_t size=SPA_MIN(d->chunk->size,d->maxsize-offset);
        uint32_t n=size/sizeof(int16_t);
        if(!push(&r->capture,(int16_t*)((uint8_t*)d->data+offset),n))
            atomic_fetch_add_explicit(&r->dropped,n,memory_order_relaxed);
        atomic_fetch_add_explicit(&r->captured,n,memory_order_relaxed);
        atomic_store_explicit(&r->capture_end_ns,now_ns(),memory_order_release);
    }
    pw_stream_queue_buffer(r->input,b); timing(&r->capture_max_ns,begin);
}
static void render(struct runtime *r, int16_t *out, uint32_t n) {
    atomic_fetch_add_explicit(&r->stats_sequence,1,memory_order_acq_rel);
    uint32_t gen=atomic_load_explicit(&r->generation,memory_order_acquire);
    if(gen!=r->render_generation) {
        uint64_t boundary=atomic_load_explicit(&r->flush_boundary,memory_order_acquire);
        atomic_store_explicit(&r->playback.read,boundary,memory_order_release);
        r->render_generation=gen; r->primed=false;
        atomic_store(&r->rendered,0);
    }
    bool muted=atomic_load_explicit(&r->muted,memory_order_relaxed);
    if(!r->primed && (available(&r->playback)>=r->prebuffer ||
                      atomic_load_explicit(&r->complete,memory_order_acquire))) {
        r->primed=true; r->fade_left=240;
    }
    uint32_t got=0;
    if(!muted && r->primed) got=pop(&r->playback,out,n);
    /* Small bounded ramps prevent hard transitions without Python/heap work. */
    for(uint32_t i=0;i<got;i++) {
        if(r->fade_left) { out[i]=(int16_t)((int)out[i]*(240-r->fade_left)/240); r->fade_left--; }
        r->last=out[i];
    }
    for(uint32_t i=got;i<n;i++) {
        r->last=(int16_t)((int)r->last*15/16); out[i]=r->last;
    }
    if(got<n && r->primed && !muted && !atomic_load(&r->complete)) {
        atomic_fetch_add_explicit(&r->starved,n-got,memory_order_relaxed); r->primed=false;
    }
    if(got<n && atomic_load(&r->complete)) r->primed=false;
    atomic_store_explicit(&r->playing,got>0,memory_order_relaxed);
    atomic_fetch_add_explicit(&r->rendered,got,memory_order_relaxed);
    /* Ack only after the old callback is finished. The producer will not
     * publish new-generation PCM before this, preventing replay/rewind races. */
    atomic_store_explicit(&r->applied_generation,gen,memory_order_release);
    atomic_fetch_add_explicit(&r->stats_sequence,1,memory_order_release);
}
static void playback_process(void *userdata) {
    struct runtime *r=userdata; uint64_t begin=now_ns();
    struct pw_buffer *b=pw_stream_dequeue_buffer(r->output);
    if(!b) return;
    struct spa_data *d=&b->buffer->datas[0];
    if(d->data && d->chunk) {
        uint32_t n=d->maxsize/sizeof(int16_t);
        if(b->requested) n=SPA_MIN(n,b->requested);
        render(r,d->data,n);
        d->chunk->offset=0; d->chunk->stride=sizeof(int16_t); d->chunk->size=n*sizeof(int16_t);
    }
    pw_stream_queue_buffer(r->output,b); timing(&r->render_max_ns,begin);
}
static void input_state(void *data, enum pw_stream_state old, enum pw_stream_state state, const char *error) {
    (void)old; struct runtime *r=data;
    atomic_store(&r->in_ready,state==PW_STREAM_STATE_STREAMING);
    if(state==PW_STREAM_STATE_ERROR || state==PW_STREAM_STATE_UNCONNECTED) {
        atomic_store(&r->failed,true); if(error) fprintf(stderr,"capture: %s\n",error);
    }
}
static void output_state(void *data, enum pw_stream_state old, enum pw_stream_state state, const char *error) {
    (void)old; struct runtime *r=data;
    atomic_store(&r->out_ready,state==PW_STREAM_STATE_STREAMING);
    if(state==PW_STREAM_STATE_ERROR || state==PW_STREAM_STATE_UNCONNECTED) {
        atomic_store(&r->failed,true); if(error) fprintf(stderr,"playback: %s\n",error);
    }
}
static const struct pw_stream_events input_events={PW_VERSION_STREAM_EVENTS,.state_changed=input_state,.process=capture_process};
static const struct pw_stream_events output_events={PW_VERSION_STREAM_EVENTS,.state_changed=output_state,.process=playback_process};
static struct pw_stream *open_stream(struct runtime *r, const char *target, bool input) {
    struct pw_properties *props=pw_properties_new(
        PW_KEY_MEDIA_TYPE,"Audio", PW_KEY_MEDIA_CATEGORY,input?"Capture":"Playback",
        PW_KEY_MEDIA_ROLE,"Communication", PW_KEY_NODE_NAME,input?"jarvis.native.capture":"jarvis.native.playback",
        PW_KEY_TARGET_OBJECT,target, PW_KEY_NODE_DONT_RECONNECT,"true",NULL);
    struct pw_stream *s=pw_stream_new_simple(pw_thread_loop_get_loop(r->loop),
        input?"JARVIS Native Capture":"JARVIS Native Playback",props,input?&input_events:&output_events,r);
    if(!s) return NULL;
    uint8_t buffer[1024]; struct spa_pod_builder builder=SPA_POD_BUILDER_INIT(buffer,sizeof(buffer));
    struct spa_audio_info_raw info={.format=SPA_AUDIO_FORMAT_S16_LE,.rate=input?16000:24000,
                                  .channels=1,.position={SPA_AUDIO_CHANNEL_MONO}};
    const struct spa_pod *params[]={spa_format_audio_raw_build(&builder,SPA_PARAM_EnumFormat,&info)};
    if(pw_stream_connect(s,input?PW_DIRECTION_INPUT:PW_DIRECTION_OUTPUT,PW_ID_ANY,
        PW_STREAM_FLAG_AUTOCONNECT|PW_STREAM_FLAG_MAP_BUFFERS|PW_STREAM_FLAG_RT_PROCESS,
        params,1)<0) { pw_stream_destroy(s); return NULL; }
    return s;
}
static int self_test(void) {
    struct runtime *r=calloc(1,sizeof(*r)); assert(r);
    int16_t in[480],out[480]; for(int i=0;i<480;i++) in[i]=1000;
    r->prebuffer=480;
    assert(push(&r->playback,in,480)); render(r,out,480); assert(out[479]==1000);
    assert(available(&r->playback)==0);
    assert(push(&r->playback,in,480));
    atomic_store(&r->flush_boundary,atomic_load(&r->playback.write)); atomic_store(&r->generation,1);
    render(r,out,480); assert(out[479]==0); assert(available(&r->playback)==0);
    for(unsigned i=0;i<CAPACITY/480+5;i++) { assert(push(&r->capture,in,480)); assert(pop(&r->capture,out,480)==480); assert(out[0]==1000); }
    assert(!push(&r->capture,in,CAPACITY+1));
    atomic_store(&r->complete,true); assert(push(&r->playback,in,100)); render(r,out,480);
    assert(available(&r->playback)==0); assert(out[99]>0);
    free(r); puts("native audio self-test passed"); return 0;
}
int main(int argc,char **argv) {
    if(argc==2 && !strcmp(argv[1],"--self-test")) return self_test();
    if(argc==2 && !strcmp(argv[1],"--self-test-webrtc-gain")) return jarvis_webrtc_gain_self_test();
    if(argc==2 && !strcmp(argv[1],"--capabilities")) {
        printf("{\"webrtc_gain\":%s,\"implementation\":\"webrtc-audio-processing-1\",\"version\":\"%s\"}\n",
               jarvis_webrtc_gain_available()?"true":"false",jarvis_webrtc_gain_version());
        return 0;
    }
    bool webrtc_gain=argc==5 && !strcmp(argv[4],"--webrtc-gain");
    if(argc!=4 && !webrtc_gain) {
        fprintf(stderr,"usage: jarvis-audio SOURCE SINK PREBUFFER_MS [--webrtc-gain]\n"); return 2;
    }
    uint16_t endian=1; if(*(uint8_t*)&endian!=1) return 2;
    signal(SIGPIPE,SIG_IGN);
    struct runtime *r=calloc(1,sizeof(*r)); if(!r) return 2;
    /* Touch ring pages before processing starts, rather than in callbacks. */
    volatile uint8_t *pages=(volatile uint8_t*)r;
    for(size_t i=0;i<sizeof(*r);i+=4096) pages[i]=0;
    r->prebuffer=(uint32_t)strtoul(argv[3],NULL,10)*24;
    if(r->prebuffer>24000) { free(r); return 2; }
    struct jarvis_webrtc_gain *gain=NULL;
    if(webrtc_gain) {
        int status=jarvis_webrtc_gain_create(1,&gain);
        if(status) {
            fprintf(stderr,"WebRTC gain startup failed (%d): %s\n",status,
                    status==JARVIS_WEBRTC_GAIN_UNAVAILABLE?
                    "companion built without webrtc-audio-processing-1 support":
                    "audio processor initialization failed");
            free(r); return 2;
        }
    }
    /* These environment variables must not override our independent targets. */
    unsetenv("PIPEWIRE_NODE"); unsetenv("PIPEWIRE_QUANTUM"); unsetenv("PIPEWIRE_LATENCY");
    pw_init(&argc,&argv); r->loop=pw_thread_loop_new("jarvis-audio",NULL);
    if(!r->loop) { jarvis_webrtc_gain_destroy(gain); pw_deinit(); free(r); return 2; }
    r->input=open_stream(r,argv[1],true); r->output=open_stream(r,argv[2],false);
    if(!r->input || !r->output || pw_thread_loop_start(r->loop)<0) {
        if(r->input) pw_stream_destroy(r->input);
        if(r->output) pw_stream_destroy(r->output);
        pw_thread_loop_destroy(r->loop); pw_deinit();
        jarvis_webrtc_gain_destroy(gain); free(r); return 2;
    }
    fcntl(STDIN_FILENO,F_SETFL,O_NONBLOCK); fcntl(STDOUT_FILENO,F_SETFL,O_NONBLOCK);
    _Alignas(8) uint8_t input[MAX_PAYLOAD+16],output[MAX_PAYLOAD+16]; size_t have=0,pending=0,sent=0;
    uint64_t stats_at=0,unready_since=0; bool ready=false,stop=false; int result=0;
    while(!stop && !atomic_load(&r->failed)) {
        if(ready && (!atomic_load(&r->in_ready) || !atomic_load(&r->out_ready))) {
            if(!unready_since) unready_since=now_ns();
            if(now_ns()-unready_since>2000000000u) {result=1;break;}
        } else unready_since=0;
        struct pollfd fd={.fd=STDIN_FILENO,.events=POLLIN};
        if(poll(&fd,1,5)<0 && errno!=EINTR) {result=1;break;}
        if(fd.revents&(POLLERR|POLLHUP|POLLNVAL)) break;
        if((fd.revents&POLLIN) && have<sizeof(input)) {
            ssize_t got=read(0,input+have,sizeof(input)-have);
            if(got==0) break;
            if(got<0 && errno!=EAGAIN && errno!=EINTR) {result=1;break;}
            if(got>0) have+=(size_t)got;
        }
        while(have>=16) {
                uint32_t magic=get32(input),type=get32(input+4),gen=get32(input+8),len=get32(input+12);
                if(magic!=MAGIC || len>MAX_PAYLOAD || len%2) {result=2;stop=true;break;}
                if(have<len+16) break;
                if(type==AUDIO && gen==atomic_load(&r->generation)) {
                    if(gen!=atomic_load_explicit(&r->applied_generation,memory_order_acquire)) break;
                    atomic_store(&r->complete,false);
                    if(!push(&r->playback,(int16_t*)(input+16),len/2)) {result=3;stop=true;break;}
                } else if(type==FLUSH) {
                    atomic_store(&r->flush_boundary,atomic_load(&r->playback.write));
                    atomic_store_explicit(&r->generation,gen,memory_order_release);
                    atomic_store(&r->complete,false);
                } else if(type==MUTE) atomic_store(&r->muted,gen!=0);
                else if(type==COMPLETE && gen==atomic_load(&r->generation)) atomic_store(&r->complete,true);
                else if(type==STOP) stop=true;
                else if(type!=AUDIO && type!=COMPLETE) {result=2;stop=true;break;}
                memmove(input,input+16+len,have-16-len); have-=16+len;
        }
        if(sent<pending) {
            ssize_t n=write(1,output+sent,pending-sent);
            if(n>0) sent+=(size_t)n;
            else if(n<0 && errno!=EAGAIN && errno!=EINTR) break;
        }
        if(sent<pending) continue;
        pending=sent=0;
        uint32_t type=0,len=0; uint64_t now=now_ns();
        if(!ready && atomic_load(&r->in_ready) && atomic_load(&r->out_ready)) {
            ready=true; type=READY; len=8;
            put32(output+16,pw_stream_get_node_id(r->input)); put32(output+20,pw_stream_get_node_id(r->output));
        } else if(now-stats_at>=100000000u) {
            type=STATS; len=64; stats_at=now;
            uint32_t seq=atomic_load_explicit(&r->stats_sequence,memory_order_acquire);
            uint64_t stats[]={atomic_load(&r->captured),atomic_load(&r->rendered),
                atomic_load(&r->starved),atomic_load(&r->dropped),
                SPA_MAX(atomic_load(&r->capture_max_ns),atomic_load(&r->render_max_ns)),
                available(&r->playback),atomic_load(&r->playing),atomic_load(&r->applied_generation)};
            if((seq&1) || seq!=atomic_load_explicit(&r->stats_sequence,memory_order_acquire)) continue;
            for(int i=0;i<8;i++) put64(output+16+8*i,stats[i]);
        } else if(available(&r->capture)>=320) {
            uint64_t count=available(&r->capture);
            /* Consumer owns read: discard oldest capture beyond 100 ms. */
            if(count>1600) {
                uint64_t rd=atomic_load(&r->capture.read); uint64_t skip=count-1600;
                atomic_store(&r->capture.read,rd+skip); atomic_fetch_add(&r->dropped,skip);
                count=1600;
            }
            uint64_t end=atomic_load_explicit(&r->capture_end_ns,memory_order_acquire);
            put64(output+16,end>count*62500?end-count*62500:0);
            pop(&r->capture,(int16_t*)(output+24),320);
            if(atomic_load(&r->muted)) memset(output+24,0,640);
            else if(gain) {
                /* APM owns internal state and may allocate: run exclusively
                 * here on the control thread, never in PipeWire callbacks. */
                int16_t *samples=(int16_t*)(output+24);
                int status=jarvis_webrtc_gain_process(gain,samples,160);
                if(!status) status=jarvis_webrtc_gain_process(gain,samples+160,160);
                if(status) { fprintf(stderr,"WebRTC gain processing failed: %d\n",status); result=4; break; }
            }
            type=CAPTURE; len=648;
        }
        if(type) {put32(output,MAGIC);put32(output+4,type);put32(output+8,atomic_load(&r->generation));put32(output+12,len);pending=16+len;}
    }
    if(atomic_load(&r->failed)) result=1;
    pw_thread_loop_stop(r->loop); pw_stream_destroy(r->input); pw_stream_destroy(r->output);
    pw_thread_loop_destroy(r->loop); pw_deinit(); jarvis_webrtc_gain_destroy(gain); free(r); return result;
}
