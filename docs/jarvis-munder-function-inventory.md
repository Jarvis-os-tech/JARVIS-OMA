Warning: truncated output (original token count: 92887)
Total output lines: 3661

# JARVIS and Munder-Difflin function navigation inventory

Generated from inspected source on 20 October 2026. Read with [the integration blueprint](jarvis-munder-integration-blueprint.md).

This is a navigation index, not a claim of exhaustive behavioral review or passing tests. JARVIS symbols are extracted with Python AST. Munder symbols use conservative line patterns for named functions, exported declarations and class-like methods; anonymous callbacks, overloads, arrow functions and dynamically generated hooks may be omitted. Inspect the linked source before modifying a symbol. Renderer files are indexed by module rather than enumerating every React callback.

Line numbers refer to this snapshot and may move. Munder links are pinned; JARVIS links point to the working tree.

## JARVIS implementation symbols

### `audio/__init__.py`

- Package declarations / compatibility exports; inspect module.

### `audio/downstream.py`

- [DownstreamRouter](../audio/downstream.py#L9) — class.
- [DownstreamRouter.__init__](../audio/downstream.py#L19) — function.
- [DownstreamRouter._generation](../audio/downstream.py#L25) — function.
- [DownstreamRouter.feed](../audio/downstream.py#L28) — function.
- [DownstreamRouter.flush](../audio/downstream.py#L46) — function.
- [DownstreamRouter.clear](../audio/downstream.py#L73) — function.

### `audio/echo_cancel.py`

- [pactl](../audio/echo_cancel.py#L12) — async.
- [EchoCancellation](../audio/echo_cancel.py#L27) — class.
- [EchoCancellation.__init__](../audio/echo_cancel.py#L28) — function.
- [EchoCancellation._source_volume](../audio/echo_cancel.py#L38) — async.
- [EchoCancellation._limit_microphone](../audio/echo_cancel.py#L45) — async.
- [EchoCancellation.start](../audio/echo_cancel.py#L59) — async.
- [EchoCancellation.close](../audio/echo_cancel.py#L83) — async.

### `audio/engine.py`

- [StreamLostError](../audio/engine.py#L29) — class.
- [_CaptureQueue](../audio/engine.py#L33) — class.
- [_CaptureQueue.__init__](../audio/engine.py#L36) — function.
- [_CaptureQueue.put_frame](../audio/engine.py#L41) — function.
- [_CaptureQueue.put_nowait](../audio/engine.py#L44) — function.
- [_CaptureQueue.get_nowait](../audio/engine.py#L47) — function.
- [_CaptureQueue.get](../audio/engine.py#L54) — async.
- [NativeAudioEngine](../audio/engine.py#L63) — class.
- [NativeAudioEngine.__init__](../audio/engine.py#L103) — function.
- [NativeAudioEngine.mark_turn_complete](../audio/engine.py#L238) — function.
- [NativeAudioEngine.mark_turn_started](../audio/engine.py#L243) — function.
- [NativeAudioEngine._get_echo_reference](../audio/engine.py#L249) — function.
- [NativeAudioEngine.set_reconnect_buffering](../audio/engine.py#L256) — function.
- [NativeAudioEngine._capture_max_age](../audio/engine.py#L269) — function.
- [NativeAudioEngine._clear_capture](../audio/engine.py#L272) — function.
- [NativeAudioEngine._set_state](../audio/engine.py#L287) — function.
- [NativeAudioEngine._input_callback](../audio/engine.py#L309) — function.
- [NativeAudioEngine._drain_capture](../audio/engine.py#L337) — function.
- [NativeAudioEngine._safe_enqueue_input](../audio/engine.py#L365) — function.
- [NativeAudioEngine._is_voice](../audio/engine.py#L384) — function.
- [NativeAudioEngine._update_voice_gate](../audio/engine.py#L415) — function.
- [NativeAudioEngine._output_callback](../audio/engine.py#L449) — function.
- [NativeAudioEngine.set_output_gain](../audio/engine.py#L675) — function.
- [NativeAudioEngine.enqueue_output](../audio/engine.py#L680) — function.
- [NativeAudioEngine.enqueue_playback](../audio/engine.py#L696) — function.
- [NativeAudioEngine.resolve_aec_devices](../audio/engine.py#L710) — function.
- [NativeAudioEngine._bind_pipewire_streams](../audio/engine.py#L749) — function.
- [NativeAudioEngine.start](../audio/engine.py#L800) — function.
- [NativeAudioEngine.handle_barge_in](../audio/engine.py#L857) — function.
- [NativeAudioEngine.trigger_barge_in](../audio/engine.py#L887) — function.
- [NativeAudioEngine.set_muted](../audio/engine.py#L899) — function.
- [NativeAudioEngine.stop_speaking](../audio/engine.py#L909) — async.
- [NativeAudioEngine.monitor_health](../audio/engine.py#L913) — async.
- [NativeAudioEngine.terminate](../audio/engine.py#L926) — function.

### `connectors/__init__.py`

- Package declarations / compatibility exports; inspect module.

### `connectors/browser.py`

- [open_url](../connectors/browser.py#L11) — function.

### `connectors/credentials.py`

- [read_env](../connectors/credentials.py#L14) — function.
- [get](../connectors/credentials.py#L37) — function.
- [token_path](../connectors/credentials.py#L42) — function.
- [secure_write](../connectors/credentials.py#L46) — function.
- [save_tokens](../connectors/credentials.py#L66) — function.
- [save_env_values](../connectors/credentials.py#L70) — function.

### `connectors/github.py`

- [_NoRedirect](../connectors/github.py#L43) — class.
- [_NoRedirect.redirect_request](../connectors/github.py#L44) — function.
- [_token](../connectors/github.py#L48) — function.
- [_client_credentials](../connectors/github.py#L54) — function.
- [_find_free_oauth_port](../connectors/github.py#L58) — function.
- [github_authorize](../connectors/github.py#L66) — function.
- [_segment](../connectors/github.py#L174) — function.
- [_number](../connectors/github.py#L180) — function.
- [_limit](../connectors/github.py#L186) — function.
- [_repository_path](../connectors/github.py#L192) — function.
- [_url](../connectors/github.py#L204) — function.
- [_request](../connectors/github.py#L210) — function.
- [_gh_request](../connectors/github.py#L228) — async.
- [_fetch](../connectors/github.py#L263) — async.
- [_body](../connectors/github.py#L279) — function.
- [_repo_fields](../connectors/github.py#L285) — function.
- [_issue_fields](../connectors/github.py#L289) — function.
- [_pr_fields](../connectors/github.py#L295) — function.
- [_mapped](../connectors/github.py#L301) — function.
- [_route](../connectors/github.py#L337) — function.
- [_snapshot_ref](../connectors/github.py#L363) — function.
- [_file_score](../connectors/github.py#L369) — function.
- [_find_relevant_files](../connectors/github.py#L390) — async.
- [_read_repository_files](../connectors/github.py#L437) — async.
- [_analyze_repository](../connectors/github.py#L477) — async.
- [dispatch](../connectors/github.py#L513) — async.

### `connectors/google_workspace.py`

- [_NoRedirect](../connectors/google_workspace.py#L55) — class.
- [_NoRedirect.redirect_request](../connectors/google_workspace.py#L56) — function.
- [_load_tokens](../connectors/google_workspace.py#L63) — function.
- [_expiry](../connectors/google_workspace.py#L77) — function.
- [_http_json](../connectors/google_workspace.py#L89) — function.
- [_client_credentials](../connectors/google_workspace.py#L104) — function.
- [_refresh](../connectors/google_workspace.py#L112) — function.
- [_access_token](../connectors/google_workspace.py#L141) — function.
- [authenticated](../connectors/google_workspace.py#L149) — function.
- [_api](../connectors/google_workspace.py#L159) — function.
- [_drive_scope_error](../connectors/google_workspace.py#L173) — function.
- [_google_error](../connectors/google_workspace.py#L185) — function.
- [_drive_file](../connectors/google_workspace.py#L194) — function.
- [drive_search_files](../connectors/google_workspace.py#L200) — function.
- [drive_get_file](../connectors/google_workspace.py#L220) — function.
- [drive_read_text_file](../connectors/google_workspace.py#L233) — function.
- [_api_text](../connectors/google_workspace.py#L249) — function.
- [_document_text](../connectors/google_workspace.py#L267) — function.
- [docs_read_document](../connectors/google_workspace.py#L280) — function.
- [sheets_get_spreadsheet](../connectors/google_workspace.py#L306) — function.
- [_column_number](../connectors/google_workspace.py#L321) — function.
- [sheets_read_range](../connectors/google_workspace.py#L331) — function.
- [_bounded](../connectors/google_workspace.py#L371) — function.
- [_extract_body](../connectors/google_workspace.py#L378) — function.
- [_headers](../connectors/google_workspace.py#L397) — function.
- [gmail_search](../connectors/google_workspace.py#L402) — function.
- [gmail_read](../connectors/google_workspace.py#L420) — function.
- [gmail_create_draft](../connectors/google_workspace.py#L430) — function.
- [gmail_send_draft](../connectors/google_workspace.py#L445) — function.
- [gmail_list_labels](../connectors/google_workspace.py#L451) — function.
- [calendar_list_events](../connectors/google_workspace.py#L457) — function.
- [calendar_get_event](../connectors/google_workspace.py#L471) — function.
- [calendar_create_event](../connectors/google_workspace.py#L479) — function.
- [calendar_list_calendars](../connectors/google_workspace.py#L488) — function.
- [tasks_list_lists](../connectors/google_workspace.py#L494) — function.
- [_task_list_id](../connectors/google_workspace.py#L502) — function.
- [tasks_list_tasks](../connectors/google_workspace.py#L515) — function.
- [tasks_create_task](../connectors/google_workspace.py#L524) — function.
- [tasks_complete_task](../connectors/google_workspace.py#L533) — function.
- [google_connection_status](../connectors/google_workspace.py#L542) — function.
- [_find_free_oauth_port](../connectors/google_workspace.py#L562) — function.
- [google_authorize](../connectors/google_workspace.py#L572) — function.
- [_serve_auth_callbacks](../connectors/google_workspace.py#L722) — function.
- [dispatch](../connectors/google_workspace.py#L758) — async.

### `connectors/internet_search.py`

- [SearchProviderError](../connectors/internet_search.py#L24) — class.
- [SearchProviderError.__init__](../connectors/internet_search.py#L25) — function.
- [brave_available](../connectors/internet_search.py#L30) — function.
- [_get_json](../connectors/internet_search.py#L34) — async.
- [_clean](../connectors/internet_search.py#L63) — function.
- [_public_url](../connectors/internet_search.py#L67) — function.
- [brave_search](../connectors/internet_search.py#L83) — async.
- [encyclopedia_eligible](../connectors/internet_search.py#L121) — function.
- [wikipedia_search](../connectors/internet_search.py#L126) — async.

### `connectors/phone.py`

- [clean_phone_number](../connectors/phone.py#L43) — function.
- [PhoneError](../connectors/phone.py#L61) — class.
- [PhoneConnector](../connectors/phone.py#L65) — class.
- [PhoneConnector.__init__](../connectors/phone.py#L72) — function.
- [PhoneConnector._run_busctl](../connectors/phone.py#L84) — async.
- [PhoneConnector._get_objects](../connectors/phone.py#L103) — async.
- [PhoneConnector.get_gateways](../connectors/phone.py#L125) — async.
- [PhoneConnector.get_calls](../connectors/phone.py#L131) — async.
- [PhoneConnector.dial](../connectors/phone.py#L159) — async.
- [PhoneConnector.answer](../connectors/phone.py#L191) — async.
- [PhoneConnector.hangup](../connectors/phone.py#L214) — async.
- [PhoneConnector.decline](../connectors/phone.py#L235) — async.
- [PhoneConnector.send_tones](../connectors/phone.py#L259) — async.
- [PhoneConnector.set_mute](../connectors/phone.py#L282) — async.
- [PhoneConnector.load_contacts](../connectors/phone.py#L323) — function.
- [PhoneConnector.resolve_contact](../connectors/phone.py#L334) — function.
- [PhoneConnector.resolve_number_to_name](../connectors/phone.py#L374) — function.
- [PhoneConnector.list_contacts](../connectors/phone.py#L392) — function.
- [PhoneConnector.get_recent_calls](../connectors/phone.py#L409) — function.
- [PhoneConnector.get_status](../connectors/phone.py#L424) — async.
- [PhoneConnector.listen_for_calls](../connectors/phone.py#L439) — async.

### `core/__init__.py`

- [__getattr__](../core/__init__.py#L5) — function.

### `core/agent.py`

- [supervise](../core/agent.py#L44) — async.
- [RenewConnection](../core/agent.py#L57) — class.
- [LiveVoice](../core/agent.py#L61) — class.
- [LiveVoice.__init__](../core/agent.py#L62) — function.
- [LiveVoice._start_camera_stream](../core/agent.py#L105) — function.
- [LiveVoice._stop_camera_stream](../core/agent.py#L148) — function.
- [LiveVoice._on_local_barge_in](../core/agent.py#L164) — function.
- [LiveVoice._queue_notice](../core/agent.py#L168) — function.
- [LiveVoice.set_vision_mode](../core/agent.py#L176) — function.
- [LiveVoice._capture_screen_frame](../core/agent.py#L216) — async.
- [LiveVoice._capture_camera_frame](../core/agent.py#L264) — async.
- [LiveVoice.stream_vision](../core/agent.py#L343) — async.
- [LiveVoice.send_notifications](../core/agent.py#L413) — async.
- [LiveVoice._print_transcript](../core/agent.py#L457) — function.
- [LiveVoice._flush_transcript](../core/agent.py#L468) — function.
- [LiveVoice.greet](../core/agent.py#L473) — async.
- [LiveVoice.send_audio](../core/agent.py#L538) — async.
- [LiveVoice.send_input_bar](../core/agent.py#L557) — async.
- [LiveVoice.run_proactive](../core/agent.py#L576) — async.
- [LiveVoice._send_tool_response](../core/agent.py#L636) — async.
- [LiveVoice._send_screen_tool_response](../core/agent.py#L640) — async.
- [LiveVoice.monitor_agents](../core/agent.py#L695) — async.
- [LiveVoice.sync_memory_vault](../core/agent.py#L706) — async.
- [LiveVoice.monitor_phone_calls](../core/agent.py#L714) — async.
- [LiveVoice._execute_tool](../core/agent.py#L757) — async.
- [LiveVoice._tool_done](../core/agent.py#L788) — function.
- [LiveVoice.cancel_tools](../core/agent.py#L796) — async.
- [LiveVoice.handle](../core/agent.py#L805) — async.
- [LiveVoice.receive](../core/agent.py#L917) — async.
- [live_config](../core/agent.py#L932) — function.
- [recover_audio](../core/agent.py#L1193) — async.
- [run](../core/agent.py#L1215) — async.
- [main](../core/agent.py#L1448) — function.

### `core/config.py`

- [AgentConfig](../core/config.py#L30) — class.
- [AudioConfig](../core/config.py#L45) — class.
- [AudioConfig.validate](../core/config.py#L68) — function.
- [AudioConfig.input_frame_bytes](../core/config.py#L107) — function.
- [AudioConfig.output_frame_bytes](../core/config.py#L112) — function.
- [AudioConfig.queue_max_chunks](../core/config.py#L117) — function.
- [VADConfig](../core/config.py#L124) — class.
- [VADConfig.validate](../core/config.py#L133) — function.
- [SkillsConfig](../core/config.py#L151) — class.
- [FilesystemConfig](../core/config.py#L159) — class.
- [MemoryConfig](../core/config.py#L169) — class.
- [MemoryConfig.validate](../core/config.py#L190) — function.
- [Config](../core/config.py#L225) — class.
- [Config.validate](../core/config.py#L235) — function.
- [_load_toml](../core/config.py#L251) — function.
- [_load_json](../core/config.py#L258) — function.
- [_find_config_file](../core/config.py#L269) — function.
- [_merge_section](../core/config.py#L298) — function.
- [_apply_env_overrides](../core/config.py#L309) — function.
- [load_config](../core/config.py#L368) — function.

### `core/desktop_session.py`

- [_is_socket](../core/desktop_session.py#L12) — function.
- [recover_desktop_environment](../core/desktop_session.py#L19) — function.
- [main](../core/desktop_session.py#L59) — function.

### `core/greeting.py`

- [GreetingMemory](../core/greeting.py#L9) — class.
- [GreetingMemory.__init__](../core/greeting.py#L10) — function.
- [GreetingMemory._connect](../core/greeting.py#L19) — function.
- [GreetingMemory.prepare](../core/greeting.py#L24) — function.
- [GreetingMemory.sent](../core/greeting.py#L38) — function.
- [GreetingMemory.record_text](../core/greeting.py#L44) — function.
- [greeting_prompt](../core/greeting.py#L49) — function.

### `core/ipc.py`

- [default_socket_path](../core/ipc.py#L12) — function.
- [JarvisIPCServer](../core/ipc.py#L17) — class.
- [JarvisIPCServer.__init__](../core/ipc.py#L20) — function.
- [JarvisIPCServer.start](../core/ipc.py#L36) — async.
- [JarvisIPCServer._handle_client](../core/ipc.py#L49) — async.
- [JarvisIPCServer.broadcast_state](../core/ipc.py#L107) — function.
- [JarvisIPCServer.close](../core/ipc.py#L118) — async.

### `core/secret_env.py`

- [is_secret_name](../core/secret_env.py#L13) — function.
- [sanitized_subprocess_env](../core/secret_env.py#L17) — function.

### `core/workers.py`

- [WorkerBusyError](../core/workers.py#L10) — class.
- [WorkerClosedError](../core/workers.py#L14) — class.
- [WorkerShutdownError](../core/workers.py#L18) — class.
- [BoundedWorker](../core/workers.py#L22) — class.
- [BoundedWorker.__init__](../core/workers.py#L29) — function.
- [BoundedWorker._get_executor](../core/workers.py#L40) — function.
- [BoundedWorker._finished](../core/workers.py#L45) — function.
- [BoundedWorker.run](../core/workers.py#L49) — async.
- [BoundedWorker.close](../core/workers.py#L72) — async.

### `filesystem/__init__.py`

- Package declarations / compatibility exports; inspect module.

### `filesystem/filesystem.py`

- [FileOperationError](../filesystem/filesystem.py#L28) — class.
- [path_for](../filesystem/filesystem.py#L32) — function.
- [details](../filesystem/filesystem.py#L38) — function.
- [inspect_path](../filesystem/filesystem.py#L54) — function.
- [list_directory](../filesystem/filesystem.py#L71) — function.
- [read_text](../filesystem/filesystem.py#L90) — function.
- [search_files](../filesystem/filesystem.py#L118) — function.
- [search_file_content](../filesystem/filesystem.py#L142) — function.
- [write_text](../filesystem/filesystem.py#L187) — function.
- [append_text](../filesystem/filesystem.py#L210) — function.
- [make_directory](../filesystem/filesystem.py#L228) — function.
- [move_path](../filesystem/filesystem.py#L237) — function.
- [copy_path](../filesystem/filesystem.py#L262) — function.
- [replace_text](../filesystem/filesystem.py#L290) — function.
- [trash_path](../filesystem/filesystem.py#L307) — function.
- [delete_path](../filesystem/filesystem.py#L327) — function.

### `filesystem/task_runner.py`

- [TaskPlanError](../filesystem/task_runner.py#L18) — class.
- [_now](../filesystem/task_runner.py#L22) — function.
- [TaskRunner](../filesystem/task_runner.py#L26) — class.
- [TaskRunner.__init__](../filesystem/task_runner.py#L27) — function.
- [TaskRunner.start](../filesystem/task_runner.py#L34) — function.
- [TaskRunner._run](../filesystem/task_runner.py#L69) — async.
- [TaskRunner._verify_step_ground_truth](../filesystem/task_runner.py#L111) — async.
- [TaskRunner.status](../filesystem/task_runner.py#L139) — function.
- [TaskRunner.list_tasks](../filesystem/task_runner.py#L151) — function.
- [TaskRunner.cancel](../filesystem/task_runner.py#L154) — function.

### `memory/codes-dev/jarvis_memory/__init__.py`

- Package declarations / compatibility exports; inspect module.

### `memory/codes-dev/jarvis_memory/bridge.py`

- [MemoryError](../memory/codes-dev/jarvis_memory/bridge.py#L35) — class.
- [rank_all](../memory/codes-dev/jarvis_memory/bridge.py#L39) — function.
- [JarvisFactStore](../memory/codes-dev/jarvis_memory/bridge.py#L48) — class.
- [JarvisFactStore.forget](../memory/codes-dev/jarvis_memory/bridge.py#L49) — function.
- [OllamaExtractorEngine](../memory/codes-dev/jarvis_memory/bridge.py#L60) — class.
- [OllamaExtractorEngine.__init__](../memory/codes-dev/jarvis_memory/bridge.py#L61) — function.
- [OllamaExtractorEngine.generate](../memory/codes-dev/jarvis_memory/bridge.py#L67) — function.
- [MemoryBridge](../memory/codes-dev/jarvis_memory/bridge.py#L78) — class.
- [MemoryBridge.__init__](../memory/codes-dev/jarvis_memory/bridge.py#L79) — function.
- [MemoryBridge._require](../memory/codes-dev/jarvis_memory/bridge.py#L112) — function.
- [MemoryBridge._mkdir](../memory/codes-dev/jarvis_memory/bridge.py#L116) — function.
- [MemoryBridge.start](../memory/codes-dev/jarvis_memory/bridge.py#L119) — function.
- [MemoryBridge.remember](../memory/codes-dev/jarvis_memory/bridge.py#L139) — function.
- [MemoryBridge.recall](../memory/codes-dev/jarvis_memory/bridge.py#L160) — function.
- [MemoryBridge._semantic_search](../memory/codes-dev/jarvis_memory/bridge.py#L196) — function.
- [MemoryBridge._semantic_document_records](../memory/codes-dev/jarvis_memory/bridge.py#L219) — function.
- [MemoryBridge._semantic_conversation_records](../memory/codes-dev/jarvis_memory/bridge.py#L233) — function.
- [MemoryBridge.recall_history](../memory/codes-dev/jarvis_memory/bridge.py#L251) — function.
- [MemoryBridge.forget](../memory/codes-dev/jarvis_memory/bridge.py#L285) — function.
- [MemoryBridge.clear](../memory/codes-dev/jarvis_memory/bridge.py#L298) — function.
- [MemoryBridge.correct](../memory/codes-dev/jarvis_memory/bridge.py#L306) — function.
- [MemoryBridge.memory_history](../memory/codes-dev/jarvis_memory/bridge.py#L318) — function.
- [MemoryBridge.update_profile](../memory/codes-dev/jarvis_memory/bridge.py#L327) — function.
- [MemoryBridge._document_db](../memory/codes-dev/jarvis_memory/bridge.py#L343) — function.
- [MemoryBridge.index_document](../memory/codes-dev/jarvis_memory/bridge.py#L351) — function.
- [MemoryBridge._search_documents](../memory/codes-dev/jarvis_memory/bridge.py#L373) — function.
- [MemoryBridge.context](../memory/codes-dev/jarvis_memory/bridge.py#L391) — function.
- [MemoryBridge.record_exchange](../memory/codes-dev/jarvis_memory/bridge.py#L431) — function.
- [MemoryBridge.status](../memory/codes-dev/jarvis_memory/bridge.py#L449) — function.
- [MemoryBridge.sync_obsidian](../memory/codes-dev/jarvis_memory/bridge.py#L468) — function.
- [MemoryBridge._sync_obsidian_locked](../memory/codes-dev/jarvis_memory/bridge.py#L472) — function.
- [MemoryBridge.close](../memory/codes-dev/jarvis_memory/bridge.py#L489) — function.

### `memory/codes-dev/jarvis_memory/capture.py`

- [extract_memories](../memory/codes-dev/jarvis_memory/capture.py#L25) — function.

### `memory/codes-dev/jarvis_memory/chunking.py`

- [ChunkConfig](../memory/codes-dev/jarvis_memory/chunking.py#L15) — class.
- [ChunkConfig.__post_init__](../memory/codes-dev/jarvis_memory/chunking.py#L22) — function.
- [ChunkConfig.validate](../memory/codes-dev/jarvis_memory/chunking.py#L25) — function.
- [Chunk](../memory/codes-dev/jarvis_memory/chunking.py#L42) — class.
- [_count_tokens](../memory/codes-dev/jarvis_memory/chunking.py#L52) — function.
- [chunk_text](../memory/codes-dev/jarvis_memory/chunking.py#L57) — function.

### `memory/codes-dev/jarvis_memory/embeddings.py`

- [EmbeddingError](../memory/codes-dev/jarvis_memory/embeddings.py#L20) — class.
- [EmbeddingProvider](../memory/codes-dev/jarvis_memory/embeddings.py#L24) — class.
- [EmbeddingProvider.identity](../memory/codes-dev/jarvis_memory/embeddings.py#L29) — function.
- [EmbeddingProvider.status](../memory/codes-dev/jarvis_memory/embeddings.py#L33) — function.
- [EmbeddingProvider.embed_texts](../memory/codes-dev/jarvis_memory/embeddings.py#L37) — function.
- [_NoRedirect](../memory/codes-dev/jarvis_memory/embeddings.py#L41) — class.
- [_NoRedirect.redirect_request](../memory/codes-dev/jarvis_memory/embeddings.py#L42) — function.
- [_vector](../memory/codes-dev/jarvis_memory/embeddings.py#L47) — function.
- [OllamaEmbeddingProvider](../memory/codes-dev/jarvis_memory/embeddings.py#L61) — class.
- [OllamaEmbeddingProvider.__init__](../memory/codes-dev/jarvis_memory/embeddings.py#L66) — function.
- [OllamaEmbeddingProvider.identity](../memory/codes-dev/jarvis_memory/embeddings.py#L119) — function.
- [OllamaEmbeddingProvider.status](../memory/codes-dev/jarvis_memory/embeddings.py#L122) — function.
- [OllamaEmbeddingProvider.embed_texts](../memory/codes-dev/jarvis_memory/embeddings.py#L127) — function.
- [OllamaEmbeddingProvider._request](../memory/codes-dev/jarvis_memory/embeddings.py#L155) — function.
- [GeminiEmbeddingProvider](../memory/codes-dev/jarvis_memory/embeddings.py#L177) — class.
- [GeminiEmbeddingProvider.__init__](../memory/codes-dev/jarvis_memory/embeddings.py#L180) — function.
- [GeminiEmbeddingProvider.identity](../memory/codes-dev/jarvis_memory/embeddings.py#L213) — function.
- [GeminiEmbeddingProvider.status](../memory/codes-dev/jarvis_memory/embeddings.py#L216) — function.
- [GeminiEmbeddingProvider.embed_texts](../memory/codes-dev/jarvis_memory/embeddings.py#L221) — function.
- [StaticEmbeddingProvider](../memory/codes-dev/jarvis_memory/embeddings.py#L276) — class.
- [StaticEmbeddingProvider.__init__](../memory/codes-dev/jarvis_memory/embeddings.py#L279) — function.
- [StaticEmbeddingProvider.identity](../memory/codes-dev/jarvis_memory/embeddings.py#L286) — function.
- [StaticEmbeddingProvider.status](../memory/codes-dev/jarvis_memory/embeddings.py#L289) — function.
- [StaticEmbeddingProvider.embed_texts](../memory/codes-dev/jarvis_memory/embeddings.py#L293) — function.
- [DeterministicFakeEmbeddingProvider](../memory/codes-dev/jarvis_memory/embeddings.py#L302) — class.
- [DeterministicFakeEmbeddingProvider.__init__](../memory/codes-dev/jarvis_memory/embeddings.py#L305) — function.
- [DeterministicFakeEmbeddingProvider.identity](../memory/codes-dev/jarvis_memory/embeddings.py#L311) — function.
- [DeterministicFakeEmbeddingProvider.status](../memory/codes-dev/jarvis_memory/embeddings.py#L314) — function.
- [DeterministicFakeEmbeddingProvider.embed_texts](../memory/codes-dev/jarvis_memory/embeddings.py#L318) — function.

### `memory/codes-dev/jarvis_memory/events.py`

- [EventType](../memory/codes-dev/jarvis_memory/events.py#L8) — class.
- [Event](../memory/codes-dev/jarvis_memory/events.py#L13) — class.
- [EventBus](../memory/codes-dev/jarvis_memory/events.py#L22) — class.
- [EventBus.subscribe](../memory/codes-dev/jarvis_memory/events.py#L25) — function.
- [EventBus.unsubscribe](../memory/codes-dev/jarvis_memory/events.py#L27) — function.
- [EventBus.publish](../memory/codes-dev/jarvis_memory/events.py#L29) — function.

### `memory/codes-dev/jarvis_memory/extractor.py`

- [FactExtractor](../memory/codes-dev/jarvis_memory/extractor.py#L33) — class.
- [FactExtractor.__init__](../memory/codes-dev/jarvis_memory/extractor.py#L36) — function.
- [FactExtractor.extract](../memory/codes-dev/jarvis_memory/extractor.py#L55) — function.
- [FactExtractor._parse](../memory/codes-dev/jarvis_memory/extractor.py#L95) — function.
- [FactExtractor._coerce_to_list](../memory/codes-dev/jarvis_memory/extractor.py#L117) — function.
- [FactExtractor._clean_fact](../memory/codes-dev/jarvis_memory/extractor.py#L145) — function.

### `memory/codes-dev/jarvis_memory/hybrid.py`

- [_number](../memory/codes-dev/jarvis_memory/hybrid.py#L26) — function.
- [_semantic_score](../memory/codes-dev/jarvis_memory/hybrid.py#L34) — function.
- [_lexical_score](../memory/codes-dev/jarvis_memory/hybrid.py#L40) — function.
- [_text_key](../memory/codes-dev/jarvis_memory/hybrid.py#L45) — function.
- [_candidate_key](../memory/codes-dev/jarvis_memory/hybrid.py#L50) — function.
- [_is_active](../memory/codes-dev/jarvis_memory/hybrid.py#L62) — function.
- [_is_structured](../memory/codes-dev/jarvis_memory/hybrid.py#L67) — function.
- [_lexical_reason](../memory/codes-dev/jarvis_memory/hybrid.py#L73) — function.
- [fuse_results](../memory/codes-dev/jarvis_memory/hybrid.py#L78) — function.

### `memory/codes-dev/jarvis_memory/knowledge.py`

- [KnowledgeStore](../memory/codes-dev/jarvis_memory/knowledge.py#L37) — class.
- [KnowledgeStore.__init__](../memory/codes-dev/jarvis_memory/knowledge.py#L38) — function.
- [KnowledgeStore._connection](../memory/codes-dev/jarvis_memory/knowledge.py#L42) — function.
- [KnowledgeStore._entry](../memory/codes-dev/jarvis_memory/knowledge.py#L80) — function.
- [KnowledgeStore._validate](../memory/codes-dev/jarvis_memory/knowledge.py#L87) — function.
- [KnowledgeStore._record](../memory/codes-dev/jarvis_memory/knowledge.py#L105) — function.
- [KnowledgeStore._insert](../memory/codes-dev/jarvis_memory/knowledge.py#L111) — function.
- [KnowledgeStore.upsert](../memory/codes-dev/jarvis_memory/knowledge.py#L122) — function.
- [KnowledgeStore._supersede](../memory/codes-dev/jarvis_memory/knowledge.py#L143) — function.
- [KnowledgeStore.list](../memory/codes-dev/jarvis_memory/knowledge.py#L149) — function.
- [KnowledgeStore.correct](../memory/codes-dev/jarvis_memory/knowledge.py#L158) — function.
- [KnowledgeStore._id](../memory/codes-dev/jarvis_memory/knowledge.py#L177) — function.
- [KnowledgeStore.history](../memory/codes-dev/jarvis_memory/knowledge.py#L183) — function.
- [KnowledgeStore.forget](../memory/codes-dev/jarvis_memory/knowledge.py#L194) — function.
- [KnowledgeStore.clear](../memory/codes-dev/jarvis_memory/knowledge.py#L206) — function.
- [KnowledgeStore.stats](../memory/codes-dev/jarvis_memory/knowledge.py#L214) — function.

### `memory/codes-dev/jarvis_memory/obsidian.py`

- [digest](../memory/codes-dev/jarvis_memory/obsidian.py#L21) — function.
- [link](../memory/codes-dev/jarvis_memory/obsidian.py#L25) — function.
- [plain](../memory/codes-dev/jarvis_memory/obsidian.py#L29) — function.
- [publish](../memory/codes-dev/jarvis_memory/obsidian.py#L33) — function.
- [_publish](../memory/codes-dev/jarvis_memory/obsidian.py#L43) — function.

### `memory/codes-dev/jarvis_memory/paths.py`

- [get_config_dir](../memory/codes-dev/jarvis_memory/paths.py#L7) — function.

### `memory/codes-dev/jarvis_memory/registry.py`

- [FactStoreRegistry](../memory/codes-dev/jarvis_memory/registry.py#L11) — class.
- [FactStoreRegistry.register](../memory/codes-dev/jarvis_memory/registry.py#L17) — function.
- [FactStoreRegistry.register_value](../memory/codes-dev/jarvis_memory/registry.py#L24) — function.
- [FactStoreRegistry.get](../memory/codes-dev/jarvis_memory/registry.py#L31) — function.
- [FactStoreRegistry.create](../memory/codes-dev/jarvis_memory/registry.py#L38) — function.
- [FactStoreRegistry.items](../memory/codes-dev/jarvis_memory/registry.py#L48) — function.
- [FactStoreRegistry.keys](../memory/codes-dev/jarvis_memory/registry.py#L52) — function.
- [FactStoreRegistry.contains](../memory/codes-dev/jarvis_memory/registry.py#L56) — function.
- [FactStoreRegistry.clear](../memory/codes-dev/jarvis_memory/registry.py#L60) — function.

### `memory/codes-dev/jarvis_memory/retrieval.py`

- [_tokens](../memory/codes-dev/jarvis_memory/retrieval.py#L28) — function.
- [_timestamp](../memory/codes-dev/jarvis_memory/retrieval.py#L34) — function.
- [rank_candidates](../memory/codes-dev/jarvis_memory/retrieval.py#L51) — function.

### `memory/codes-dev/jarvis_memory/scanner.py`

- [InjectionScanResult](../memory/codes-dev/jarvis_memory/scanner.py#L107) — class.
- [InjectionScanner](../memory/codes-dev/jarvis_memory/scanner.py#L115) — class.
- [InjectionScanner.__init__](../memory/codes-dev/jarvis_memory/scanner.py#L126) — function.
- [InjectionScanner.scan](../memory/codes-dev/jarvis_memory/scanner.py#L132) — function.
- [InjectionScanner._scan_python](../memory/codes-dev/jarvis_memory/scanner.py#L136) — function.

### `memory/codes-dev/jarvis_memory/security_types.py`

- [ThreatLevel](../memory/codes-dev/jarvis_memory/security_types.py#L14) — class.
- [RedactionMode](../memory/codes-dev/jarvis_memory/security_types.py#L23) — class.
- [SecurityEventType](../memory/codes-dev/jarvis_memory/security_types.py#L31) — class.
- [ScanFinding](../memory/codes-dev/jarvis_memory/security_types.py#L47) — class.
- [ScanResult](../memory/codes-dev/jarvis_memory/security_types.py#L59) — class.
- [ScanResult.clean](../memory/codes-dev/jarvis_memory/security_types.py#L65) — function.
- [ScanResult.highest_threat](../memory/codes-dev/jarvis_memory/security_types.py#L70) — function.
- [SecurityEvent](../memory/codes-dev/jarvis_memory/security_types.py#L88) — class.

### `memory/codes-dev/jarvis_memory/service.py`

- [MemoryService](../memory/codes-dev/jarvis_memory/service.py#L42) — class.
- [MemoryService.__init__](../memory/codes-dev/jarvis_memory/service.py#L45) — function.
- [MemoryService.start](../memory/codes-dev/jarvis_memory/service.py#L65) — function.
- [MemoryService.stop](../memory/codes-dev/jarvis_memory/service.py#L79) — function.
- [MemoryService.is_running](../memory/codes-dev/jarvis_memory/service.py#L96) — function.
- [MemoryService.submit](../memory/codes-dev/jarvis_memory/service.py#L101) — function.
- [MemoryService._subscribe_events](../memory/codes-dev/jarvis_memory/service.py#L119) — function.
- [MemoryService._unsubscribe_events](../memory/codes-dev/jarvis_memory/service.py#L129) — function.
- [MemoryService._on_completed_exchange](../memory/codes-dev/jarvis_memory/service.py#L139) — function.
- [MemoryService._loop](../memory/codes-dev/jarvis_memory/service.py#L149) — function.
- [MemoryService._scan](../memory/codes-dev/jarvis_memory/service.py#L169) — function.
- [MemoryService._flagged](../memory/codes-dev/jarvis_memory/service.py#L192) — function.
- [MemoryService._blocks_exchange](../memory/codes-dev/jarvis_memory/service.py#L197) — function.
- [MemoryService._process](../memory/codes-dev/jarvis_memory/service.py#L212) — function.
- [MemoryService.list_facts](../memory/codes-dev/jarvis_memory/service.py#L247) — function.
- [MemoryService.clear_facts](../memory/codes-dev/jarvis_memory/service.py#L250) — function.
- [MemoryService.fact_count](../memory/codes-dev/jarvis_memory/service.py#L253) — function.
- [build_memory_service](../memory/codes-dev/jarvis_memory/service.py#L257) — function.
- [_build_scanner](../memory/codes-dev/jarvis_memory/service.py#L297) — function.
- [publish_completed_exchange](../memory/codes-dev/jarvis_memory/service.py#L311) — function.

### `memory/codes-dev/jarvis_memory/session.py`

- [SessionIdentity](../memory/codes-dev/jarvis_memory/session.py#L20) — class.
- [SessionMessage](../memory/codes-dev/jarvis_memory/session.py#L32) — class.
- [Session](../memory/codes-dev/jarvis_memory/session.py#L43) — class.
- [Session.add_message](../memory/codes-dev/jarvis_memory/session.py#L53) — function.
- [SessionStore](../memory/codes-dev/jarvis_memory/session.py#L65) — class.
- [SessionStore.__init__](../memory/codes-dev/jarvis_memory/session.py#L68) — function.
- [SessionStore._create_tables](../memory/codes-dev/jarvis_memory/session.py#L82) — function.
- [SessionStore.get_or_create](../memory/codes-dev/jarvis_memory/session.py#L110) — function.
- [SessionStore._create_session](../memory/codes-dev/jarvis_memory/session.py#L170) — function.
- [SessionStore.save_message](../memory/codes-dev/jarvis_memory/session.py#L199) — function.
- [SessionStore.consolidate](../memory/codes-dev/jarvis_memory/session.py#L237) — function.
- [SessionStore.decay](../memory/codes-dev/jarvis_memory/session.py#L268) — function.
- [SessionStore.link_channel](../memory/codes-dev/jarvis_memory/session.py#L289) — function.
- [SessionStore.list_sessions](../memory/codes-dev/jarvis_memory/session.py#L304) — function.
- [SessionStore._load_messages](../memory/codes-dev/jarvis_memory/session.py#L342) — function.
- [SessionStore.close](../memory/codes-dev/jarvis_memory/session.py#L359) — function.

### `memory/codes-dev/jarvis_memory/store.py`

- [_lock_windows_blocking](../memory/codes-dev/jarvis_memory/store.py#L37) — function.
- [_unlock_windows](../memory/codes-dev/jarvis_memory/store.py#L66) — function.
- [_default_fact_path](../memory/codes-dev/jarvis_memory/store.py#L74) — function.
- [_cross_process_lock](../memory/codes-dev/jarvis_memory/store.py#L94) — function.
- [Fact](../memory/codes-dev/jarvis_memory/store.py#L128) — class.
- [Fact.trusted_for_recall](../memory/codes-dev/jarvis_memory/store.py#L138) — function.
- [FactStore](../memory/codes-dev/jarvis_memory/store.py#L148) — class.
- [FactStore.add](../memory/codes-dev/jarvis_memory/store.py#L152) — function.
- [FactStore.set_trust](../memory/codes-dev/jarvis_memory/store.py#L155) — function.
- [FactStore.add_many](../memory/codes-dev/jarvis_memory/store.py#L160) — function.
- [FactStore.add_with_trust](../memory/codes-dev/jarvis_memory/store.py#L168) — function.
- [FactStore.add_many_with_trust](../memory/codes-dev/jarvis_memory/store.py#L181) — function.
- [FactStore.promote_reviewed](../memory/codes-dev/jarvis_memory/store.py#L193) — function.
- [FactStore.list](../memory/codes-dev/jarvis_memory/store.py#L204) — function.
- [FactStore.clear](../memory/codes-dev/jarvis_memory/store.py#L208) — function.
- [FactStore.count](../memory/codes-dev/jarvis_memory/store.py#L212) — function.
- [LocalFactStore](../memory/codes-dev/jarvis_memory/store.py#L217) — class.
- [LocalFactStore.__init__](../memory/codes-dev/jarvis_memory/store.py#L226) — function.
- [LocalFactStore._load](../memory/codes-dev/jarvis_memory/store.py#L244) — function.
- [LocalFactStore._flush](../memory/codes-dev/jarvis_memory/store.py#L282) — function.
- [LocalFactStore._lock_path](../memory/codes-dev/jarvis_memory/store.py#L307) — function.
- [LocalFactStore._sync_from_disk_locked](../memory/codes-dev/jarvis_memory/store.py#L310) — function.
- [LocalFactStore.add](../memory/codes-dev/jarvis_memory/store.py#L316) — function.
- [LocalFactStore.add_with_trust](../memory/codes-dev/jarvis_memory/store.py#L348) — function.
- [LocalFactStore.set_trust](../memory/codes-dev/jarvis_memory/store.py#L351) — function.
- [LocalFactStore.promote_reviewed](../memory/codes-dev/jarvis_memory/store.py#L363) — function.
- [LocalFactStore.list](../memory/codes-dev/jarvis_memory/store.py#L376) — function.
- [LocalFactStore.clear](../memory/codes-dev/jarvis_memory/store.py#L381) — function.
- [LocalFactStore.count](../memory/codes-dev/jarvis_memory/store.py#L393) — function.
- [LocalFactStore.path](../memory/codes-dev/jarvis_memory/store.py#L399) — function.
- [_ensure_fact_store_backends_registered](../memory/codes-dev/jarvis_memory/store.py#L404) — function.
- [create_fact_store](../memory/codes-dev/jarvis_memory/store.py#L410) — function.
- [load_configured_facts](../memory/codes-dev/jarvis_memory/store.py#L432) — function.

### `memory/codes-dev/jarvis_memory/summaries.py`

- [render_daily_summary](../memory/codes-dev/jarvis_memory/summaries.py#L5) — function.

### `memory/codes-dev/jarvis_memory/types.py`

- [Role](../memory/codes-dev/jarvis_memory/types.py#L7) — class.
- [Message](../memory/codes-dev/jarvis_memory/types.py#L13) — class.

### `memory/codes-dev/jarvis_memory/vector_store.py`

- [VectorStore](../memory/codes-dev/jarvis_memory/vector_store.py#L30) — class.
- [VectorStore.__init__](../memory/codes-dev/jarvis_memory/vector_store.py#L33) — function.
- [VectorStore._identity](../memory/codes-dev/jarvis_memory/vector_store.py#L37) — function.
- [VectorStore._declared_dimension](../memory/codes-dev/jarvis_memory/vector_store.py#L45) — function.
- [VectorStore._vector](../memory/codes-dev/jarvis_memory/vector_store.py#L59) — function.
- [VectorStore._pack](../memory/codes-dev/jarvis_memory/vector_store.py#L73) — function.
- [VectorStore._unpack](../memory/codes-dev/jarvis_memory/vector_store.py#L77) — function.
- [VectorStore._write_connection](../memory/codes-dev/jarvis_memory/vector_store.py#L82) — function.
- [VectorStore.sync](../memory/codes-dev/jarvis_memory/vector_store.py#L95) — function.
- [VectorStore.clear](../memory/codes-dev/jarvis_memory/vector_store.py#L174) — function.
- [VectorStore.search](../memory/codes-dev/jarvis_memory/vector_store.py#L194) — function.

### `orchestration/__init__.py`

- Package declarations / compatibility exports; inspect module.

### `orchestration/agent_orchestrator.py`

- [OrchestrationError](../orchestration/agent_orchestrator.py#L21) — class.
- [now](../orchestration/agent_orchestrator.py#L25) — function.
- [validate_model](../orchestration/agent_orchestrator.py#L29) — function.
- [command_for](../orchestration/agent_orchestrator.py#L37) — function.
- [AgentOrchestrator](../orchestration/agent_orchestrator.py#L62) — class.
- [AgentOrchestrator.__init__](../orchestration/agent_orchestrator.py#L63) — function.
- [AgentOrchestrator._response](../orchestration/agent_orchestrator.py#L81) — function.
- [AgentOrchestrator.discover](../orchestration/agent_orchestrator.py#L85) — function.
- [AgentOrchestrator.delegate](../orchestration/agent_orchestrator.py#L93) — function.
- [AgentOrchestrator._append](../orchestration/agent_orchestrator.py#L133) — function.
- [AgentOrchestrator._read](../orchestration/agent_orchestrator.py#L142) — async.
- [AgentOrchestrator._stop_process](../orchestration/agent_orchestrator.py#L149) — async.
- [AgentOrchestrator._run](../orchestration/agent_orchestrator.py#L168) — async.
- [AgentOrchestrator.status](../orchestration/agent_orchestrator.py#L225) — function.
- [AgentOrchestrator.list_jobs](../orchestration/agent_orchestrator.py#L237) — function.
- [AgentOrchestrator.delegate_team](../orchestration/agent_orchestrator.py#L242) — function.
- [AgentOrchestrator._run_team](../orchestration/agent_orchestrator.py#L294) — async.
- [AgentOrchestrator._delegate_team_assignment](../orchestration/agent_orchestrator.py#L339) — function.
- [AgentOrchestrator.team_status](../orchestration/agent_orchestrator.py#L343) — function.
- [AgentOrchestrator.cancel_team](../orchestration/agent_orchestrator.py#L350) — async.
- [AgentOrchestrator.stop_admission](../orchestration/agent_orchestrator.py#L369) — function.
- [AgentOrchestrator.resume](../orchestration/agent_orchestrator.py#L379) — function.
- [AgentOrchestrator.stop_all](../orchestration/agent_orchestrator.py#L384) — async.
- [AgentOrchestrator._cancel_all](../orchestration/agent_orchestrator.py#L393) — async.
- [AgentOrchestrator.cancel](../orchestration/agent_orchestrator.py#L398) — async.
- [AgentOrchestrator.close](../orchestration/agent_orchestrator.py#L411) — async.

### `orchestration/desktop_execution.py`

- [visible_batch_command](../orchestration/desktop_execution.py#L32) — function.
- [native_task_command](../orchestration/desktop_execution.py#L49) — function.
- [interactive_command](../orchestration/desktop_execution.py#L73) — function.
- [DesktopAgentOrchestrator](../orchestration/desktop_execution.py#L124) — class.
- [DesktopAgentOrchestrator._tmux](../orchestration/desktop_execution.py#L127) — async.
- [DesktopAgentOrchestrator.discover](../orchestration/desktop_execution.py#L143) — function.
- [DesktopAgentOrchestrator.delegate](../orchestration/desktop_execution.py#L159) — function.
- [DesktopAgentOrchestrator._delegate_team_assignment](../orchestration/desktop_execution.py#L188) — function.
- [DesktopAgentOrchestrator._run_team](../orchestration/desktop_execution.py#L200) — async.
- [DesktopAgentOrchestrator._run](../orchestration/desktop_execution.py#L241) — async.
- [DesktopAgentOrchestrator._run_shared_pane](../orchestration/desktop_execution.py#L345) — async.

### `orchestration/evolution.py`

- [EvolutionError](../orchestration/evolution.py#L37) — class.
- [_Stopped](../orchestration/evolution.py#L41) — class.
- [_Stopped.__init__](../orchestration/evolution.py#L42) — function.
- [_safe_path](../orchestration/evolution.py#L46) — function.
- [default_state_dir](../orchestration/evolution.py#L55) — function.
- [verification_command](../orchestration/evolution.py#L59) — function.
- [EvolutionManager](../orchestration/evolution.py#L91) — class.
- [EvolutionManager.__init__](../orchestration/evolution.py#L92) — function.
- [EvolutionManager._load](../orchestration/evolution.py#L119) — function.
- [EvolutionManager._save](../orchestration/evolution.py#L140) — function.
- [EvolutionManager._update](../orchestration/evolution.py#L156) — function.
- [EvolutionManager.status](../orchestration/evolution.py#L160) — function.
- [EvolutionManager.list_jobs](../orchestration/evolution.py#L165) — function.
- [EvolutionManager.start](../orchestration/evolution.py#L170) — async.
- [EvolutionManager._check_cancel](../orchestration/evolution.py#L206) — function.
- [EvolutionManager._stop_process](../orchestration/evolution.py#L213) — async.
- [EvolutionManager._command](../orchestration/evolution.py#L229) — async.
- [EvolutionManager._git](../orchestration/evolution.py#L280) — async.
- [EvolutionManager._snapshot](../orchestration/evolution.py#L288) — async.
- [EvolutionManager._stage](../orchestration/evolution.py#L319) — async.
- [EvolutionManager._diff](../orchestration/evolution.py#L383) — async.
- [EvolutionManager._fingerprint](../orchestration/evolution.py#L389) — async.
- [EvolutionManager._verify](../orchestration/evolution.py#L394) — async.
- [EvolutionManager._run](../orchestration/evolution.py#L413) — async.
- [EvolutionManager.cancel](../orchestration/evolution.py#L458) — async.
- [EvolutionManager.close](../orchestration/evolution.py#L476) — async.

### `orchestration/harness2_adapter.py`

- [_now](../orchestration/harness2_adapter.py#L19) — function.
- [Harness2Adapter](../orchestration/harness2_adapter.py#L23) — class.
- [Harness2Adapter.__init__](../orchestration/harness2_adapter.py#L29) — function.
- [Harness2Adapter.status](../orchestration/harness2_adapter.py#L35) — function.
- [Harness2Adapter._load_guidance](../orchestration/harness2_adapter.py#L47) — function.
- [Harness2Adapter.prepare_prompt](../orchestration/harness2_adapter.py#L62) — function.
- [Harness2Adapter.record_outcome](../orchestration/harness2_adapter.py#L75) — function.

### `orchestration/model_policy.py`

- [apply_model_policy](../orchestration/model_policy.py#L5) — function.

### `orchestration/personas.py`

- [software_assignments](../orchestration/personas.py#L16) — function.

### `proactive/__init__.py`

- Package declarations / compatibility exports; inspect module.

### `proactive/calendar.py`

- [calendar_agenda](../proactive/calendar.py#L5) — function.

### `proactive/control.py`

- [AutonomyState](../proactive/control.py#L20) — class.
- [AutonomyState.can_run](../proactive/control.py#L29) — function.
- [AutonomyControl](../proactive/control.py#L35) — class.
- [AutonomyControl.__init__](../proactive/control.py#L43) — function.
- [AutonomyControl.get_state](../proactive/control.py#L49) — function.
- [AutonomyControl.pause](../proactive/control.py#L59) — function.
- [AutonomyControl.resume](../proactive/control.py#L64) — function.
- [AutonomyControl.stop_all](../proactive/control.py#L69) — function.
- [AutonomyControl._connect](../proactive/control.py#L74) — function.
- [AutonomyControl._initialize](../proactive/control.py#L82) — function.
- [AutonomyControl._set](../proactive/control.py#L99) — function.
- [AutonomyControl._session](../proactive/control.py#L120) — function.
- [AutonomyControl._secure_permissions](../proactive/control.py#L128) — function.

### `proactive/events.py`

- [EventStatus](../proactive/events.py#L20) — class.
- [Event](../proactive/events.py#L28) — class.
- [_now](../proactive/events.py#L39) — function.
- [_payload](../proactive/events.py#L43) — function.
- [EventBus](../proactive/events.py#L56) — class.
- [EventBus.__init__](../proactive/events.py#L59) — function.
- [EventBus._connect](../proactive/events.py#L65) — function.
- [EventBus._session](../proactive/events.py#L78) — function.
- [EventBus._initialize](../proactive/events.py#L86) — function.
- [EventBus._row](../proactive/events.py#L101) — function.
- [EventBus.subscribe](../proactive/events.py#L106) — function.
- [EventBus._validate_type](../proactive/events.py#L123) — function.
- [EventBus.publish](../proactive/events.py#L128) — function.
- [EventBus.get](../proactive/events.py#L150) — function.
- [EventBus.pending](../proactive/events.py#L155) — function.
- [EventBus.claim](../proactive/events.py#L169) — function.
- [EventBus.transition](../proactive/events.py#L192) — function.

### `proactive/ledger.py`

- [ActivityStatus](../proactive/ledger.py#L20) — class.
- [Activity](../proactive/ledger.py#L32) — class.
- [_now](../proactive/ledger.py#L43) — function.
- [ActivityLedger](../proactive/ledger.py#L47) — class.
- [ActivityLedger.__init__](../proactive/ledger.py#L50) — function.
- [ActivityLedger._connect](../proactive/ledger.py#L55) — function.
- [ActivityLedger._session](../proactive/ledger.py#L68) — function.
- [ActivityLedger._initialize](../proactive/ledger.py#L76) — function.
- [ActivityLedger.save_execution](../proactive/ledger.py#L101) — function.
- [ActivityLedger.executions](../proactive/ledger.py#L107) — function.
- [ActivityLedger.execution](../proactive/ledger.py#L114) — function.
- [ActivityLedger._row](../proactive/ledger.py#L121) — function.
- [ActivityLedger.append](../proactive/ledger.py#L126) — function.
- [ActivityLedger.get](../proactive/ledger.py#L154) — function.
- [ActivityLedger.list](../proactive/ledger.py#L159) — function.
- [ActivityLedger.transition](../proactive/ledger.py#L176) — function.

### `proactive/monitor.py`

- [MonitorError](../proactive/monitor.py#L19) — class.
- [_number](../proactive/monitor.py#L23) — function.
- [ProactiveMonitor](../proactive/monitor.py#L32) — class.
- [ProactiveMonitor.__init__](../proactive/monitor.py#L40) — function.
- [ProactiveMonitor.track](../proactive/monitor.py#L43) — function.
- [ProactiveMonitor.update](../proactive/monitor.py#L88) — function.
- [ProactiveMonitor.poll](../proactive/monitor.py#L117) — function.
- [ProactiveMonitor.due_retries](../proactive/monitor.py#L131) — function.
- [ProactiveMonitor.start_retry](../proactive/monitor.py#L137) — function.
- [ProactiveMonitor.get](../proactive/monitor.py#L154) — function.
- [ProactiveMonitor.list_jobs](../proactive/monitor.py#L158) — function.
- [ProactiveMonitor._schedule_retry](../proactive/monitor.py#L162) — function.
- [ProactiveMonitor._get](../proactive/monitor.py#L179) — function.

### `proactive/planner.py`

- [PlannedTask](../proactive/planner.py#L25) — class.
- [TaskPlan](../proactive/planner.py#L37) — class.
- [TaskPlan.as_dict](../proactive/planner.py#L45) — function.
- [_NormalizedEvent](../proactive/planner.py#L69) — class.
- [_stable_id](../proactive/planner.py#L77) — function.
- [_text](../proactive/planner.py#L81) — function.
- [_event_mapping](../proactive/planner.py#L87) — function.
- [_normalize_event](../proactive/planner.py#L97) — function.
- [_select_agent](../proactive/planner.py#L137) — function.
- [AutonomousPlanner](../proactive/planner.py#L167) — class.
- [AutonomousPlanner.__init__](../proactive/planner.py#L170) — function.
- [AutonomousPlanner.plan](../proactive/planner.py#L182) — function.
- [AutonomousPlanner.clear_seen](../proactive/planner.py#L236) — function.
- [plan_event](../proactive/planner.py#L241) — function.

### `proactive/policy.py`

- [ActionEffect](../proactive/policy.py#L16) — class.
- [DecisionStatus](../proactive/policy.py#L24) — class.
- [Action](../proactive/policy.py#L34) — class.
- [PolicyDecision](../proactive/policy.py#L46) — class.
- [PolicyLimits](../proactive/policy.py#L55) — class.
- [PolicyLimits.__post_init__](../proactive/policy.py#L61) — function.
- [ProactivePolicy](../proactive/policy.py#L70) — class.
- [ProactivePolicy.__init__](../proactive/policy.py#L81) — function.
- [ProactivePolicy.paused](../proactive/policy.py#L89) — function.
- [ProactivePolicy.pause](../proactive/policy.py#L92) — function.
- [ProactivePolicy.resume](../proactive/policy.py#L96) — function.
- [ProactivePolicy.classify](../proactive/policy.py#L99) — function.
- [ProactivePolicy.evaluate](../proactive/policy.py#L103) — function.
- [ProactivePolicy._expire](../proactive/policy.py#L151) — function.
- [ProactivePolicy._trim_rate_window](../proactive/policy.py#L160) — function.
- [ProactivePolicy._decision](../proactive/policy.py#L166) — function.

### `proactive/runtime.py`

- [ProactiveRuntime](../proactive/runtime.py#L22) — class.
- [ProactiveRuntime.__init__](../proactive/runtime.py#L23) — function.
- [ProactiveRuntime.enqueue](../proactive/runtime.py#L38) — function.
- [ProactiveRuntime.observe_todos](../proactive/runtime.py#L55) — function.
- [ProactiveRuntime.observe_focus](../proactive/runtime.py#L80) — function.
- [ProactiveRuntime.observe_calendar](../proactive/runtime.py#L105) — function.
- [ProactiveRuntime.observe_reminders](../proactive/runtime.py#L122) — function.
- [ProactiveRuntime.call](../proactive/runtime.py#L140) — async.
- [ProactiveRuntime.close](../proactive/runtime.py#L148) — async.
- [ProactiveRuntime._finish_close](../proactive/runtime.py#L157) — async.
- [ProactiveRuntime.tick](../proactive/runtime.py#L162) — async.
- [ProactiveRuntime._run_tick](../proactive/runtime.py#L174) — async.
- [ProactiveRuntime._tick](../proactive/runtime.py#L178) — async.
- [ProactiveRuntime._reconcile_jobs](../proactive/runtime.py#L267) — async.
- [ProactiveRuntime.stop_all](../proactive/runtime.py#L300) — async.
- [ProactiveRuntime.pause](../proactive/runtime.py#L308) — function.
- [ProactiveRuntime.resume](../proactive/runtime.py#L309) — function.
- [ProactiveRuntime.status](../proactive/runtime.py#L312) — function.

### `proactive/verification.py`

- [validate_checks](../proactive/verification.py#L17) — function.
- [_digest](../proactive/verification.py#L37) — function.
- [verify_files](../proactive/verification.py#L69) — function.

### `skills/__init__.py`

- Package declarations / compatibility exports; inspect module.

### `skills/ground_truth.py`

- [_desktop_env](../skills/ground_truth.py#L21) — function.
- [_run_command](../skills/ground_truth.py#L30) — async.
- [verify_file_state](../skills/ground_truth.py#L44) — async.
- [verify_process_state](../skills/ground_truth.py#L115) — async.
- [verify_window_state](../skills/ground_truth.py#L185) — async.
- [verify_clipboard_state](../skills/ground_truth.py#L261) — async.
- [verify_ground_truth](../skills/ground_truth.py#L304) — async.

### `skills/gui_control.py`

- [GuiControlError](../skills/gui_control.py#L15) — class.
- [GuiControl](../skills/gui_control.py#L19) — class.
- [GuiControl.__init__](../skills/gui_control.py#L20) — function.
- [GuiControl._invoke](../skills/gui_control.py#L31) — async.
- [GuiControl._call](../skills/gui_control.py#L63) — async.
- [GuiControl.list_windows](../skills/gui_control.py#L95) — async.
- [GuiControl.inspect_window](../skills/gui_control.py#L103) — async.
- [GuiControl.click_element](../skills/gui_control.py#L125) — async.
- [GuiControl.observe_desktop](../skills/gui_control.py#L138) — async.
- [GuiControl.click_desktop](../skills/gui_control.py#L157) — async.
- [GuiControl._require_desktop_point](../skills/gui_control.py#L171) — function.
- [GuiControl._query_active_window](../skills/gui_control.py#L179) — async.
- [GuiControl._verify_action_point](../skills/gui_control.py#L196) — async.
- [GuiControl.scroll_desktop](../skills/gui_control.py#L233) — async.
- [GuiControl.type_at](../skills/gui_control.py#L248) — async.
- [GuiControl.press_key_at](../skills/gui_control.py#L263) — async.
- [GuiControl.browser_bind](../skills/gui_control.py#L287) — async.
- [GuiControl.browser_open_isolated](../skills/gui_control.py#L304) — async.
- [GuiControl._check_browser_tab](../skills/gui_control.py#L324) — function.
- [GuiControl.browser_snapshot](../skills/gui_control.py#L328) — async.
- [GuiControl.browser_click](../skills/gui_control.py#L338) — async.
- [GuiControl.browser_type](../skills/gui_control.py#L357) — async.
- [GuiControl.browser_navigate](../skills/gui_control.py#L371) — async.
- [GuiControl.browser_double_click](../skills/gui_control.py#L384) — async.
- [GuiControl.verify_window](../skills/gui_control.py#L400) — async.

### `skills/input_bar.py`

- [TestBar](../skills/input_bar.py#L347) — class.
- [TestBar.__init__](../skills/input_bar.py#L348) — function.
- [TestBar.start](../skills/input_bar.py#L355) — function.
- [TestBar.pop](../skills/input_bar.py#L387) — function.
- [TestBar.close](../skills/input_bar.py#L391) — function.

### `skills/modal_healing.py`

- [DialogType](../skills/modal_healing.py#L76) — class.
- [DesktopDialog](../skills/modal_healing.py#L84) — class.
- [DesktopDialog.__init__](../skills/modal_healing.py#L87) — function.
- [DesktopDialog.to_dict](../skills/modal_healing.py#L109) — function.
- [_desktop_env](../skills/modal_healing.py#L123) — function.
- [_run_command](../skills/modal_healing.py#L132) — async.
- [_query_clients](../skills/modal_healing.py#L146) — async.
- [_query_active_window](../skills/modal_healing.py#L161) — async.
- [classify_dialog](../skills/modal_healing.py#L176) — function.
- [detect_desktop_dialogs](../skills/modal_healing.py#L281) — async.
- [handle_desktop_dialog](../skills/modal_healing.py#L292) — async.
- [heal_window_focus](../skills/modal_healing.py#L406) — async.

### `skills/overlay_client.py`

- [main](../skills/overlay_client.py#L17) — function.

### `skills/skills.py`

- [SkillError](../skills/skills.py#L54) — class.
- [_normalized](../skills/skills.py#L58) — function.
- [DesktopSkills](../skills/skills.py#L62) — class.
- [DesktopSkills.__init__](../skills/skills.py#L389) — function.
- [DesktopSkills._discover_commands](../skills/skills.py#L446) — function.
- [DesktopSkills._exclude_unavailable_skills](../skills/skills.py#L469) — function.
- [DesktopSkills.declarations](../skills/skills.py#L486) — function.
- [DesktopSkills._load_manifests](../skills/skills.py#L494) — function.
- [DesktopSkills._validate_spec](../skills/skills.py#L525) — function.
- [DesktopSkills._validate_schema](../skills/skills.py#L537) — function.
- [DesktopSkills._arguments_match](../skills/skills.py#L601) — function.
- [DesktopSkills.availability](../skills/skills.py#L637) — function.
- [DesktopSkills.capability_context](../skills/skills.py#L641) — function.
- [DesktopSkills._adapter_list_capabilities](../skills/skills.py#L651) — async.
- [DesktopSkills.adapter_availability](../skills/skills.py#L680) — function.
- [DesktopSkills._command](../skills/skills.py#L690) — function.
- [DesktopSkills._run](../skills/skills.py#L696) — async.
- [DesktopSkills._launch](../skills/skills.py#L713) — async.
- [DesktopSkills._applications](../skills/skills.py#L727) — function.
- [DesktopSkills.execute](../skills/skills.py#L758) — async.
- [DesktopSkills._gui_control](../skills/skills.py#L777) — function.
- [DesktopSkills._adapter_gui_list_windows](../skills/skills.py#L785) — async.
- [DesktopSkills._adapter_gui_inspect_window](../skills/skills.py#L788) — async.
- [DesktopSkills._adapter_gui_click_element](../skills/skills.py#L791) — async.
- [DesktopSkills._adapter_gui_observe_desktop](../skills/skills.py#L794) — async.
- [DesktopSkills._adapter_gui_click_desktop](../skills/skills.py#L797) — async.
- [DesktopSkills._adapter_gui_scroll_desktop](../skills/skills.py#L800) — async.
- [DesktopSkills._adapter_gui_type_at](../skills/skills.py#L803) — async.
- [DesktopSkills._adapter_gui_key_at](../skills/skills.py#L806) — async.
- [DesktopSkills._adapter_gui_browser_bind](../skills/skills.py#L809) — async.
- [DesktopSkills._adapter_gui_browser_open_isolated](../skills/skills.py#L812) — async.
- [DesktopSkills._adapter_gui_browser_snapshot](../skills/skills.py#L815) — async.
- [DesktopSkills._adapter_gui_browser_click](../skills/skills.py#L818) — async.
- [DesktopSkills._adapter_gui_browser_type](../skills/skills.py#L821) — async.
- [DesktopSkills._adapter_gui_browser_navigate](../skills/skills.py#L824) — async.
- [DesktopSkills._adapter_gui_browser_double_click](../skills/skills.py#L827) — async.
- [DesktopSkills._adapter_gui_verify_window](../skills/skills.py#L830) — async.
- [DesktopSkills.gui_visual_delivery](../skills/skills.py#L833) — function.
- [DesktopSkills._valid_task_step](../skills/skills.py#L837) — function.
- [DesktopSkills._adapter_list_system_agents](../skills/skills.py#L841) — async.
- [DesktopSkills._adapter_delegate_agent](../skills/skills.py#L844) — async.
- [DesktopSkills._with_shared_memory](../skills/skills.py#L858) — async.
- [DesktopSkills._adapter_delegate_team](../skills/skills.py#L870) — async.
- [DesktopSkills._adapter_start_agent_goal](../skills/skills.py#L881) — async.
- [DesktopSkills._adapter_check_agent_team](../skills/skills.py#L894) — async.
- [DesktopSkills._adapter_cancel_agent_team](../skills/skills.py#L900) — async.
- [DesktopSkills._adapter_check_agent_job](../skills/skills.py#L906) — async.
- [DesktopSkills._adapter_list_agent_jobs](../skills/skills.py#L912) — async.
- [DesktopSkills._adapter_cancel_agent_job](../skills/skills.py#L915) — async.
- [DesktopSkills._adapter_type_text](../skills/skills.py#L921) — async.
- [DesktopSkills.evolution](../skills/skills.py#L928) — function.
- [DesktopSkills._adapter_start_development](../skills/skills.py#L935) — async.
- [DesktopSkills._adapter_request_capability](../skills/skills.py#L941) — async.
- [DesktopSkills._adapter_development_status](../skills/skills.py#L955) — async.
- [DesktopSkills._adapter_list_development_jobs](../skills/skills.py#L973) — async.
- [DesktopSkills._adapter_cancel_development](../skills/skills.py#L980) — async.
- [DesktopSkills._google](../skills/skills.py#L986) — async.
- [DesktopSkills._adapter_google_gmail_search](../skills/skills.py#L996) — async.
- [DesktopSkills._adapter_google_gmail_read](../skills/skills.py#L999) — async.
- [DesktopSkills._adapter_google_gmail_create_draft](../skills/skills.py#L1002) — async.
- [DesktopSkills._adapter_google_gmail_send_draft](../skills/skills.py#L1005) — async.
- [DesktopSkills._adapter_google_gmail_list_labels](../skills/skills.py#L1008) — async.
- [DesktopSkills._adapter_google_calendar_list_events](../skills/skills.py#L1011) — async.
- [DesktopSkills._adapter_google_calendar_get_event](../skills/skills.py#L1014) — async.
- [DesktopSkills._adapter_google_calendar_create_event](../skills/skills.py#L1017) — async.
- [DesktopSkills._adapter_google_calendar_list_calendars](../skills/skills.py#L1027) — async.
- [DesktopSkills._adapter_google_tasks_list_lists](../skills/skills.py#L1030) — async.
- [DesktopSkills._adapter_google_tasks_list_tasks](../skills/skills.py#L1033) — async.
- [DesktopSkills._adapter_google_tasks_create_task](../skills/skills.py#L1036) — async.
- [DesktopSkills._adapter_google_tasks_complete_task](../skills/skills.py#L1039) — async.
- [DesktopSkills._adapter_google_authorize](../skills/skills.py#L1042) — async.
- [DesktopSkills._adapter_google_connection_status](../skills/skills.py#L1045) — async.
- [DesktopSkills._adapter_google_drive_search_files](../skills/skills.py#L1048) — async.
- [DesktopSkills._adapter_google_drive_get_file](../skills/skills.py#L1051) — async.
- [DesktopSkills._adapter_google_drive_read_text_file](../skills/skills.py#L1054) — async.
- [DesktopSkills._adapter_google_docs_read_document](../skills/skills.py#L1057) — async.
- [DesktopSkills._adapter_google_sheets_get_spreadsheet](../skills/skills.py#L1060) — async.
- [DesktopSkills._adapter_google_sheets_read_range](../skills/skills.py#L1063) — async.
- [DesktopSkills._adapter_github_connection_status](../skills/skills.py#L1066) — async.
- [DesktopSkills._adapter_github_authorize](../skills/skills.py#L1069) — async.
- [DesktopSkills._adapter_github_list_repositories](../skills/skills.py#L1072) — async.
- [DesktopSkills._adapter_github_get_repository](../skills/skills.py#L1075) — async.
- [DesktopSkills._adapter_github_list_repository_files](../skills/skills.py#L1078) — async.
- [DesktopSkills._adapter_github_read_repository_file](../skills/skills.py#L1082) — async.
- [DesktopSkills._adapter_github_find_relevant_files](../skills/skills.py#L1086) — async.
- [DesktopSkills._adapter_github_read_repository_files](../skills/skills.py#L1091) — async.
- [DesktopSkills._adapter_github_analyze_repository](../skills/skills.py#L1095) — async.
- [DesktopSkills._adapter_github_list_issues](../skills/skills.py#L1099) — async.
- [DesktopSkills._adapter_github_get_issue](../skills/skills.py#L1103) — async.
- [DesktopSkills._adapter_github_list_pull_requests](../skills/skills.py#L1106) — async.
- [DesktopSkills._adapter_github_get_pull_request](../skills/skills.py#L1110) — async.
- [DesktopSkills._adapter_press_key](../skills/skills.py#L1113) — async.
- [DesktopSkills._adapter_list_desktop_commands](../skills/skills.py#L1119) — async.
- [DesktopSkills._adapter_execute_desktop_command](../skills/skills.py#L1122) — async.
- [DesktopSkills._adapter_list_bar_panels](../skills/skills.py#L1125) — async.
- [DesktopSkills._adapter_open_bar_panel](../skills/skills.py#L1128) — async.
- [DesktopSkills._adapter_close_bar_panel](../skills/skills.py#L1131) — async.
- [DesktopSkills._adapter_set_volume](../skills/skills.py#L1134) — async.
- [DesktopSkills._adapter_control_microphone](../skills/skills.py#L1142) — async.
- [DesktopSkills._adapter_set_brightness](../skills/skills.py#L1148) — async.
- [DesktopSkills._adapter_control_night_light](../skills/skills.py#L1154) — async.
- [DesktopSkills._adapter_control_notifications](../skills/skills.py#L1160) — async.
- [DesktopSkills._adapter_control_theme](../skills/skills.py#L1166) — async.
- [DesktopSkills._adapter_open_control_panel](../skills/skills.py#L1172) — async.
- [DesktopSkills._adapter_move_window_workspace](../skills/skills.py#L1178) — async.
- [DesktopSkills._adapter_detect_desktop_dialogs](../skills/skills.py#L1181) — async.
- [DesktopSkills._adapter_handle_desktop_dialog](../skills/skills.py#L1185) — async.
- [DesktopSkills._adapter_heal_window_focus](../skills/skills.py#L1191) — async.
- [DesktopSkills._adapter_verify_ground_truth](../skills/skills.py#L1197) — async.
- [DesktopSkills.close_agent_jobs](../skills/skills.py#L1205) — async.
- [DesktopSkills._adapter_open_input_bar](../skills/skills.py#L1222) — async.
- [DesktopSkills._adapter_close_input_bar](../skills/skills.py#L1239) — async.
- [DesktopSkills._adapter_proactive_task](../skills/skills.py#L1258) — async.
- [DesktopSkills._adapter_proactive_status](../skills/skills.py#L1263) — async.
- [DesktopSkills._adapter_proactive_pause](../skills/skills.py#L1267) — async.
- [DesktopSkills._adapter_proactive_resume](../skills/skills.py#L1273) — async.
- [DesktopSkills._adapter_proactive_stop](../skills/skills.py#L1277) — async.
- [DesktopSkills._cancel_active_development](../skills/skills.py#L1283) — async.
- [DesktopSkills.memory](../skills/skills.py#L1289) — function.
- [DesktopSkills.proactive](../skills/skills.py#L1295) — function.
- [DesktopSkills.memory_context](../skills/skills.py#L1302) — function.
- [DesktopSkills.memory_call](../skills/skills.py#L1309) — async.
- [DesktopSkills.queue_memory_exchange](../skills/skills.py#L1314) — function.
- [DesktopSkills.queue_memory_job](../skills/skills.py#L1319) — function.
- [DesktopSkills.get_proactive](../skills/skills.py#L1336) — async.
- [DesktopSkills._memory_operation](../skills/skills.py#L1339) — async.
- [DesktopSkills._adapter_remember_memory](../skills/skills.py#L1345) — async.
- [DesktopSkills._adapter_recall_memory](../skills/skills.py#L1348) — async.
- [DesktopSkills._adapter_forget_memory](../skills/skills.py#L1351) — async.
- [DesktopSkills._adapter_clear_memory](../skills/skills.py#L1354) — async.
- [DesktopSkills._adapter_update_memory_profile](../skills/skills.py#L1357) — async.
- [DesktopSkills._adapter_index_memory_document](../skills/skills.py#L1360) — async.
- [DesktopSkills._adapter_memory_status](../skills/skills.py#L1363) — async.
- [DesktopSkills._adapter_sync_memory_vault](../skills/skills.py#L1366) — async.
- [DesktopSkills._adapter_correct_memory](../skills/skills.py#L1369) — async.
- [DesktopSkills._adapter_memory_history](../skills/skills.py#L1372) — async.
- [DesktopSkills.agent_job_events](../skills/skills.py#L1376) — function.
- [DesktopSkills._adapter_start_task](../skills/skills.py#L1379) — async.
- [DesktopSkills._adapter_task_status](../skills/skills.py#L1385) — async.
- [DesktopSkills._adapter_list_tasks](../skills/skills.py#L1391) — async.
- [DesktopSkills._adapter_cancel_task](../skills/skills.py#L1394) — async.
- [DesktopSkills._file_operation](../skills/skills.py#L1400) — async.
- [DesktopSkills._adapter_list_files](../skills/skills.py#L1406) — async.
- [DesktopSkills._adapter_read_file](../skills/skills.py#L1410) — async.
- [DesktopSkills._adapter_search_files](../skills/skills.py#L1413) — async.
- [DesktopSkills._adapter_search_file_content](../skills/skills.py#L1417) — async.
- [DesktopSkills._adapter_write_file](../skills/skills.py#L1421) — async.
- [DesktopSkills._adapter_append_file](../skills/skills.py#L1424) — async.
- [DesktopSkills._adapter_make_directory](../skills/skills.py#L1427) — async.
- [DesktopSkills._adapter_move_path](../skills/skills.py#L1430) — async.
- [DesktopSkills._adapter_copy_path](../skills/skills.py#L1433) — async.
- [DesktopSkills._adapter_trash_path](../skills/skills.py#L1436) — async.
- [DesktopSkills._adapter_delete_path](../skills/skills.py#L1439) — async.
- [DesktopSkills._adapter_inspect_path](../skills/skills.py#L1442) — async.
- [DesktopSkills._adapter_edit_file](../skills/skills.py#L1445) — async.
- [DesktopSkills._adapter_list_applications](../skills/skills.py#L1450) — async.
- [DesktopSkills._adapter_open_application](../skills/skills.py#L1454) — async.
- [DesktopSkills._adapter_internet_search](../skills/skills.py#L1480) — async.
- [DesktopSkills._adapter_open_website](../skills/skills.py#L1574) — async.
- [DesktopSkills._adapter_adjust_volume](../skills/skills.py#L1593) — async.
- [DesktopSkills._adapter_adjust_brightness](../skills/skills.py#L1607) — async.
- [DesktopSkills._adapter_switch_workspace](../skills/skills.py#L1620) — async.
- [DesktopSkills._adapter_show_notification](../skills/skills.py#L1638) — async.
- [DesktopSkills._adapter_create_reminder](../skills/skills.py#L1648) — async.
- [DesktopSkills._adapter_list_reminders](../skills/skills.py#L1657) — async.
- [DesktopSkills._adapter_clear_reminders](../skills/skills.py#L1668) — async.
- [DesktopSkills._adapter_cancel_reminder](../skills/skills.py#L1673) — async.
- [DesktopSkills._todo_path](../skills/skills.py#L1688) — function.
- [DesktopSkills._read_todos](../skills/skills.py#L1691) — function.
- [DesktopSkills._create_todo](../skills/skills.py#L1702) — function.
- [DesktopSkills._list_todos](../skills/skills.py#L1721) — function.
- [DesktopSkills._notify_quickshell_todos](../skills/skills.py#L1732) — function.
- [DesktopSkills._write_todos](../skills/skills.py#L1735) — function.
- [DesktopSkills._find_todo](../skills/skills.py#L1745) — function.
- [DesktopSkills._update_todo](../skills/skills.py#L1756) — function.
- [DesktopSkills._complete_todo](../skills/skills.py#L1770) — function.
- [DesktopSkills._delete_todo](../skills/skills.py#L1777) — function.
- [DesktopSkills._clear_completed_todos](../skills/skills.py#L1783) — function.
- [DesktopSkills._move_todo](../skills/skills.py#L1789) — function.
- [DesktopSkills._todo_operation](../skills/skills.py#L1800) — async.
- [DesktopSkills._adapter_create_todo](../skills/skills.py#L1806) — async.
- [DesktopSkills._adapter_list_todos](../skills/skills.py#L1809) — async.
- [DesktopSkills._adapter_update_todo](../skills/skills.py#L1812) — async.
- [DesktopSkills._adapter_complete_todo](../skills/skills.py#L1815) — async.
- [DesktopSkills._adapter_delete_todo](../skills/skills.py#L1818) — async.
- [DesktopSkills._adapter_clear_completed_todos](../skills/skills.py#L1821) — async.
- [DesktopSkills._adapter_move_todo](../skills/skills.py#L1824) — async.
- [DesktopSkills._adapter_get_desktop_context](../skills/skills.py#L1827) — async.
- [DesktopSkills._adapter_inspect_screen](../skills/skills.py#L1955) — async.
- [DesktopSkills._adapter_control_vision_mode](../skills/skills.py#L2015) — async.
- [DesktopSkills._adapter_capture_camera_frame](../skills/skills.py#L2048) — async.
- [DesktopSkills._adapter_check_vision_hardware](../skills/skills.py#L2083) — async.
- [DesktopSkills._adapter_list_windows](../skills/skills.py#L2101) — async.
- [DesktopSkills._adapter_focus_window](../skills/skills.py#L2133) — async.
- [DesktopSkills._adapter_list_workspaces](../skills/skills.py#L2202) — async.
- [DesktopSkills._adapter_get_system_resources](../skills/skills.py#L2230) — async.
- [DesktopSkills._adapter_get_system_information](../skills/skills.py#L2234) — async.
- [DesktopSkills._adapter_get_system_control_status](../skills/skills.py#L2238) — async.
- [DesktopSkills._adapter_system_control_extension](../skills/skills.py#L2241) — async.
- [DesktopSkills._adapter_lock_screen](../skills/skills.py#L2247) — async.
- [DesktopSkills._adapter_take_screenshot](../skills/skills.py#L2252) — async.
- [DesktopSkills._adapter_manage_window](../skills/skills.py#L2278) — async.
- [DesktopSkills._adapter_control_power](../skills/skills.py#L2306) — async.
- [DesktopSkills._adapter_control_wifi](../skills/skills.py#L2315) — async.
- [DesktopSkills._adapter_control_bluetooth](../skills/skills.py#L2324) — async.
- [DesktopSkills._adapter_read_clipboard](../skills/skills.py#L2333) — async.
- [DesktopSkills._adapter_write_clipboard](../skills/skills.py#L2342) — async.
- [DesktopSkills.phone](../skills/skills.py#L2375) — function.
- [DesktopSkills._adapter_phone_call](../skills/skills.py#L2381) — async.
- [DesktopSkills._adapter_phone_answer](../skills/skills.py#L2387) — async.
- [DesktopSkills._adapter_phone_hangup](../skills/skills.py#L2393) — async.
- [DesktopSkills._adapter_phone_decline](../skills/skills.py#L2399) — async.
- [DesktopSkills._adapter_phone_mute](../skills/skills.py#L2405) — async.
- [DesktopSkills._adapter_phone_send_tones](../skills/skills.py#L2411) — async.
- [DesktopSkills._adapter_phone_list_contacts](../skills/skills.py#L2417) — async.
- [DesktopSkills._adapter_phone_recent_calls](../skills/skills.py#L2426) — async.
- [DesktopSkills._adapter_phone_status](../skills/skills.py#L2435) — async.
- [DesktopSkills._adapter_phone_open](../skills/skills.py#L2441) — async.
- [DesktopSkills._adapter_phone_close](../skills/skills.py#L2447) — async.

### `skills/system_control.py`

- [_desktop_env](../skills/system_control.py#L39) — function.
- [_run_command](../skills/system_control.py#L47) — async.
- [_query_active_window](../skills/system_control.py#L84) — async.
- [_query_open_windows](../skills/system_control.py#L100) — async.
- [_clean_window_target](../skills/system_control.py#L116) — function.
- [_focus_window_target](../skills/system_control.py#L141) — async.
- [type_text](../skills/system_control.py#L296) — async.
- [press_key](../skills/system_control.py#L375) — async.
- [_get_bindings](../skills/system_control.py#L427) — async.
- [list_desktop_commands](../skills/system_control.py#L486) — async.
- [execute_desktop_command](../skills/system_control.py#L510) — async.
- [list_bar_panels](../skills/system_control.py#L545) — async.
- [open_bar_panel](../skills/system_control.py#L573) — async.
- [close_bar_panel](../skills/system_control.py#L588) — async.
- [find_control_panel_plugin](../skills/system_control.py#L603) — function.
- [get_control_panel_script](../skills/system_control.py#L615) — function.
- [_observation_error](../skills/system_control.py#L625) — function.
- [_control_exec](../skills/system_control.py#L629) — async.
- [_verified_result](../skills/system_control.py#L648) — function.
- [_audio_state](../skills/system_control.py#L657) — async.
- [_set_audio](../skills/system_control.py#L670) — async.
- [set_volume](../skills/system_control.py#L715) — async.
- [control_microphone](../skills/system_control.py#L720) — async.
- [_brightness_state](../skills/system_control.py#L727) — async.
- [set_brightness](../skills/system_control.py#L745) — async.
- [_nightlight_state](../skills/system_control.py#L776) — async.
- [control_night_light](../skills/system_control.py#L790) — async.
- [_wifi_state](../skills/system_control.py#L823) — async.
- [control_wifi](../skills/system_control.py#L836) — async.
- [_bluetooth_state](../skills/system_control.py#L885) — async.
- [control_bluetooth](../skills/system_control.py#L899) — async.
- [control_power](../skills/system_control.py#L925) — async.
- [_dnd_state](../skills/system_control.py#L982) — async.
- [_notification_history](../skills/system_control.py#L995) — async.
- [control_notifications](../skills/system_control.py#L1030) — async.
- [control_theme](../skills/system_control.py#L1063) — async.
- [get_control_status](../skills/system_control.py#L1115) — async.
- [open_control_panel](../skills/system_control.py#L1159) — async.
- [manage_window](../skills/system_control.py#L1203) — async.
- [switch_workspace](../skills/system_control.py#L1235) — async.
- [lock_screen](../skills/system_control.py#L1261) — async.
- [take_screenshot](../skills/system_control.py#L1272) — async.
- [read_clipboard](../skills/system_control.py#L1307) — async.
- [write_clipboard](../skills/system_control.py#L1318) — async.
- [move_window_to_workspace](../skills/system_control.py#L1348) — async.
- [detect_desktop_dialogs](../skills/system_control.py#L1368) — async.
- [handle_desktop_dialog](../skills/system_control.py#L1374) — async.
- [heal_window_focus](../skills/system_control.py#L1380) — async.
- [verify_ground_truth](../skills/system_control.py#L1386) — async.

### `skills/system_extensions.py`

- [_run](../skills/system_extensions.py#L19) — async.
- [_result](../skills/system_extensions.py#L52) — function.
- [_audio](../skills/system_extensions.py#L57) — async.
- [_service](../skills/system_extensions.py#L93) — async.
- [_media](../skills/system_extensions.py#L128) — async.
- [system_control_extension](../skills/system_extensions.py#L159) — async.

### `skills/system_information.py`

- [_command](../skills/system_information.py#L20) — async.
- [SystemInformation](../skills/system_information.py#L54) — class.
- [SystemInformation.__init__](../skills/system_information.py#L55) — function.
- [SystemInformation._read](../skills/system_information.py#L64) — function.
- [SystemInformation._run](../skills/system_information.py#L71) — async.
- [SystemInformation.get_system_information](../skills/system_information.py#L74) — async.
- [SystemInformation._local](../skills/system_information.py#L133) — function.
- [SystemInformation._external](../skills/system_information.py#L241) — async.
- [get_system_information](../skills/system_information.py#L300) — async.

## JARVIS voice tool declarations

These names come from the canonical `skill_manifests/` directory. A declaration is not proof that its dependency or authentication is available.

### `skill_manifests/agent-orchestration.json`

- `start_agent_goal` → `agents.start_goal`.
- `list_system_agents` → `agents.list`.
- `delegate_agent` → `agents.delegate`.
- `delegate_team` → `agents.delegate_team`.
- `check_agent_team` → `agents.team_status`.
- `cancel_agent_team` → `agents.cancel_team`.
- `check_agent_job` → `agents.status`.
- `list_agent_jobs` → `agents.jobs`.
- `cancel_agent_job` → `agents.cancel`.

### `skill_manifests/capabilities.json`

- `list_capabilities` → `capabilities.list`.

### `skill_manifests/desktop-awareness.json`

- `inspect_screen` → `screen.inspect`.
- `list_windows` → `window.list`.
- `focus_window` → `window.focus`.
- `list_workspaces` → `workspace.list`.
- `get_system_resources` → `system.resources`.

### `skill_manifests/development.json`

- `request_capability` → `evolution.request`.
- `start_development` → `evolution.start`.
- `development_status` → `evolution.status`.
- `list_development_jobs` → `evolution.list`.
- `cancel_development` → `evolution.cancel`.

### `skill_manifests/filesystem.json`

- `list_files` → `filesystem.list`.
- `read_file` → `filesystem.read`.
- `write_file` → `filesystem.write`.
- `append_file` → `filesystem.append`.
- `edit_file` → `filesystem.edit`.
- `make_directory` → `filesystem.mkdir`.
- `move_path` → `filesystem.move`.
- `copy_path` → `filesystem.copy`.
- `trash_path` → `filesystem.trash`.
- `delete_path` → `filesystem.delete`.
- `inspect_file` → `filesystem.info`.
- `search_files` → `filesystem.search`.
- `search_file_content` → `filesystem.grep`.

### `skill_manifests/github.json`

- `github_authorize` → `github.authorize`.
- `github_connection_status` → `github.status`.
- `github_list_repositories` → `github.repositories`.
- `github_get_repository` → `github.repository`.
- `github_list_repository_files` → `github.files`.
- `github_read_repository_file` → `github.file`.
- `github_analyze_repository` → `github.analyze_repository`.
- `github_find_relevant_files` → `github.find_relevant_files`.
- `github_read_repository_files` → `github.read_repository_files`.
- `github_list_issues` → `github.issues`.
- `github_get_issue` → `github.issue`.
- `github_list_pull_requests` → `github.pulls`.
- `github_get_pull_request` → `github.pull`.

### `skill_manifests/google-workspace.json`

- `gmail_search` → `google.gmail_search`.
- `gmail_read` → `google.gmail_read`.
- `gmail_create_draft` → `google.gmail_create_draft`.
- `gmail_send_draft` → `google.gmail_send_draft`.
- `gmail_list_labels` → `google.gmail_list_labels`.
- `calendar_list_events` → `google.calendar_list_events`.
- `calendar_get_event` → `google.calendar_get_event`.
- `calendar_create_event` → `google.calendar_create_event`.
- `calendar_list_calendars` → `google.calendar_list_calendars`.
- `tasks_list_lists` → `google.tasks_list_lists`.
- `tasks_list_tasks` → `google.tasks_list_tasks`.
- `tasks_create_task` → `google.tasks_create_task`.
- `tasks_complete_task` → `google.tasks_complete_task`.
- `drive_search_files` → `google.drive_search_files`.
- `drive_get_file` → `google.drive_get_file`.
- `drive_read_text_file` → `google.drive_read_text_file`.
- `docs_read_document` → `google.docs_read_document`.
- `sheets_get_spreadsheet` → `google.sheets_get_spreadsheet`.
- `sheets_read_range` → `google.sheets_read_range`.
- `google_authorize` → `google.google_authorize`.
- `google_connection_status` → `google.google_connection_status`.

### `skill_manifests/gui-control.json`

- `gui_list_windows` → `gui.windows`.
- `gui_inspect_window` → `gui.inspect_window`.
- `gui_click_element` → `gui.click_element`.
- `gui_observe_desktop` → `gui.observe_desktop`.
- `gui_click_desktop` → `gui.click_desktop`.
- `gui_scroll_desktop` → `gui.scroll_desktop`.
- `gui_type_at` → `gui.type_at`.
- `gui_key_at` → `gui.key_at`.
- `gui_browser_bind` → `gui.browser_bind`.
- `gui_browser_open_isolated` → `gui.browser_open_isolated`.
- `gui_browser_snapshot` → `gui.browser_snapshot`.
- `gui_browser_click` → `gui.browser_click`.
- `gui_browser_type` → `gui.browser_type`.
- `gui_browser_navigate` → `gui.browser_navigate`.
- `gui_browser_double_click` → `gui.browser_double_click`.
- `gui_verify_window` → `gui.verify_window`.

### `skill_manifests/input-bar.json`

- `open_input_bar` → `input_bar.open`.
- `close_input_bar` → `input_bar.close`.

### `skill_manifests/internet-search.json`

- `internet_search` → `web.search`.

### `skill_manifests/memory.json`

- `remember_memory` → `memory.remember`.
- `recall_memory` → `memory.recall`.
- `forget_memory` → `memory.forget`.
- `clear_memory` → `memory.clear`.
- `correct_memory` → `memory.correct`.
- `memory_history` → `memory.history`.
- `update_memory_profile` → `memory.profile`.
- `index_memory_document` → `memory.index`.
- `memory_status` → `memory.status`.
- `sync_memory_vault` → `memory.obsidian`.

### `skill_manifests/omarchy-defaults.json`

- `list_applications` → `applications.list`.
- `open_application` → `applications.open`.
- `open_website` → `web.open`.
- `switch_workspace` → `workspace.switch`.
- `show_notification` → `notification.show`.
- `create_reminder` → `reminder.create`.
- `list_reminders` → `reminder.list`.
- `clear_reminders` → `reminder.clear`.
- `cancel_reminder` → `reminder.cancel`.
- `create_todo` → `todo.create`.
- `list_todos` → `todo.list`.
- `update_todo` → `todo.update`.
- `complete_todo` → `todo.complete`.
- `delete_todo` → `todo.delete`.
- `clear_completed_todos` → `todo.clear_completed`.
- `get_desktop_context` → `system.context`.
- `move_todo` → `todo.move`.

### `skill_manifests/phone.json`

- `phone_call` → `phone.call`.
- `phone_answer` → `phone.answer`.
- `phone_hangup` → `phone.hangup`.
- `phone_decline` → `phone.decline`.
- `phone_mute` → `phone.mute`.
- `phone_send_tones` → `phone.send_tones`.
- `phone_list_contacts` → `phone.list_contacts`.
- `phone_recent_calls` → `phone.recent_calls`.
- `phone_status` → `phone.status`.
- `phone_open` → `phone.open`.
- `phone_close` → `phone.close`.

### `skill_manifests/proactive.json`

- `proactive_task` → `proactive.enqueue`.
- `proactive_status` → `proactive.status`.
- `pause_jarvis` → `proactive.pause`.
- `resume_jarvis` → `proactive.resume`.
- `stop_all_jarvis_work` → `proactive.stop`.

### `skill_manifests/system-controls.json`

- `lock_screen` → `system.lock`.
- `take_screenshot` → `system.screenshot`.
- `manage_window` → `window.manage`.
- `control_power` → `system.power`.
- `control_wifi` → `network.wifi`.
- `control_bluetooth` → `network.bluetooth`.
- `read_clipboard` → `clipboard.read`.
- `write_clipboard` → `clipboard.write`.
- `type_text` → `input.type`.
- `press_key` → `input.key`.
- `list_desktop_commands` → `system.keybindings_list`.
- `execute_desktop_command` → `system.keybindings_exec`.
- `list_bar_panels` → `shell.bar_list`.
- `open_bar_panel` → `shell.bar_open`.
- `close_bar_panel` → `shell.bar_close`.
- `set_volume` → `audio.volume_set`.
- `control_microphone` → `audio.mic_control`.
- `set_brightness` → `display.brightness_set`.
- `move_window_to_workspace` → `window.move_workspace`.
- `detect_desktop_dialogs` → `system.detect_dialogs`.
- `handle_desktop_dialog` → `system.handle_dialog`.
- `heal_window_focus` → `system.heal_focus`.
- `verify_ground_truth` → `system.verify_ground_truth`.
- `control_night_light` → `display.night_light`.
- `control_notifications` → `notification.control`.
- `control_theme` → `theme.control`.
- `open_control_panel` → `control_panel.open`.

### `skill_manifests/system-extensions.json`

- `system_control_extension` → `system.extension`.

### `skill_manifests/system-information.json`

- `get_system_information` → `system.information`.
- `get_system_control_status` → `system.control_status`.

### `skill_manifests/task-runner.json`

- `start_task` → `task.start`.
- `task_status` → `task.status`.
- `list_tasks` → `task.list`.
- `cancel_task` → `task.cancel`.

### `skill_manifests/vision.json`

- `control_vision_mode` → `vision.control_mode`.
- `capture_camera_frame` → `vision.capture_frame`.
- `check_vision_hardware` → `vision.check_hardware`.

## Munder main, shared and preload symbols

### [src/main/analytics.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts)

- [EVENTS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L47)
- [AnalyticsFeature](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L97)
- [SpawnFailReason](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L105)
- [InstallRung](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L110)
- [InstallOutcome](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L113)
- [MESSAGE_SURFACES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L128)
- [MessageSurface](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L129)
- [RENDERER_MESSAGE_SURFACES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L138)
- [isRendererMessageSurface](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L144)
- [AnalyticsInitOptions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L148)
- [dntSet](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L157)
- [Analytics](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L165)
- [init](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L183)
- [setEnabled](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L238)
- [track](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L243)
- [trackMessageSent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L269)
- [trackFeature](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L275)
- [endSession](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L283)
- [loadOrMintInstallId](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L295)
- [VERSION_STAMP_FILE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L322)
- [VERSION_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L328)
- [VersionTransition](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L332)
- [updateTransition](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L350)
- [readVersionStamp](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L365)
- [writeVersionStamp](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L377)
- [LOG_FILE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L417)
- [LOG_DOWNLOADED](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L418)
- [LOG_QUIT_REQUESTED](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L419)
- [LOG_QUIT_FAILED](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L420)
- [LOG_READY](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L423)
- [LOG_QUIT_CANCELLED](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L425)
- [LOG_TAIL_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L429)
- [UpdateVia](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L433)
- [updateVia](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L436)
- [readUpdaterLogTail](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L486)
- [durationBucket](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L506)
- [analytics](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/analytics.ts#L516)

### [src/main/breaker.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts)

- [BreakerLevel](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L31)
- [BreakerState](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L35)
- [BreakerAction](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L44)
- [BreakerDecision](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L46)
- [BreakerInput](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L54)
- [LEVELS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L69)
- [rank](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L70)
- [actionFor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L71)
- [tokensOf](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L76)
- [workTokensOf](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L86)
- [DEFAULTS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L89)
- [COMPACT_GRACE_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L99)
- [POST_COMPACT_GRACE_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L102)
- [PROGRESS_TOOL_WINDOW_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L105)
- [NO_PROGRESS_BEATS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L108)
- [AgentBreakerState](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L110)
- [CircuitBreaker](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L138)
- [constructor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L141)
- [cfg](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L143)
- [get](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L157)
- [forget](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L171)
- [levelFor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L176)
- [recordToolUse](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L185)
- [recordError](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L199)
- [recordUserPrompt](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L207)
- [recordCompactStart](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L215)
- [recordCompactEnd](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L223)
- [toolKey](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L228)
- [tick](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L257)
- [evaluate](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/breaker.ts#L328)

### [src/main/cliInstall.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/cliInstall.ts)

- [InstallRungKind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/cliInstall.ts#L13)
- [chooseInstallRung](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/cliInstall.ts#L36)
- [buildMissingCliScript](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/cliInstall.ts#L55)

### [src/main/closingTime.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts)

- [ClosingTimePhase](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L30)
- [ClosingTimeEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L33)
- [ACK_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L43)
- [COMPLETE_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L44)
- [TIMEOUT_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L48)
- [TEARDOWN_GRACE_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L51)
- [ClosingTimeController](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L53)
- [constructor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L61)
- [isActive](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L77)
- [start](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L83)
- [cancel](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L151)
- [onRouted](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L171)
- [armTimeout](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L220)
- [cleanup](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L227)
- [emitState](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/closingTime.ts#L233)

### [src/main/config.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts)

- [ScheduledMission](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L27)
- [OPS_STANDUP_MISSION](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L65)
- [HEARTBEAT_MISSION](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L98)
- [COMPACT_MAINTENANCE_MISSION](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L123)
- [LEGACY_COMPACT_MAINTENANCE_INTERVAL_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L141)
- [CircuitBreakerConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L149)
- [KnowledgeGraphConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L168)
- [HarnessConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L175)
- [DEFAULTS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L422)
- [configPath](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L490)
- [withTriggerDefaults](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L509)
- [migrateTriggersV1](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L548)
- [readConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L588)
- [normalizeStoredHomes](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L612)
- [ConfigWriteListener](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L631)
- [configWriteListeners](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L632)
- [onConfigWritten](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L634)
- [persistConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L639)
- [mkdirSync](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L641)
- [writeConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L669)
- [setAgentTokenCap](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L707)
- [resetConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L733)
- [persistConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L735)
- [MODEL_GOD](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L746)
- [MODEL_WORKER](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L747)
- [MODEL_HELPER](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L748)
- [RoleHint](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L752)
- [modelForRole](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L763)
- [ensureHarnessHome](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L781)
- [ensureClaudeGlobalPermissions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L798)
- [ClaudeProjectConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L822)
- [ClaudeConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L823)
- [ensureClaudeProjectTrust](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L825)
- [ensureClaudePermissionsAccepted](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L876)
- [ensureClaudeGlobalPermissions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/config.ts#L881)

### [src/main/control.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts)

- [MAX_PENDING_STEERS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L25)
- [AgentControlSnapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L27)
- [AgentControl](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L35)
- [ControlRegistry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L43)
- [ensure](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L46)
- [pause](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L63)
- [pauseAutoDelivery](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L64)
- [replaceAutoDeliveryPauses](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L67)
- [gateTool](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L74)
- [steer](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L78)
- [halt](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L92)
- [clearSteers](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L95)
- [resume](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L97)
- [shouldHalt](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L101)
- [isAutoDeliveryPaused](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L102)
- [toolDecision](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L107)
- [takeSteer](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L116)
- [snapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/control.ts#L118)

### [src/main/costLifetime.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts)

- [Segment](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L45)
- [EPS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L54)
- [MAX_BYTES_PER_PASS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L58)
- [CostLedgerTotals](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L60)
- [usdFor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L78)
- [all](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L84)
- [floorTotal](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L94)
- [refresh](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L106)
- [refreshFully](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L116)
- [fold](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L123)
- [consume](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L152)
- [foldLine](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L162)
- [recompute](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L181)
- [reset](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L190)
- [lifetimeUsdFromLedger](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/costLifetime.ts#L203)

### [src/main/db.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts)

- [CommandHistoryRow](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L23)
- [MIGRATIONS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L49)
- [PersistStore](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L70)
- [constructor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L74)
- [open](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L79)
- [migrate](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L91)
- [close](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L105)
- [setKv](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L123)
- [addHistory](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L134)
- [listHistory](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L143)
- [searchHistory](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L157)
- [clampLimit](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/db.ts#L171)

### [src/main/fetchText.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fetchText.ts)

- [getText](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fetchText.ts#L14)

### [src/main/freeflow.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts)

- [GROQ_TRANSCRIBE_URL](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L21)
- [DEFAULT_GROQ_MODEL](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L24)
- [MAX_AUDIO_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L27)
- [REQUEST_TIMEOUT_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L29)
- [TranscribeOptions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L31)
- [TranscribeResult](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L46)
- [transcribeWithGroq](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L56)
- [extractError](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L111)
- [toUint8Array](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L120)
- [toArrayBuffer](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L126)
- [errMsg](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/freeflow.ts#L130)

### [src/main/fs.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts)

- [lexicalJoin](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L16)
- [canonicalize](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L33)
- [hasSymlinkComponent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L66)
- [safeResolve](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L100)
- [READ_FLAGS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L125)
- [WRITE_FLAGS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L126)
- [openForRead](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L142)
- [DirEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L146)
- [listDir](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L153)
- [MAX_READ_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L178)
- [readFileText](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L180)
- [MAX_BINARY_READ_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L212)
- [readFileBinary](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L231)
- [writeFileText](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L275)
- [expandTilde](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L309)
- [normalizeHiveHome](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L335)
- [statAbs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/fs.ts#L357)

### [src/main/git.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts)

- [runGit](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L5)
- [GitBranchInfo](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L29)
- [GitStatusEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L33)
- [GitStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L39)
- [GitCommit](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L44)
- [GitAheadBehind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L53)
- [getBranch](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L59)
- [getStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L67)
- [getLog](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L98)
- [getBranches](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L122)
- [getAheadBehind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L141)
- [isRepo](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L152)
- [MAX_DIFF_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L157)
- [GitDiff](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L163)
- [getDiff](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L180)
- [mainRepoRoot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L242)
- [agentBranchFor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L254)
- [addWorktree](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L263)
- [removeWorktree](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L277)
- [worktreeHasUnintegratedWork](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L291)
- [worktreeIsGcSafe](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L332)
- [isSafeRev](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L358)
- [getLogGraph](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L365)
- [GitCommitFile](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L392)
- [parseNameStatusZ](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L400)
- [getCommitFiles](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L422)
- [MAX_SHOW_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L429)
- [getFileAtRev](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L433)
- [GitCompare](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L449)
- [compareRefs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L458)
- [GitWorktreeInfo](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/git.ts#L473)
- [listWorktrees](https://github.com/HarnessMD/munder-difflin/blob/75…32887 tokens truncated…ithub.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L355)
- [SlackReplyServerOptions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L405)
- [SlackReplyServer](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L425)
- [constructor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L431)
- [start](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L438)
- [stop](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L457)
- [handle](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L462)
- [checkToken](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L503)
- [isLoopback](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/slack.ts#L513)

### [src/main/telemetry.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts)

- [AgentUsageSample](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L43)
- [BreakerState](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L61)
- [ToolSpan](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L72)
- [TelemetryEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L84)
- [TelemetrySnapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L90)
- [SessionAccum](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L97)
- [MAX_BODY_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L108)
- [SPAN_RING_CAP](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L109)
- [TelemetryCollectorOptions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L111)
- [TelemetryCollector](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L131)
- [constructor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L152)
- [start](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L162)
- [stop](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L175)
- [endpoint](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L182)
- [getAgentUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L191)
- [onAgentUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L203)
- [onApiError](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L211)
- [forgetAgent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L226)
- [getSpans](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L236)
- [snapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L241)
- [listen](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L254)
- [handleRequest](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L269)
- [ingestMetrics](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L305)
- [ingestLogs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L343)
- [session](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L384)
- [pushSpan](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L396)
- [aggregateLive](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L405)
- [transcriptFallback](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L439)
- [grokFallback](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L485)
- [publishUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L519)
- [OtelKV](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L529)
- [OtelAnyValue](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L530)
- [OtelDataPoint](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L536)
- [OtelMetric](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L537)
- [ResourceMetrics](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L538)
- [OtelLogRecord](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L539)
- [ResourceLogs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L540)
- [ATTR_ALLOWLIST](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L545)
- [flattenAttrs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L551)
- [pointValue](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L567)
- [str](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L573)
- [numAttr](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L576)
- [truthy](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L580)
- [errMsg](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/telemetry.ts#L583)

### [src/main/transcript.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts)

- [projectKey](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L13)
- [legacyProjectKey](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L20)
- [projectDir](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L43)
- [VALID_SESSION_ID](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L73)
- [seedSessionTranscript](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L75)
- [resolveSessionCwd](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L103)
- [AgentUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L132)
- [zero](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L143)
- [ReadUsageOptions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L147)
- [FileUsageEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L163)
- [usageCache](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L182)
- [USAGE_CACHE_MAX](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L185)
- [parseUsageLines](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L198)
- [readFileUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L255)
- [readAgentUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L313)
- [num](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L339)
- [CONTEXT_TAIL_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L349)
- [readContextTokens](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/transcript.ts#L351)

### [src/main/triggerHistory.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts)

- [TriggerHistoryInput](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L33)
- [TriggerHistoryPatch](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L39)
- [historyPath](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L43)
- [readAll](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L51)
- [writeAll](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L63)
- [isEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L73)
- [normaliseKind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L83)
- [appendTriggerHistory](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L94)
- [writeAll](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L111)
- [listTriggerHistory](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L116)
- [updateTriggerHistory](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L127)
- [writeAll](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L140)
- [clearTriggerHistory](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L147)
- [writeAll](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/triggerHistory.ts#L152)

### [src/main/tunnelmole.d.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/tunnelmole.d.ts)

- Module helpers or types; follow file link.

### [src/main/updater.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts)

- [REPO](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L47)
- [CHECK_INTERVAL_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L48)
- [FALLBACK_CACHE_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L49)
- [abortPendingRestart](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L83)
- [logLine](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L87)
- [resolve](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L88)
- [failPendingRestart](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L101)
- [resolve](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L105)
- [logLine](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L110)
- [emit](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L120)
- [autoUpdateEnabled](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L125)
- [AutoUpdater](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L133)
- [loadAutoUpdater](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L145)
- [errText](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L163)
- [pickDownloadAsset](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L174)
- [fetchReleaseBody](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L190)
- [fallbackCheck](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L219)
- [CHECK_TIMEOUT_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L273)
- [withTimeout](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L277)
- [runCheck](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L292)
- [emit](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L293)
- [runDownload](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L319)
- [SIMULATED_NOTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L346)
- [initAutoUpdater](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/updater.ts#L366)

### [src/main/usage.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts)

- [AgentUsageSample](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L39)
- [UsageProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L56)
- [getAgentUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L58)
- [UsageResolver](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L66)
- [normalizeModel](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L72)
- [StubUsageProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L83)
- [constructor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L84)
- [getAgentUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L86)
- [CumulativeSampleGate](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L122)
- [admits](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L126)
- [forget](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/usage.ts#L137)

### [src/main/webhook.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts)

- [WebhookEndpoint](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L54)
- [WebhookEndpointRef](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L66)
- [WebhookInbound](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L74)
- [WebhookDispatch](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L85)
- [WebhookTaskStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L96)
- [WebhookServerOptions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L102)
- [MAX_BODY_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L123)
- [TUNNEL_START_TIMEOUT_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L125)
- [RATE_LIMIT](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L127)
- [PER_ENDPOINT_RATE_LIMIT](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L130)
- [RATE_WINDOW_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L131)
- [LEGACY_ENDPOINT_ID](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L135)
- [UNKNOWN_BUCKET](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L141)
- [WebhookServer](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L143)
- [constructor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L158)
- [setEndpoints](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L172)
- [endpointIds](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L188)
- [publicUrl](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L193)
- [listening](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L200)
- [start](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L210)
- [stop](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L233)
- [listen](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L239)
- [openTunnel](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L252)
- [allowRequest](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L265)
- [handleRequest](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L276)
- [handleStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L299)
- [handleCreate](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L312)
- [verifySecret](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L383)
- [readEndpointId](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L399)
- [parseSchema](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L412)
- [readToken](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L419)
- [json](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L430)
- [errMsg](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/webhook.ts#L437)

### [src/main/workerLaunch.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerLaunch.ts)

- [WorkerLaunch](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerLaunch.ts#L15)
- [buildWorkerLaunch](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerLaunch.ts#L24)

### [src/main/workerWake.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts)

- [WORKER_WAKE_NUDGE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L36)
- [WORKER_WAKE_IDLE_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L40)
- [WORKER_WAKE_BOOT_GRACE_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L42)
- [WORKER_WAKE_COOLDOWN_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L44)
- [WORKER_WAKE_HITL_REARM_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L46)
- [WORKER_WAKE_STALL_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L67)
- [WORKER_WAKE_REPORT_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L69)
- [HookClass](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L74)
- [classifyHook](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L76)
- [isTurnHook](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L98)
- [WorkerWakeFacts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L115)
- [WorkerWakeHold](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L144)
- [liveInboxIds](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L150)
- [isStalledWorker](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L157)
- [ActivityEvidence](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L166)
- [activityEvidenceAt](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L180)
- [WorkerWakeWatchdog](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L188)
- [noteSpawn](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L208)
- [noteHook](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L215)
- [turnHookAt](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L223)
- [isStalled](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L231)
- [forget](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L239)
- [explain](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L254)
- [decide](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L282)
- [shouldReportHold](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L299)
- [lastNudge](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/workerWake.ts#L306)

### [src/main/worktreeDeps.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/worktreeDeps.ts)

- [DepLink](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/worktreeDeps.ts#L5)
- [DepUnlink](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/worktreeDeps.ts#L9)
- [linkWorktreeDeps](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/worktreeDeps.ts#L14)
- [unlinkWorktreeDeps](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/main/worktreeDeps.ts#L35)

### [src/shared/agentProvider.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts)

- [AgentProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L24)
- [BridgeDescriptor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L53)
- [AgentProviderPreset](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L62)
- [AGENT_PROVIDER_PRESETS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L170)
- [isAgentProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L583)
- [normalizeAgentProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L601)
- [providerPreset](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L605)
- [isClaudeProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L609)
- [isHiveAwareProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L614)
- [canReceiveInbox](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L621)
- [commandBinary](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L626)
- [inferAgentProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L634)
- [bridgeOf](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L661)
- [defaultCommandForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L668)
- [autoModeFlagForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L674)
- [argsWithAutoModeFlag](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L686)
- [hasAutoModeStance](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L697)
- [nonInteractiveEnvForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L706)
- [commandGroupsForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L711)
- [ProviderInstallInfo](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L719)
- [installInfoForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentProvider.ts#L727)

### [src/shared/agentRole.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentRole.ts)

- [TRANSIENT_ROLE_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentRole.ts#L10)
- [isDurableRole](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentRole.ts#L12)
- [preferredAgentRole](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentRole.ts#L23)
- [roleForHiveSpawn](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/agentRole.ts#L39)

### [src/shared/broadcast.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/broadcast.ts)

- [BroadcastCandidate](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/broadcast.ts#L9)
- [selectBroadcastTargets](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/broadcast.ts#L36)

### [src/shared/claudeCommands.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/claudeCommands.ts)

- [CmdKind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/claudeCommands.ts#L16)
- [Cmd](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/claudeCommands.ts#L18)
- [CmdGroup](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/claudeCommands.ts#L25)
- [COMMAND_GROUPS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/claudeCommands.ts#L30)

### [src/shared/codexCommands.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexCommands.ts)

- [CODEX_COMMAND_GROUPS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexCommands.ts#L14)

### [src/shared/codexRemote.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexRemote.ts)

- [CODEX_REMOTE_SOCKET_RELATIVE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexRemote.ts#L4)
- [CODEX_REMOTE_ALIAS_ROOT](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexRemote.ts#L17)
- [CODEX_REMOTE_SOCKET_MAX](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexRemote.ts#L20)
- [codexRemoteAliasPath](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexRemote.ts#L24)
- [codexRemoteSocketFits](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexRemote.ts#L37)
- [codexRemoteEndpoint](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexRemote.ts#L41)
- [withCodexRemoteArgs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/codexRemote.ts#L46)

### [src/shared/commandLine.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/commandLine.ts)

- [tokenizeCommand](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/commandLine.ts#L11)

### [src/shared/dropFonts.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/dropFonts.ts)

- [DROP_FONT_WOFF2_BASE64](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/dropFonts.ts#L18)

### [src/shared/engineAvailability.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/engineAvailability.ts)

- [EngineAvailabilityState](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/engineAvailability.ts#L17)
- [EngineAvailability](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/engineAvailability.ts#L27)
- [classifyEngineAvailability](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/engineAvailability.ts#L38)
- [engineBlocksOnboarding](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/engineAvailability.ts#L56)
- [engineAvailabilityBadge](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/engineAvailability.ts#L61)
- [engineAvailabilityMessage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/engineAvailability.ts#L73)

### [src/shared/godIdentity.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/godIdentity.ts)

- [DEFAULT_GOD_NAME](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/godIdentity.ts#L3)
- [resolveGodName](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/godIdentity.ts#L17)

### [src/shared/grokCommands.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/grokCommands.ts)

- [GROK_COMMAND_GROUPS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/grokCommands.ts#L9)

### [src/shared/heroPayload.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts)

- [HeroPlan](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts#L24)
- [HeroSponsor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts#L31)
- [HeroPayload](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts#L37)
- [DEFAULT_HERO](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts#L47)
- [MAX](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts#L56)
- [str](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts#L58)
- [httpsUrl](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts#L67)
- [parseHeroPayload](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/heroPayload.ts#L81)

### [src/shared/hire.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts)

- [HIRE_SPEC_V1](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L27)
- [BUNDLED_SKILL_IDS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L32)
- [HireProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L41)
- [HireManifest](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L43)
- [HireValidation](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L84)
- [PROVIDERS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L94)
- [MAX_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L95)
- [FLAG_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L102)
- [MODEL_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L112)
- [SAFE_FLAG_NAMES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L139)
- [isSafeFlag](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L149)
- [str](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L155)
- [capped](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L157)
- [validateHireManifest](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L170)
- [parseHireDeepLink](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L322)
- [isAllowedManifestUrl](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L339)
- [HIRE_MAX_BYTES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hire.ts#L346)

### [src/shared/hireQueue.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hireQueue.ts)

- [HireReviewQueue](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hireQueue.ts#L4)
- [EMPTY_HIRE_QUEUE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hireQueue.ts#L10)
- [enqueueHires](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hireQueue.ts#L16)
- [finishCurrentHire](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hireQueue.ts#L29)
- [clearHireQueue](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hireQueue.ts#L36)
- [hireQueueProgress](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hireQueue.ts#L40)

### [src/shared/hiveNudge.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hiveNudge.ts)

- [NUDGE_HEAD](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hiveNudge.ts#L13)
- [inboxNudgeText](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hiveNudge.ts#L25)
- [isInboxNudge](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hiveNudge.ts#L37)

### [src/shared/hookEvents.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hookEvents.ts)

- [HookEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hookEvents.ts#L2)
- [OPTIONAL_STRING_FIELDS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hookEvents.ts#L12)
- [validateHookEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/hookEvents.ts#L15)

### [src/shared/imageTypes.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imageTypes.ts)

- [MIME_BY_EXT](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imageTypes.ts#L23)
- [extensionOf](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imageTypes.ts#L44)
- [imageMimeForPath](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imageTypes.ts#L54)
- [isImagePath](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imageTypes.ts#L59)
- [isSvgPath](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imageTypes.ts#L70)
- [formatBytes](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imageTypes.ts#L75)

### [src/shared/imeGuard.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imeGuard.ts)

- [ComposingKeyEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imeGuard.ts#L32)
- [isComposingKey](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/imeGuard.ts#L42)

### [src/shared/integrations.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts)

- [IntegrationKind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L24)
- [IntegrationAuthType](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L29)
- [IntegrationRecord](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L37)
- [IntegrationTemplate](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L64)
- [INTEGRATION_SLUG_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L84)
- [HEADER_NAME_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L86)
- [ALL_AUTH_TYPES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L87)
- [ALL_KINDS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L88)
- [secretRefFor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L91)
- [authTypeNeedsSecret](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L96)
- [validateIntegrationRecord](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L106)
- [validateBaseUrl](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L151)
- [buildAuthHeaders](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L175)
- [resolveUpstreamUrl](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L204)
- [INTEGRATION_TEMPLATES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/integrations.ts#L239)

### [src/shared/mcpCatalog.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/mcpCatalog.ts)

- [McpTier](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/mcpCatalog.ts#L25)
- [McpCatalogEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/mcpCatalog.ts#L27)
- [MCP_CATALOG](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/mcpCatalog.ts#L52)
- [mcpCatalogEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/mcpCatalog.ts#L156)
- [isSafeReadonlyMcp](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/mcpCatalog.ts#L162)
- [defaultMcpDefaults](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/mcpCatalog.ts#L168)

### [src/shared/modelCatalogPayload.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts)

- [CatalogModel](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L34)
- [ModelCatalog](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L42)
- [CATALOG_SCHEMA_VERSION](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L50)
- [MAX](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L52)
- [str](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L68)
- [bound](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L78)
- [parseModel](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L84)
- [parseKey](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L104)
- [parseModelCatalog](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/modelCatalogPayload.ts#L120)

### [src/shared/ossModels.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/ossModels.ts)

- [OssLocalPick](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/ossModels.ts#L18)
- [OssProviderPick](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/ossModels.ts#L27)
- [OSS_LOCAL_PICKS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/ossModels.ts#L36)
- [OSS_PROVIDER_PICKS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/ossModels.ts#L48)
- [localSlugFor](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/ossModels.ts#L62)
- [hasOssQuickPicks](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/ossModels.ts#L68)
- [OSS_BLOG_LINKS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/ossModels.ts#L73)

### [src/shared/providerAutomation.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts)

- [COMPACTION_FOCUS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L10)
- [ProviderContextCommands](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L13)
- [NO_CONTEXT_COMMANDS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L27)
- [CONTEXT_COMMANDS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L49)
- [contextCommandsForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L153)
- [compactionCommandForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L164)
- [COMPACT_VERBS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L177)
- [isCompactionCommand](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L194)
- [clearCommandForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L208)
- [remoteControlCommandForProvider](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L219)
- [terminalReadySettleMs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L229)
- [terminalReadyToReceive](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/providerAutomation.ts#L248)

### [src/shared/realtimePricing.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/realtimePricing.ts)

- [REALTIME_MODEL](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/realtimePricing.ts#L24)
- [REALTIME_AUDIO_INPUT_PER_MTOK](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/realtimePricing.ts#L27)
- [REALTIME_AUDIO_OUTPUT_PER_MTOK](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/realtimePricing.ts#L28)
- [RealtimeUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/realtimePricing.ts#L35)
- [normalizeRealtimeUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/realtimePricing.ts#L45)
- [computeRealtimeUsd](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/realtimePricing.ts#L61)
- [formatUsd](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/realtimePricing.ts#L70)

### [src/shared/releaseDrop.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts)

- [DROP_OPEN](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts#L46)
- [DROP_CLOSE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts#L47)
- [extractDropHtml](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts#L55)
- [stripActiveContent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts#L74)
- [FRAME_FONT_CSS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts#L104)
- [FRAME_BASE_CSS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts#L125)
- [DEFAULT_DROP_HTML](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts#L260)
- [buildDropSrcDoc](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseDrop.ts#L521)

### [src/shared/releaseNotes.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts)

- [RELEASE_NOTES_MAX_BULLETS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L37)
- [RELEASE_NOTES_MAX_CHARS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L40)
- [RELEASE_NOTES_MAX_BULLET_CHARS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L45)
- [MIN_PARTIAL_CHARS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L47)
- [ReleaseNotesOptions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L49)
- [FENCE_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L55)
- [HEADING_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L56)
- [RULE_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L59)
- [BULLET_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L60)
- [TABLE_ROW_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L61)
- [SETEXT_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L63)
- [WHATS_NEW_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L64)
- [FULL_CHANGELOG_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L66)
- [BARE_URL_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L67)
- [STYLE_SCRIPT_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L86)
- [HTML_HEADING_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L87)
- [HTML_LI_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L88)
- [APOS_ENTITY_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L92)
- [isHeadingLine](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L95)
- [isWhatsNewLine](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L100)
- [bulletPrefix](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L106)
- [stripMarkdown](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L120)
- [isMeaningful](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L146)
- [usableLines](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L156)
- [firstSection](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L188)
- [collectItems](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L214)
- [flush](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L241)
- [clip](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L247)
- [summarizeReleaseNotes](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/releaseNotes.ts#L262)

### [src/shared/taskLedger.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/taskLedger.ts)

- [RawTask](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/taskLedger.ts#L26)
- [isRawTask](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/taskLedger.ts#L28)
- [idOf](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/taskLedger.ts#L32)
- [mergeTaskLedger](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/taskLedger.ts#L53)
- [patchTaskInLedger](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/taskLedger.ts#L80)

### [src/shared/terminalPaths.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts)

- [PREVIEW_EXTS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L35)
- [EDIT_EXTS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L43)
- [PathAction](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L62)
- [extOf](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L70)
- [PATH_TOKEN_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L90)
- [pathTokenMatcher](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L93)
- [URL_TOKEN_RE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L114)
- [urlTokenMatcher](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L117)
- [URL_TRAILING_PROSE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L121)
- [stripUrlToken](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L134)
- [TerminalLinkSpan](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L150)
- [terminalLinkSpans](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L171)
- [stripPathToken](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L198)
- [isPathToken](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L214)
- [classifyPathToken](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/terminalPaths.ts#L231)

### [src/shared/tokenCaps.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/tokenCaps.ts)

- [MAX_AGENT_TOKEN_CAP](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/tokenCaps.ts#L2)

### [src/shared/toolCatalog.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/toolCatalog.ts)

- [ToolKind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/toolCatalog.ts#L21)
- [ToolSpec](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/toolCatalog.ts#L23)
- [BASE_TOOLS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/toolCatalog.ts#L43)
- [toolCatalog](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/toolCatalog.ts#L105)
- [ToolStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/toolCatalog.ts#L128)
- [setupPrompt](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/toolCatalog.ts#L146)

### [src/shared/triggers.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts)

- [TriggerMode](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L28)
- [TRIGGER_MODES](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L30)
- [DEFAULT_TRIGGER_MODE](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L36)
- [InboundKind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L43)
- [isAutoAllowed](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L46)
- [classifyInboundKind](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L60)
- [ContextRule](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L82)
- [ContextTriggerConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L108)
- [DEFAULT_COMPACTION_FOCUS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L117)
- [DEFAULT_CONTEXT_TRIGGER](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L133)
- [WebhookTrigger](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L159)
- [DEFAULT_WEBHOOK_SCHEMA_OBJECT](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L176)
- [DEFAULT_WEBHOOK_SCHEMA](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L191)
- [OrgTriggerConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L202)
- [DEFAULT_ORG_TRIGGER](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L208)
- [CLONE_NODE_BLURB](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L215)
- [TriggerHistoryEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L227)
- [TRIGGER_HISTORY_LIMIT](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L248)
- [validateAgainstSchema](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L259)
- [matchesType](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L294)
- [isPlainObject](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/triggers.ts#L307)

### [src/shared/updateState.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts)

- [UpdateStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L11)
- [UpdateAction](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L34)
- [REPO](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L36)
- [installerUrl](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L41)
- [pendingVersion](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L52)
- [manualDownloadUrl](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L60)
- [UpdateBadgeView](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L66)
- [parseVersion](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L78)
- [isNewer](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L83)
- [shouldShowReleaseDrop](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L117)
- [clampPercent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L126)
- [rank](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L133)
- [versionOf](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L147)
- [reduceStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L160)
- [describeUpdate](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L175)
- [UpdateSettingsView](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L233)
- [describeUpdateSettings](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L256)
- [manualInstallSteps](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/updateState.ts#L325)

### [src/shared/weeklySchedule.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts)

- [WeeklySchedule](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L25)
- [WEEKDAY_LABELS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L32)
- [WEEKDAY_INITIALS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L35)
- [WEEKLY_CATCHUP_MS](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L47)
- [normalizeWeekly](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L53)
- [formatMinute](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L68)
- [formatWeekly](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L75)
- [slotAt](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L88)
- [nextWeeklyFireMs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L98)
- [previousWeeklyFireMs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L113)
- [weeklyDelayMs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/shared/weeklySchedule.ts#L136)

### [src/preload/index.d.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.d.ts)

- Module helpers or types; follow file link.

### [src/preload/index.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts)

- [IntegrationRecordView](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L29)
- [RosterSnapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L38)
- [HiveAgentMeta](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L48)
- [HiveMessage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L61)
- [VoiceMessage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L80)
- [HiveRegistry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L95)
- [AgentDirectoryEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L110)
- [AgentDirectory](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L139)
- [HumanQA](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L145)
- [HiveTask](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L154)
- [HiveRouteEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L179)
- [HiveTerminalHandoffEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L191)
- [SpawnPtyOptions](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L202)
- [PtyExit](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L228)
- [ScheduledMission](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L231)
- [KnowledgeGraphConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L247)
- [CircuitBreakerConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L252)
- [HarnessConfig](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L260)
- [MemoryStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L336)
- [KnowledgeStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L347)
- [KnowledgeDoc](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L354)
- [KnowledgeHit](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L369)
- [KnowledgeIngestResult](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L378)
- [DirEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L384)
- [GitCommit](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L391)
- [GitStatusEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L400)
- [GitStatus](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L401)
- [GitDiff](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L403)
- [GitCommitRow](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L415)
- [GitFileChange](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L424)
- [AgentUsage](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L433)
- [AgentUsageSample](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L445)
- [ToolSpan](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L458)
- [PowerResumeEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L473)
- [ClosingTimeEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L481)
- [AgentControlSnapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L489)
- [BreakerState](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L498)
- [TelemetryEvent](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L506)
- [TelemetrySnapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L512)
- [CommandHistoryEntry](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L518)
- [GHIssue](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L527)
- [CIRun](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L537)
- [WorkerSnapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L545)
- [PreservedWorktreeSnapshot](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L560)
- [api](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L567)
- [CthApi](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/preload/index.ts#L1431)

## Munder renderer module map

UI modules are candidates for reuse or observation; backend authority must not be inferred from a UI label.

- [src/renderer/src/App.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/App.tsx)
- [src/renderer/src/components/AddAgentModal.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AddAgentModal.tsx)
- [src/renderer/src/components/AgentCard.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AgentCard.tsx)
- [src/renderer/src/components/AgentControlStrip.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AgentControlStrip.tsx)
- [src/renderer/src/components/AgentDetailPanel.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AgentDetailPanel.tsx)
- [src/renderer/src/components/AgentHoldButton.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AgentHoldButton.tsx)
- [src/renderer/src/components/AgentNameEditor.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AgentNameEditor.tsx)
- [src/renderer/src/components/AgentStrip.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AgentStrip.tsx)
- [src/renderer/src/components/AiEnginesSettings.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AiEnginesSettings.tsx)
- [src/renderer/src/components/AskMeTab.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/AskMeTab.tsx)
- [src/renderer/src/components/BlockedBanner.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/BlockedBanner.tsx)
- [src/renderer/src/components/CodeEditor.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/CodeEditor.tsx)
- [src/renderer/src/components/CommandBar.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/CommandBar.tsx)
- [src/renderer/src/components/CommandCenterPanel.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/CommandCenterPanel.tsx)
- [src/renderer/src/components/EditAgentModal.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/EditAgentModal.tsx)
- [src/renderer/src/components/FileTree.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/FileTree.tsx)
- [src/renderer/src/components/FilesTab.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/FilesTab.tsx)
- [src/renderer/src/components/FullscreenTerminal.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/FullscreenTerminal.tsx)
- [src/renderer/src/components/GitTab.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/GitTab.tsx)
- [src/renderer/src/components/HivePicker.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/HivePicker.tsx)
- [src/renderer/src/components/Icon.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/Icon.tsx)
- [src/renderer/src/components/IntegrationsRegistry.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/IntegrationsRegistry.tsx)
- [src/renderer/src/components/McpDefaultsSettings.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/McpDefaultsSettings.tsx)
- [src/renderer/src/components/MemoryGraphPanel.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/MemoryGraphPanel.tsx)
- [src/renderer/src/components/MemoryPanel.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/MemoryPanel.tsx)
- [src/renderer/src/components/MessageQueueComposer.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/MessageQueueComposer.tsx)
- [src/renderer/src/components/MichaelBooting.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/MichaelBooting.tsx)
- [src/renderer/src/components/OfficeThemePicker.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/OfficeThemePicker.tsx)
- [src/renderer/src/components/OnboardingWizard.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/OnboardingWizard.tsx)
- [src/renderer/src/components/PixelBadge.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/PixelBadge.tsx)
- [src/renderer/src/components/PixelButton.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/PixelButton.tsx)
- [src/renderer/src/components/PixelPanel.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/PixelPanel.tsx)
- [src/renderer/src/components/ProviderLogo.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/ProviderLogo.tsx)
- [src/renderer/src/components/PtyTerminalView.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/PtyTerminalView.tsx)
- [src/renderer/src/components/QuitWarningModal.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/QuitWarningModal.tsx)
- [src/renderer/src/components/RealtimeMichaelToggle.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/RealtimeMichaelToggle.tsx)
- [src/renderer/src/components/RecentText.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/RecentText.tsx)
- [src/renderer/src/components/ReleaseDrop.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/ReleaseDrop.tsx)
- [src/renderer/src/components/SettingsHeroCard.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/SettingsHeroCard.tsx)
- [src/renderer/src/components/SettingsModal.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/SettingsModal.tsx)
- [src/renderer/src/components/SetupPanel.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/SetupPanel.tsx)
- [src/renderer/src/components/SidebarSplitter.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/SidebarSplitter.tsx)
- [src/renderer/src/components/SidebarTabs.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/SidebarTabs.tsx)
- [src/renderer/src/components/SkillsTab.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/SkillsTab.tsx)
- [src/renderer/src/components/SpritePortrait.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/SpritePortrait.tsx)
- [src/renderer/src/components/TaskDetailOverlay.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/TaskDetailOverlay.tsx)
- [src/renderer/src/components/TasksKanban.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/TasksKanban.tsx)
- [src/renderer/src/components/TerminalView.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/TerminalView.tsx)
- [src/renderer/src/components/ThreadsPanel.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/ThreadsPanel.tsx)
- [src/renderer/src/components/ToolWaterfall.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/ToolWaterfall.tsx)
- [src/renderer/src/components/UpdateBadge.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/UpdateBadge.tsx)
- [src/renderer/src/components/UpdateToast.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/UpdateToast.tsx)
- [src/renderer/src/components/UpdatesSection.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/UpdatesSection.tsx)
- [src/renderer/src/components/WorkersTab.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/WorkersTab.tsx)
- [src/renderer/src/components/ansiText.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/ansiText.ts)
- [src/renderer/src/components/askMeOrder.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/askMeOrder.ts)
- [src/renderer/src/components/git/CommitGraph.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/git/CommitGraph.tsx)
- [src/renderer/src/components/git/graph.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/git/graph.ts)
- [src/renderer/src/components/memoryGraph/buildGraph.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/memoryGraph/buildGraph.ts)
- [src/renderer/src/components/memoryGraph/extractTopics.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/memoryGraph/extractTopics.ts)
- [src/renderer/src/components/memoryGraph/forceLayout.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/memoryGraph/forceLayout.ts)
- [src/renderer/src/components/termColor.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/termColor.ts)
- [src/renderer/src/components/terminalAutomation.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/terminalAutomation.ts)
- [src/renderer/src/components/terminalFontSize.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/terminalFontSize.ts)
- [src/renderer/src/components/terminalKeys.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/terminalKeys.ts)
- [src/renderer/src/components/terminalPool.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/terminalPool.ts)
- [src/renderer/src/components/terminalRecovery.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/terminalRecovery.ts)
- [src/renderer/src/components/terminalSelection.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/terminalSelection.ts)
- [src/renderer/src/components/triggers/ContextSection.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/ContextSection.tsx)
- [src/renderer/src/components/triggers/JsonEditor.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/JsonEditor.tsx)
- [src/renderer/src/components/triggers/OrgSection.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/OrgSection.tsx)
- [src/renderer/src/components/triggers/SchedulesSection.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/SchedulesSection.tsx)
- [src/renderer/src/components/triggers/TriggerHistoryTab.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/TriggerHistoryTab.tsx)
- [src/renderer/src/components/triggers/TriggersTab.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/TriggersTab.tsx)
- [src/renderer/src/components/triggers/WebhooksSection.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/WebhooksSection.tsx)
- [src/renderer/src/components/triggers/api.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/api.ts)
- [src/renderer/src/components/triggers/ui.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/components/triggers/ui.tsx)
- [src/renderer/src/design/theme.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/design/theme.ts)
- [src/renderer/src/design/tokens.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/design/tokens.ts)
- [src/renderer/src/freeflow/holdOption.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/freeflow/holdOption.ts)
- [src/renderer/src/freeflow/recorder.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/freeflow/recorder.ts)
- [src/renderer/src/hooks/queueDelivery.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/hooks/queueDelivery.ts)
- [src/renderer/src/hooks/useHive.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/hooks/useHive.ts)
- [src/renderer/src/hooks/usePtyParser.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/hooks/usePtyParser.ts)
- [src/renderer/src/hooks/useResolvedGodName.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/hooks/useResolvedGodName.ts)
- [src/renderer/src/hooks/useRestoreTeam.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/hooks/useRestoreTeam.ts)
- [src/renderer/src/hooks/useTelemetry.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/hooks/useTelemetry.ts)
- [src/renderer/src/hooks/useTypewriter.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/hooks/useTypewriter.ts)
- [src/renderer/src/hooks/useWorkspaceImage.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/hooks/useWorkspaceImage.ts)
- [src/renderer/src/i18n/index.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/i18n/index.ts)
- [src/renderer/src/i18n/useDirection.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/i18n/useDirection.ts)
- [src/renderer/src/i18n/useGodNameSync.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/i18n/useGodNameSync.ts)
- [src/renderer/src/ide/GitPanes.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/ide/GitPanes.tsx)
- [src/renderer/src/ide/IdePanel.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/ide/IdePanel.tsx)
- [src/renderer/src/ide/ImagePreview.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/ide/ImagePreview.tsx)
- [src/renderer/src/ide/MonacoDiff.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/ide/MonacoDiff.tsx)
- [src/renderer/src/ide/MonacoEditor.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/ide/MonacoEditor.tsx)
- [src/renderer/src/ide/chrome.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/ide/chrome.ts)
- [src/renderer/src/ide/monaco.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/ide/monaco.ts)
- [src/renderer/src/integrations/registryClient.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/integrations/registryClient.ts)
- [src/renderer/src/main.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/main.tsx)
- [src/renderer/src/markdown/MarkdownPreview.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/markdown/MarkdownPreview.tsx)
- [src/renderer/src/markdown/mdLinks.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/markdown/mdLinks.ts)
- [src/renderer/src/markdown/rehypeAutoDir.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/markdown/rehypeAutoDir.ts)
- [src/renderer/src/markdown/remarkSoftBreaks.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/markdown/remarkSoftBreaks.ts)
- [src/renderer/src/realtime/CompletionToast.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/realtime/CompletionToast.tsx)
- [src/renderer/src/realtime/CostHud.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/realtime/CostHud.tsx)
- [src/renderer/src/realtime/DevicePicker.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/realtime/DevicePicker.tsx)
- [src/renderer/src/realtime/actions.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/realtime/actions.ts)
- [src/renderer/src/realtime/costStore.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/realtime/costStore.ts)
- [src/renderer/src/realtime/session.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/realtime/session.ts)
- [src/renderer/src/realtime/tools.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/realtime/tools.ts)
- [src/renderer/src/scene/office/Camera.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/Camera.ts)
- [src/renderer/src/scene/office/Character.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/Character.ts)
- [src/renderer/src/scene/office/CharacterSprite.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/CharacterSprite.ts)
- [src/renderer/src/scene/office/DeskScreen.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/DeskScreen.ts)
- [src/renderer/src/scene/office/MessageEnvelope.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/MessageEnvelope.ts)
- [src/renderer/src/scene/office/OfficeFloor.tsx](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/OfficeFloor.tsx)
- [src/renderer/src/scene/office/SeatPool.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/SeatPool.ts)
- [src/renderer/src/scene/office/SpriteAdapter.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/SpriteAdapter.ts)
- [src/renderer/src/scene/office/ThoughtBubble.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/ThoughtBubble.ts)
- [src/renderer/src/scene/office/TiledMapRenderer.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/TiledMapRenderer.ts)
- [src/renderer/src/scene/office/ToolBubble.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/ToolBubble.ts)
- [src/renderer/src/scene/office/cafeteriaLines.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/cafeteriaLines.ts)
- [src/renderer/src/scene/office/cast.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/cast.ts)
- [src/renderer/src/scene/office/glRecovery.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/glRecovery.ts)
- [src/renderer/src/scene/office/pathfinding.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/pathfinding.ts)
- [src/renderer/src/scene/office/portraitArt.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/portraitArt.ts)
- [src/renderer/src/scene/office/themeLoader.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/themeLoader.ts)
- [src/renderer/src/scene/office/themeRegistry.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/scene/office/themeRegistry.ts)
- [src/renderer/src/store/config.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/store/config.ts)
- [src/renderer/src/store/focusMode.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/store/focusMode.ts)
- [src/renderer/src/store/mockEvents.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/store/mockEvents.ts)
- [src/renderer/src/store/rosterSource.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/store/rosterSource.ts)
- [src/renderer/src/store/store.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/store/store.ts)
- [src/renderer/src/terminal/arabicJoiner.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/terminal/arabicJoiner.ts)
- [src/renderer/src/terminal/arabicSetting.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/terminal/arabicSetting.ts)
- [src/renderer/src/terminal/arabicSpacingFix.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/terminal/arabicSpacingFix.ts)
- [src/renderer/src/terminal/useArabicTerminalSync.ts](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/src/renderer/src/terminal/useArabicTerminalSync.ts)

## Munder focused-test navigation

Tests are indexed, not executed in this analysis. Review implementation assertions and dependency requirements before reusing them.

- [agent-exit-record.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/agent-exit-record.test.cjs)
- [agent-exit-signal-e2e.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/agent-exit-signal-e2e.test.cjs)
- [agent-provider.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/agent-provider.test.cjs)
- [agent-role.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/agent-role.test.cjs)
- [agent-token-cap.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/agent-token-cap.test.cjs)
- [ansi-text.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/ansi-text.test.cjs)
- [arabic-terminal.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/arabic-terminal.test.cjs)
- [arabic-ui.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/arabic-ui.test.cjs)
- [askme-order.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/askme-order.test.cjs)
- [auto-mode-sandbox.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/auto-mode-sandbox.test.cjs)
- [breaker.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/breaker.test.cjs)
- [broadcast-targets.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/broadcast-targets.test.cjs)
- [bundled-fonts.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/bundled-fonts.test.cjs)
- [claude-permissions-config.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/claude-permissions-config.test.cjs)
- [cli-install-ladder.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/cli-install-ladder.test.cjs)
- [codex-remote.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/codex-remote.test.cjs)
- [command-name-validation.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/command-name-validation.test.cjs)
- [commit-graph.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/commit-graph.test.cjs)
- [compact-latch.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/compact-latch.test.cjs)
- [config-write-notify.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/config-write-notify.test.cjs)
- [control.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/control.test.cjs)
- [cost-lifetime.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/cost-lifetime.test.cjs)
- [crush-provider-config.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/crush-provider-config.test.cjs)
- [engine-availability.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/engine-availability.test.cjs)
- [expand-tilde.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/expand-tilde.test.cjs)
- [focus-mode.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/focus-mode.test.cjs)
- [fs-path-containment.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/fs-path-containment.test.cjs)
- [git-status-rename.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/git-status-rename.test.cjs)
- [god-identity.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/god-identity.test.cjs)
- [grok-usage-ledger.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/grok-usage-ledger.test.cjs)
- [harness-home-tilde.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/harness-home-tilde.test.cjs)
- [harness-home.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/harness-home.test.cjs)
- [hero-payload.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hero-payload.test.cjs)
- [hire-import.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hire-import.test.cjs)
- [hire-queue.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hire-queue.test.cjs)
- [hire-validator-parity.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hire-validator-parity.test.cjs)
- [hive-archived-recipient.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-archived-recipient.test.cjs)
- [hive-cwd.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-cwd.test.cjs)
- [hive-generated-docs.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-generated-docs.test.cjs)
- [hive-hook-node.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-hook-node.test.cjs)
- [hive-hop-cap.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-hop-cap.test.cjs)
- [hive-malformed-outbox.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-malformed-outbox.test.cjs)
- [hive-nudge.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-nudge.test.cjs)
- [hive-pi-bootstrap.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-pi-bootstrap.test.cjs)
- [hive-pi-models.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-pi-models.test.cjs)
- [hive-roster-injection.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-roster-injection.test.cjs)
- [hive-runtime-path.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-runtime-path.test.cjs)
- [hive-task-mutation.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-task-mutation.test.cjs)
- [hive-unknown-recipient.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-unknown-recipient.test.cjs)
- [hive-windows-prompt.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hive-windows-prompt.test.cjs)
- [hook-event-contract.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hook-event-contract.test.cjs)
- [hooks-framing.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hooks-framing.test.cjs)
- [hooks-notification.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hooks-notification.test.cjs)
- [hooks-socket.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/hooks-socket.test.cjs)
- [i18n-god-name.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/i18n-god-name.test.cjs)
- [ide-image.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/ide-image.test.cjs)
- [ime-guard.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/ime-guard.test.cjs)
- [kg-core.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/kg-core.test.cjs)
- [memory-rearm.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/memory-rearm.test.cjs)
- [mempalace-device.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/mempalace-device.test.cjs)
- [mine-ignore-sync.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/mine-ignore-sync.test.cjs)
- [model-catalog-remote.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/model-catalog-remote.test.cjs)
- [model-catalog.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/model-catalog.test.cjs)
- [node-install.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/node-install.test.cjs)
- [office-gl-recovery.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/office-gl-recovery.test.cjs)
- [osc-color-reply.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/osc-color-reply.test.cjs)
- [palace-reap.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/palace-reap.test.cjs)
- [pi-bridge.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/pi-bridge.test.cjs)
- [pr-evidence-gate.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/pr-evidence-gate.test.cjs)
- [proc-kill.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/proc-kill.test.cjs)
- [provider-automation.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/provider-automation.test.cjs)
- [provider-config.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/provider-config.test.cjs)
- [proxy-bridge-retry.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/proxy-bridge-retry.test.cjs)
- [pty-env.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/pty-env.test.cjs)
- [queue-delivery.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/queue-delivery.test.cjs)
- [quit-sweep.electron.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/quit-sweep.electron.test.cjs)
- [realtime-findcard.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/realtime-findcard.test.cjs)
- [reflect-summary.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/reflect-summary.test.cjs)
- [release-drop-reach.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/release-drop-reach.test.cjs)
- [release-drop.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/release-drop.test.cjs)
- [release-notes.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/release-notes.test.cjs)
- [renderer-sandbox.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/renderer-sandbox.test.cjs)
- [restart-cancel.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/restart-cancel.test.cjs)
- [restart-terminal-preserve.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/restart-terminal-preserve.test.cjs)
- [roster-source.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/roster-source.test.cjs)
- [roster.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/roster.test.cjs)
- [settings-one-save.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/settings-one-save.test.cjs)
- [skills-install.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/skills-install.test.cjs)
- [skills.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/skills.test.cjs)
- [slack-stop-persist.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/slack-stop-persist.test.cjs)
- [slack-timeout.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/slack-timeout.test.cjs)
- [slack.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/slack.test.cjs)
- [standing-goal-injection.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/standing-goal-injection.test.cjs)
- [task-ledger.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/task-ledger.test.cjs)
- [telemetry-forget-agent.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/telemetry-forget-agent.test.cjs)
- [telemetry-funnel.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/telemetry-funnel.test.cjs)
- [telemetry-message-count.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/telemetry-message-count.test.cjs)
- [telemetry-session-fallback.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/telemetry-session-fallback.test.cjs)
- [terminal-automation.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/terminal-automation.test.cjs)
- [terminal-keys.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/terminal-keys.test.cjs)
- [terminal-link-activation.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/terminal-link-activation.test.cjs)
- [terminal-paths.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/terminal-paths.test.cjs)
- [terminal-recovery.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/terminal-recovery.test.cjs)
- [terminal-selection.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/terminal-selection.test.cjs)
- [theme-notify.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/theme-notify.test.cjs)
- [transcript-project-dir.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/transcript-project-dir.test.cjs)
- [transcript-usage.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/transcript-usage.test.cjs)
- [tui-theme-hint.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/tui-theme-hint.test.cjs)
- [update-applied.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/update-applied.test.cjs)
- [update-badge-acknowledgement.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/update-badge-acknowledgement.test.cjs)
- [update-check-timeout.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/update-check-timeout.test.cjs)
- [update-download-asset.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/update-download-asset.test.cjs)
- [update-state.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/update-state.test.cjs)
- [voice-messages.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/voice-messages.test.cjs)
- [webhook-endpoints.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/webhook-endpoints.test.cjs)
- [weekly-schedule.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/weekly-schedule.test.cjs)
- [win-cmd-shim.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/win-cmd-shim.test.cjs)
- [windows-command-fallback.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/windows-command-fallback.test.cjs)
- [worker-inbox-settle.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/worker-inbox-settle.test.cjs)
- [worker-launch.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/worker-launch.test.cjs)
- [worker-permission-parity.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/worker-permission-parity.test.cjs)
- [worker-wake-stall.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/worker-wake-stall.test.cjs)
- [worker-wake.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/worker-wake.test.cjs)
- [worktree-deps.test.cjs](https://github.com/HarnessMD/munder-difflin/blob/75869287eb5ab88d382a3711332bdb9918cf1073/test/worktree-deps.test.cjs)

<!-- inventory-complete -->
