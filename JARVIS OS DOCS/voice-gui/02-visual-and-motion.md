# 02 — Visual and motion system

Status: proposed design tokens, not measured implementation. Values use logical pixels at 100% display scaling.

## Identity

Dark slate surfaces, a soft cyan assistant core, restrained light, readable typography and generous space. The desktop stays unobstructed in compact mode. The expanded canvas gives work a coherent composition with only relevant widgets. The user-supplied reference images establish the material language; the Rose reels establish the shift from central assistant to content-rich workspace. The design excludes an application dock, launcher rail and persistent helper sidebars.

## Tokens

| Token | Proposed value | Usage |
| --- | --- | --- |
| background | `#0A0C12` | Opaque fallback and canvas base |
| surface | `rgba(22,26,35,0.88)` | Default translucent card |
| surface-light | `rgba(30,36,48,0.92)` | Raised controls |
| backdrop | `rgba(10,12,18,0.45)` | Expanded mode only |
| primary-text | `#F2F5FA` | Main text |
| secondary-text | `#B4BFCE` | Supporting text |
| tertiary-text | `#8E9BAD` | Nonessential metadata; validate contrast on final background |
| accent | `#55DDEA` | Focus, listening and selected controls |
| thinking | `#A6B9FF` | Processing accent |
| success | `#83D8B1` | Verified outcomes |
| attention | `#F0C078` | Muted/standby, pending attention |
| danger | `#F193A0` | Failed actions and destructive controls |
| border | `rgba(235,245,255,0.14)` | One-pixel card boundary |
| focus | 2px cyan + 2px offset | All interactive elements |
| spacing | 4, 8, 12, 16, 24, 32, 48 | Shared rhythm |
| radius | 12 control; 20 card; 24 large; capsule for pill | Shared component geometry |
| card padding/gap | 24 / 16 | Standard desktop cards |
| blur | 16px preferred; 0px fallback | Compositor capability dependent |
| shadow | `0 12px 36px rgba(0,0,0,0.24)` | Floating elevation only |

The earlier 65% card alpha is too dependent on wallpaper for reliable reading. Start at 88% with explicit high-contrast/opaque mode. Blur is optional and requires compositor support; QML transparency alone does not blur arbitrary windows. Battery and capture labels require legibility on both light and dark apps.

Use Geist if available in the existing shell, otherwise a system sans-serif. Use a system monospace for time, numeric columns and paths; avoid making all interface text monospace. Preferred sizes: 32px conversation heading, 24px compact conversation text, 20px card heading, 16px body/data, 13px metadata. Body line height 1.5. Essential controls stay at least 14px text with 44×44px interaction targets. No all-caps paragraphs or sub-12px essential labels.

## Spatial rules

Compact pill: top-centre of selected monitor, 32px visible height, 16px radius, minimum 44px interactive activation region. Width adapts to privacy text/time/battery rather than cropping the privacy state. Initial range 300–420px, with accessibility scaling allowed. Core 12px. Unknown battery uses “Battery unavailable” or a concise unknown marker with accessible description, never an invented percentage.

Expanded layout: monitor safe area inset 32–48px, accounting for existing bars and output scaling. Return control stays top-right inside the safe area, above all card content. It has independent ownership from widget renderers and a full text label. Optional input sits at the bottom, above the on-screen keyboard where present.

Conversation anchor: centred on the usable width. Core centre around 144px from safe-area top; first transcript baseline below the core around 230px. These are reference values, not fixed physical coordinates. Keep transcript width at most 720px. Scale down header height when work cards appear.

Workspace anchor: core 40–56px inside the same top header region; task title and short response beside/below it. The transition is triggered by meaningful content entering the workspace, not every audio-state change. A core can speak at its compact workspace size without forcing cards downward.

| Usable width | Canvas arrangement | Limits |
| --- | --- | --- |
| 1600px+ | Up to 3 card columns; a chart may span 2 | Content width capped near 1680px |
| 1100–1599px | 2 columns; detail view may span both | Keep each data card ≥320px |
| 720–1099px | 1 column; compact header | Page/section navigation for comparisons |
| Below 720px or large text | 1 column, minimal core, scrollable content | No forced multi-column tables |

Wide tables scroll within a labelled region or expand to a dedicated detail view. Never shrink data text to fit. First viewport shows 3–6 meaningful cards; additional results appear behind “More results” or a scrollable continuation. Existing cards stay spatially stable during live updates.

## Native windows and canvas placement

Use active output geometry and reserved areas to keep the compact presence and expanded canvas inside the selected monitor's usable area. Task widgets belong inside the voice canvas. A native application handoff returns to compact presence; no helper card is automatically attached to the app and the app is not resized silently.

Window bounds do not reveal every text field or critical target. Avoid claims of perfect screen awareness. Permitted accessibility/screen context can ground a spoken reference, while the user controls opening the canvas. Re-evaluate targets after monitor, scale, focus, layout or user changes.

Expanded canvas appears on one chosen monitor. Other monitors remain usable. A monitor disconnect moves the canvas into the surviving output's safe area, preserving content and exit access. Screen lock hides sensitive content and suppresses spoken private output according to policy. Unlock does not automatically resume speech or pending side effects.

## Motion vocabulary

| State | Geometry/motion | Data source | Reduced-motion form |
| --- | --- | --- | --- |
| Compact/idle | Still 12px core, no endless pulse | Readiness/privacy status | Identical still form |
| Listening | 80–96px soft core; gentle envelope expansion | Fresh measured microphone amplitude | Static ring + labelled input meter |
| Thinking | 64–72px compact flowing shape | Accepted turn + processing stage | Static shape + stage text |
| Executing/verifying | 48–56px restrained core; card stage changes | Task/action events | Static core + text |
| Speaking | Subtle outward envelope/ripples | Measured actual playback | Static ring + labelled playback meter |
| Muted/standby | Subdued still core and explicit label | Acknowledged capture/wake state | Identical |
| Offline/error | Motion settles, recovery text | Connection freshness/error | Identical |

Thinking motion is symbolic activity and is never labelled an audio waveform. If output measurements are unavailable, show “Speaking” with restrained symbolic activity or remain still; do not fabricate measured motion. Use RMS initially; FFT requires a measured feed and a product benefit. A filler ripple follows actual playback and does not claim a completed action.

| Transition | Duration target | Curve |
| --- | --- | --- |
| Hover/focus | 100–140ms | Ease-out |
| State colour/shape | 180–240ms | Ease-in-out |
| Card enter/update | 180–260ms, 8–12px translation | Ease-out; no bouncing data |
| Compact ↔ conversation | 280–360ms | Critically damped feel; no overshoot |
| Conversation ↔ workspace | 240–320ms | Coordinated core/header/card motion |
| Exit | Immediately release input, visual fade ≤180ms | Ease-out |
| Audio envelope | Attack 40–70ms; release 120–180ms | Interpolate newest fresh sample |

Never delay the control operation until an animation ends. Layout animation pauses during selection, drag or editing. Audio continues independently when rendering stalls. Drop intermediate visual samples and catch up to the newest timestamp; never queue old waveform frames.

Skeletons reserve stable space only while a view is being prepared. They use low-contrast blocks with a slow optional opacity sweep, not flashy scanning lights. After about 8 seconds, replace indefinite shimmer with current stage, elapsed time, cancellation where supported and a recovery option. Exact deadlines come from task policy.

## Accessibility and input

Visible focus, Tab/Shift+Tab navigation, Enter/Space activation, labelled buttons and keyboard-operable card menus are required. Announce meaningful state changes once, not every audio sample. Support 200% text scaling, high contrast, reduced transparency and reduced motion. Text/shape accompanies every colour distinction.

No auto-expiration while a user is reading, hovering, selecting text, scrolling, navigating by keyboard or editing a card. Preserve scroll and selections during data refresh by stable entity IDs. Screen-reader support must be checked on the actual Qt/Wayland stack; do not claim it solely from accessibility labels.

The Return control remains legible above all content and never participates in a card's fade/expiry. A failed shader falls back to a simple ring. A rich renderer crash falls back to the native card frame with recovery controls.
