# Test-suite symbol index

TASK-09 · static AST inventory, 2026-10-27. Test-definition and assert counts are lexical, not collected/parametrized counts or proof of execution. The SHA-256 values describe the current test sources, not prior audit source. No application module was imported. IDs TS-001 onward are fixed for this snapshot; append future IDs rather than renumber existing ones.

## TS-001 — `tests/e2e/conftest.py`

SHA-256 `fe5b1d6c970335afe5c2925d6005a407541067abafb64de9fa0a21fccca50081`. 0 test definitions; 0 assert nodes.
- No `test_*` function definitions; may be helper, fixture or explicit CLI.

## TS-002 — `tests/e2e/product_behavior_chainlit_app.py`

SHA-256 `8cae633ddb09bb28a60f543cc3d2cb9ad92640d740dacc85f79106dbeebdda25`. 0 test definitions; 0 assert nodes.
- No `test_*` function definitions; may be helper, fixture or explicit CLI.

## TS-003 — `tests/e2e/test_product_behavior_browser.py`

SHA-256 `103103c10c0e214e77bc3243bf999a41cb1b02464537d9c46abb2a70abb2842d`. 13 test definitions; 66 assert nodes.
- `test_product_e2e_is_headless_unless_explicitly_opted_in` at line 155; asserts 3, raises contexts 0.
- `test_pb_nav_001_home_is_message_free` at line 188; asserts 3, raises contexts 0.
- `test_pb_nav_003_ended_chats_visible_and_read_only` at line 202; asserts 3, raises contexts 0.
- `test_pb_nav_008_reload_restores_navigation` at line 211; asserts 2, raises contexts 0.
- `test_pb_life_001_new_chat_persists_and_opens` at line 223; asserts 1, raises contexts 0.
- `test_pb_life_005_end_chat_does_not_render_navigation` at line 242; asserts 2, raises contexts 0.
- `test_pb_life_006_ended_history_remains_readable` at line 256; asserts 2, raises contexts 0.
- `test_pb_life_009_fork_creates_and_opens_independent_chat` at line 264; asserts 1, raises contexts 0.
- `test_product_shell_visual_cleanup_and_toolbar_state` at line 284; asserts 24, raises contexts 0.
- `test_pb_doc_002_indexing_finishes_before_answer` at line 355; asserts 7, raises contexts 0.
- `test_answer_inspector_is_read_only_message_local_and_survives_reload` at line 396; asserts 13, raises contexts 0.
- `test_answer_inspector_reports_forced_native_fallback` at line 464; asserts 2, raises contexts 0.
- `test_answer_inspector_shows_cross_chat_provenance` at line 482; asserts 3, raises contexts 0.

## TS-004 — `tests/product_behavior/__init__.py`

SHA-256 `1a8e31d6d19232d82c38ebd42169f76435b3b848470e805c8e40cc2df8805b81`. 0 test definitions; 0 assert nodes.
- No `test_*` function definitions; may be helper, fixture or explicit CLI.

## TS-005 — `tests/product_behavior/test_inventory.py`

SHA-256 `962c1ebaeb2cb8a3aa825fc44d90946da3195c8d16cba8e7ca8dff2fe35bd0da`. 3 test definitions; 6 assert nodes.
- `test_product_behavior_inventory_is_exactly_50_and_frozen_by_category` at line 14; asserts 4, raises contexts 0.
- `test_every_case_has_an_explicit_oracle` at line 23; asserts 1, raises contexts 0.
- `test_case_ids_are_numbered_by_required_inventory` at line 30; asserts 1, raises contexts 0.

## TS-006 — `tests/product_behavior/test_runner.py`

SHA-256 `738dddf86b8f8e8508e13d3eb1f2bd8213edf0cbe3c0cda0d6168dc139e132f0`. 3 test definitions; 15 assert nodes.
- `test_non_browser_product_oracles_execute_without_harness_errors` at line 35; asserts 3, raises contexts 0.
- `test_report_contains_all_reliability_metrics` at line 46; asserts 7, raises contexts 0.
- `test_summary_counts_executed_browser_cases` at line 68; asserts 5, raises contexts 0.

## TS-007 — `tests/test_answer_inspector.py`

SHA-256 `dde51c54bab9e0c52a458fcd1a51c184cda72374f5a20f7d07821655264ab118`. 8 test definitions; 31 assert nodes.
- `test_completed_graph_answer_persists_reloadable_read_only_inspection` at line 93; asserts 9, raises contexts 0.
- `test_forced_graph_failure_reports_native_fallback_truthfully` at line 133; asserts 3, raises contexts 0.
- `test_document_inspection_enforces_chat_scope_and_reports_lifecycle` at line 152; asserts 3, raises contexts 0.
- `test_current_chat_evidence_cannot_expose_another_chat` at line 194; asserts 2, raises contexts 0.
- `test_cross_chat_raw_span_reports_prior_chat_and_message_provenance` at line 213; asserts 4, raises contexts 0.
- `test_missing_diagnostics_and_serialization_failure_do_not_break_answer` at line 237; asserts 3, raises contexts 0.
- `test_fork_copies_inspection_to_remapped_assistant_message` at line 255; asserts 5, raises contexts 0.
- `test_answer_inspection_schema_is_added_idempotently_to_old_database` at line 277; asserts 2, raises contexts 0.

## TS-008 — `tests/test_answer_policy_prompts.py`

SHA-256 `273bb26c9881484e9fcd1cc28eedceef1a5a5e1199202299074b5f703560dd40`. 5 test definitions; 8 assert nodes.
- `test_production_system_prompt_answers_when_context_is_sufficient` at line 7; asserts 1, raises contexts 0.
- `test_production_system_prompt_keeps_abstention_for_missing_evidence` at line 14; asserts 1, raises contexts 0.
- `test_generic_answer_policy_prioritizes_explicit_context_over_priors` at line 21; asserts 2, raises contexts 0.
- `test_generic_answer_policy_does_not_force_choice_between_conflicting_claims` at line 30; asserts 2, raises contexts 0.
- `test_generic_answer_policy_qualifies_partial_evidence` at line 39; asserts 2, raises contexts 0.

## TS-009 — `tests/test_architecture_layers.py`

SHA-256 `b0d2b5a48ed0a38ba6f42e4921c0cc03ec58dedbe7fcda8cadc748f0f38846cf`. 9 test definitions; 99 assert nodes.
- `test_route_planner_profiles_and_sources` at line 54; asserts 13, raises contexts 0.
- `test_routing_agent_wraps_existing_route_plan_behavior` at line 92; asserts 8, raises contexts 0.
- `test_routing_agent_falls_back_when_planner_fails` at line 109; asserts 6, raises contexts 0.
- `test_retriever_dispatcher_calls_only_enabled_retrievers` at line 125; asserts 5, raises contexts 0.
- `test_retrievers_return_useful_metadata` at line 158; asserts 7, raises contexts 0.
- `test_memory_reranker_scores_sorts_and_does_not_mutate` at line 197; asserts 8, raises contexts 0.
- `test_context_budget_allocator_profiles_and_disabled_sources` at line 232; asserts 12, raises contexts 0.
- `test_coordinator_trace_contains_all_trace_only_layers` at line 291; asserts 34, raises contexts 0.
- `test_coordinator_falls_back_when_context_packet_is_invalid` at line 354; asserts 6, raises contexts 0.

## TS-010 — `tests/test_backend.py`

SHA-256 `19ecabb13ce7e36468cb9b21ed4d978e83867cfbdba20f26aa0c1349cf2cce53`. 0 test definitions; 0 assert nodes.
- No `test_*` function definitions; may be helper, fixture or explicit CLI.

## TS-011 — `tests/test_chainlit_chat_actions.py`

SHA-256 `84a6aa60fc8b0e5eeca467b3488abc7cec0e9115303a660dde143728a8d50566`. 14 test definitions; 52 assert nodes.
- `test_end_chat_uses_authoritative_action_keeps_history_and_refreshes` at line 57; asserts 6, raises contexts 0.
- `test_failed_end_does_not_present_chat_as_ended` at line 102; asserts 4, raises contexts 0.
- `test_fork_chat_switches_to_authoritative_action_result` at line 129; asserts 6, raises contexts 0.
- `test_new_chat_uses_current_chat_service_and_opens_it` at line 159; asserts 6, raises contexts 0.
- `test_inactive_chat_rejects_turn_before_model_or_persistence` at line 187; asserts 2, raises contexts 0.
- `test_chat_start_is_home_and_does_not_create_message_or_chat` at line 210; asserts 3, raises contexts 0.
- `test_home_navigation_does_not_create_conversation_message` at line 229; asserts 5, raises contexts 0.
- `test_chat_resume_restores_persisted_ended_state` at line 242; asserts 4, raises contexts 0.
- `test_chat_controls_are_state_only_not_conversation_messages` at line 268; asserts 2, raises contexts 0.
- `test_answer_inspector_state_is_window_only_and_scoped_to_chat` at line 289; asserts 2, raises contexts 0.
- `test_inspector_serialization_failure_is_non_blocking` at line 321; asserts 2, raises contexts 0.
- `test_window_lifecycle_action_delegates_to_existing_handler` at line 336; asserts 2, raises contexts 0.
- `test_live_orchestration_mode_is_configured_without_ui_selector` at line 359; asserts 3, raises contexts 0.
- `test_same_turn_upload_persists_user_before_index_and_answers_once` at line 369; asserts 5, raises contexts 0.

## TS-012 — `tests/test_chainlit_data_layer.py`

SHA-256 `995cc41debb5a91574c91c213ee5b4117156fb00bb2aea1141f99388b35e891a`. 4 test definitions; 26 assert nodes.
- `test_chainlit_data_layer_lists_and_loads_threads` at line 15; asserts 12, raises contexts 0.
- `test_chainlit_data_layer_lists_active_and_ended_with_stable_pagination` at line 53; asserts 7, raises contexts 0.
- `test_loading_ended_thread_returns_only_its_readable_history` at line 88; asserts 4, raises contexts 0.
- `test_chainlit_data_layer_update_and_delete_thread` at line 110; asserts 3, raises contexts 0.

## TS-013 — `tests/test_chainlit_memory_trace_helpers.py`

SHA-256 `aa7dbf8aea0eba37cd151ba490c58456873e4c09bbe9d75ed30ea2a9fd3c4d83`. 3 test definitions; 7 assert nodes.
- `test_saved_memory_rows_reads_result_metadata` at line 12; asserts 1, raises contexts 0.
- `test_retrieved_memory_rows_falls_back_to_trace_metadata` at line 18; asserts 1, raises contexts 0.
- `test_orchestration_trace_is_bounded_and_contains_no_evidence_text` at line 27; asserts 5, raises contexts 0.

## TS-014 — `tests/test_chat_end_action.py`

SHA-256 `4a8add1ed678660c22fc84e7cc93eb0123a11fb4723542c34c2c40b79d1e0e3a`. 16 test definitions; 58 assert nodes.
- `test_chat_end_success_processes_memory_then_marks_inactive` at line 110; asserts 5, raises contexts 0.
- `test_chat_end_failure_keeps_chat_active` at line 129; asserts 2, raises contexts 1.
- `test_empty_chat_is_a_successful_noop_and_becomes_inactive` at line 144; asserts 3, raises contexts 0.
- `test_chat_end_is_idempotent_for_already_inactive_chat` at line 161; asserts 4, raises contexts 0.
- `test_process_all_for_chat_end_uses_bounded_batches` at line 176; asserts 4, raises contexts 0.
- `test_rejected_chat_end_batch_remains_pending_and_chat_stays_active` at line 207; asserts 2, raises contexts 1.
- `test_assistant_only_batch_is_processed_as_valid_noop` at line 236; asserts 3, raises contexts 0.
- `test_no_valid_memories_is_processed_as_valid_noop` at line 255; asserts 3, raises contexts 0.
- `test_chat_end_marks_inactive_after_valid_noop` at line 278; asserts 2, raises contexts 0; decorators `pytest.mark.parametrize('rejection_reason', ['no_user_messages', 'langmem_no_valid_memories'])`.
- `test_updater_exception_keeps_chat_active_and_message_pending` at line 298; asserts 2, raises contexts 1.
- `test_chat_end_finalizes_pending_previous_chat_gist_segments` at line 316; asserts 7, raises contexts 0.
- `test_chat_end_assistant_only_gist_batch_is_valid_noop` at line 357; asserts 5, raises contexts 0.
- `test_gist_finalization_failure_keeps_chat_active_without_partial_gist` at line 376; asserts 3, raises contexts 1.
- `test_repeated_chat_end_does_not_duplicate_previous_chat_gists` at line 399; asserts 4, raises contexts 0.
- `test_semantically_processed_messages_still_finalize_as_gist` at line 423; asserts 3, raises contexts 0.
- `test_finalized_previous_chat_gist_reaches_context_packet` at line 446; asserts 6, raises contexts 0.

## TS-015 — `tests/test_chat_fork_action.py`

SHA-256 `661945b6246440e8e1942dd4516adb566a0110dadae7ddd084521db7e15e5512`. 7 test definitions; 41 assert nodes.
- `test_fork_empty_chat_creates_active_copy_and_preserves_original` at line 71; asserts 7, raises contexts 0.
- `test_fork_copies_messages_with_new_ids_and_preserves_order` at line 92; asserts 6, raises contexts 0.
- `test_pending_inherited_messages_are_not_semantically_reprocessed` at line 122; asserts 6, raises contexts 0.
- `test_post_fork_messages_remain_semantically_processable` at line 151; asserts 8, raises contexts 0.
- `test_fork_remaps_gist_provenance_without_copying_legacy_memory` at line 198; asserts 9, raises contexts 0.
- `test_fork_rolls_back_if_provenance_cannot_be_remapped` at line 257; asserts 4, raises contexts 1.
- `test_fork_missing_chat_raises_clear_error_without_partial_chat` at line 278; asserts 1, raises contexts 1.

## TS-016 — `tests/test_chat_gist_summarizer.py`

SHA-256 `12f679fdf77331086c5b4451e2ee9d7b3ad3b132f9ac56b82bf437765777b89d`. 13 test definitions; 69 assert nodes.
- `test_no_gist_created_if_not_enough_messages` at line 63; asserts 5, raises contexts 0.
- `test_older_messages_are_gist_processed_and_latest_recent_messages_are_kept` at line 84; asserts 18, raises contexts 0.
- `test_latest_user_message_is_not_summarized_even_with_small_recent_window` at line 126; asserts 4, raises contexts 0.
- `test_messages_are_not_marked_summarized_if_insert_fails` at line 152; asserts 3, raises contexts 1.
- `test_empty_gist_is_rejected_without_marking_messages` at line 173; asserts 5, raises contexts 0.
- `test_no_model_or_extractor_skips_without_side_effects` at line 194; asserts 3, raises contexts 0.
- `test_structured_summarized_messages_remain_eligible_for_gist` at line 212; asserts 4, raises contexts 0.
- `test_gist_processing_does_not_mark_structured_memory_summarized` at line 236; asserts 3, raises contexts 0.
- `test_current_chat_gist_processor_is_disabled_by_default` at line 258; asserts 4, raises contexts 0.
- `test_repeated_current_chat_gist_batch_does_not_duplicate_processed_span` at line 282; asserts 5, raises contexts 0.
- `test_current_chat_gist_is_not_routed_into_default_context` at line 307; asserts 3, raises contexts 0.
- `test_chat_end_finalizes_only_messages_pending_after_rolling_gist` at line 350; asserts 8, raises contexts 0.
- `test_parse_gist_summary_accepts_valid_json_and_rejects_transcripts` at line 389; asserts 4, raises contexts 0.

## TS-017 — `tests/test_chat_lifecycle.py`

SHA-256 `566125ab387230dccfa3028abc0bfbfa463fff11d450185fc9a64820e99ea940`. 3 test definitions; 12 assert nodes.
- `test_new_chats_are_active_and_can_transition_lifecycle` at line 9; asserts 7, raises contexts 0.
- `test_list_chats_still_includes_inactive_chats` at line 35; asserts 1, raises contexts 0.
- `test_existing_database_migrates_active_column_idempotently` at line 46; asserts 4, raises contexts 0.

## TS-018 — `tests/test_chat_service_file_uploads.py`

SHA-256 `4a180cc3dfcc5bbb17000ab5e300af7099186e94b289dd649b4be607ed59dde2`. 4 test definitions; 17 assert nodes.
- `test_chat_service_indexes_uploaded_file_through_configured_indexer` at line 41; asserts 7, raises contexts 0.
- `test_chat_service_uses_display_name_for_chainlit_temp_upload` at line 65; asserts 6, raises contexts 0.
- `test_chat_service_titles_chat_from_first_message` at line 88; asserts 2, raises contexts 0.
- `test_chat_service_can_start_chat_with_existing_thread_id` at line 106; asserts 2, raises contexts 0.

## TS-019 — `tests/test_chroma_document_store.py`

SHA-256 `04d6a3d82025f6c08001e76ab5e4c0c08dac2ea82a08012df1cd86155c6babd4`. 4 test definitions; 19 assert nodes.
- `test_chroma_is_persistent_global_document_store_without_sqlite_side_effects` at line 74; asserts 13, raises contexts 0.
- `test_clean_database_never_creates_legacy_document_tables` at line 157; asserts 2, raises contexts 0.
- `test_repeated_stable_document_id_does_not_duplicate_logical_chunks` at line 167; asserts 2, raises contexts 0.
- `test_existing_database_drops_legacy_document_tables_and_preserves_live_rows` at line 190; asserts 2, raises contexts 0.

## TS-020 — `tests/test_context_builder.py`

SHA-256 `c5564624af2cc8d8242e6b90d64b659250131f1286c28c9d468e0e0023e0dd91`. 11 test definitions; 60 assert nodes.
- `test_context_builder_respects_budgets_and_records_drops` at line 49; asserts 14, raises contexts 0.
- `test_context_builder_orders_structured_before_recent_and_latest_last` at line 103; asserts 5, raises contexts 0.
- `test_context_builder_formats_retrieved_sections_between_structured_and_recent` at line 147; asserts 8, raises contexts 0.
- `test_context_builder_orders_recent_messages_chronologically_not_by_rank` at line 198; asserts 2, raises contexts 0.
- `test_context_builder_excludes_latest_user_message_from_recent_candidates` at line 241; asserts 5, raises contexts 0.
- `test_recent_budget_retains_newest_fitting_suffix_in_chronological_order` at line 288; asserts 3, raises contexts 0.
- `test_recent_suffix_drops_older_messages_before_newer_messages` at line 336; asserts 3, raises contexts 0.
- `test_only_newest_prior_recent_message_fits_with_current_turn_separate` at line 383; asserts 3, raises contexts 0.
- `test_no_prior_recent_message_fits_but_current_turn_remains_once` at line 431; asserts 4, raises contexts 0.
- `test_context_builder_detects_overflow_and_drops_low_ranked_non_recent` at line 468; asserts 8, raises contexts 0.
- `test_context_builder_records_overflow_when_recent_and_latest_still_exceed_limit` at line 521; asserts 5, raises contexts 0.

## TS-021 — `tests/test_context_comparator.py`

SHA-256 `03bf791229cecf73fde96ed9bd947e90109de2a1d49b6f0cd01db129b1b5472f`. 4 test definitions; 12 assert nodes.
- `test_context_comparator_detects_missing_latest_user_query` at line 30; asserts 3, raises contexts 0.
- `test_context_comparator_detects_missing_recent_messages` at line 47; asserts 3, raises contexts 0.
- `test_context_comparator_detects_missing_structured_memory` at line 68; asserts 3, raises contexts 0.
- `test_context_comparator_detects_large_token_count_difference` at line 86; asserts 3, raises contexts 0.

## TS-022 — `tests/test_context_manager_agent.py`

SHA-256 `97062be8964f9b65c9f575c57fc36e1c344a1c8760fe7db98d0aa7dc0ad11fc3`. 5 test definitions; 20 assert nodes.
- `test_context_manager_agent_preserves_direct_candidate_content_and_formatting` at line 31; asserts 3, raises contexts 0.
- `test_context_manager_agent_records_trace_metadata` at line 77; asserts 6, raises contexts 0.
- `test_production_previous_chat_route_reaches_context_packet` at line 113; asserts 6, raises contexts 0.
- `test_disabled_candidate_source_receives_no_budget` at line 165; asserts 2, raises contexts 0.
- `test_candidate_fallback_budget_stays_within_allocatable_limit` at line 191; asserts 3, raises contexts 0.

## TS-023 — `tests/test_current_chat_span_retriever.py`

SHA-256 `135138e6eaa7fc8cf4cf7bf413d5a12c50239872067380a3c005cce079aa5c32`. 8 test definitions; 38 assert nodes.
- `test_old_same_chat_fact_reaches_context_packet_outside_recent_window` at line 50; asserts 8, raises contexts 0.
- `test_exact_quote_comes_from_raw_current_chat_messages` at line 101; asserts 6, raises contexts 0.
- `test_current_chat_span_never_reads_other_chats` at line 132; asserts 4, raises contexts 0.
- `test_current_user_query_is_excluded_from_span_and_context` at line 157; asserts 3, raises contexts 0.
- `test_span_expands_around_hit_in_chronological_order` at line 187; asserts 5, raises contexts 0.
- `test_overlapping_hit_windows_are_merged` at line 219; asserts 3, raises contexts 0.
- `test_current_chat_span_is_disabled_by_default_but_works_when_enabled` at line 246; asserts 3, raises contexts 0.
- `test_oversized_span_is_dropped_without_exceeding_context_budget` at line 272; asserts 6, raises contexts 0.

## TS-024 — `tests/test_direct_raw_retrieval.py`

SHA-256 `0627acb0977b3076c79ff3f54da17cb969ea838a0d528e191f1cd16aa59d88d5`. 6 test definitions; 17 assert nodes.
- `test_direct_raw_finds_fact_omitted_from_gist` at line 27; asserts 5, raises contexts 0.
- `test_direct_raw_order_and_limit_are_deterministic` at line 60; asserts 2, raises contexts 0.
- `test_direct_raw_respects_explicit_chat_scope` at line 82; asserts 3, raises contexts 0.
- `test_global_summary_exposes_complete_timeline_beyond_focused_limit` at line 110; asserts 4, raises contexts 0.
- `test_explicit_raw_span_rejects_chat_outside_scope` at line 142; asserts 1, raises contexts 0.
- `test_gist_and_direct_duplicate_merge_retrieval_paths` at line 165; asserts 2, raises contexts 0.

## TS-025 — `tests/test_document_ingestion_agent.py`

SHA-256 `3ea6cff3a250b8240bf19728aae043f024c31a2431e16472db440d5e170d2619`. 4 test definitions; 20 assert nodes.
- `test_document_ingestion_agent_indexes_file_with_structured_result` at line 41; asserts 11, raises contexts 0.
- `test_document_ingestion_agent_preserves_display_name_for_temp_upload` at line 64; asserts 6, raises contexts 0.
- `test_document_ingestion_agent_accepts_object_index_result` at line 82; asserts 3, raises contexts 0.
- `test_document_ingestion_agent_propagates_loader_errors` at line 95; asserts 0, raises contexts 1.

## TS-026 — `tests/test_document_inspection.py`

SHA-256 `5f2fe8c8882ff852a419740a049cfaf3dd4207e3aac5d1be7a5b7ba79585e2bd`. 3 test definitions; 13 assert nodes.
- `test_rows_from_chroma_metadata_group_by_document_id` at line 10; asserts 6, raises contexts 0.
- `test_format_document_inspection_rows_is_cli_readable` at line 52; asserts 6, raises contexts 0.
- `test_format_document_inspection_rows_handles_empty_rows` at line 76; asserts 1, raises contexts 0.

## TS-027 — `tests/test_document_loaders.py`

SHA-256 `ddc59fa3f4c5265953ec5260ecb78d8fbb27e7bedfa309f5f3c6fbe1622fa1fa`. 10 test definitions; 34 assert nodes.
- `test_txt_loader_preserves_text_and_metadata` at line 70; asserts 7, raises contexts 0.
- `test_markdown_loader_preserves_text_and_metadata` at line 85; asserts 4, raises contexts 0.
- `test_loader_uses_display_name_for_chainlit_bin_upload` at line 97; asserts 5, raises contexts 0.
- `test_unsupported_extension_raises_clear_error` at line 110; asserts 0, raises contexts 1.
- `test_missing_file_raises_clear_error` at line 118; asserts 0, raises contexts 1.
- `test_index_loaded_document_uses_existing_indexing_api` at line 123; asserts 2, raises contexts 0.
- `test_index_file_document_loads_then_indexes` at line 145; asserts 4, raises contexts 0.
- `test_index_file_document_accepts_display_name_for_temp_upload` at line 158; asserts 4, raises contexts 0.
- `test_loaded_file_indexes_and_retrieves_document_memory_candidate` at line 171; asserts 6, raises contexts 0.
- `test_pdf_loader_skips_when_pdf_dependency_unavailable` at line 195; asserts 2, raises contexts 0.

## TS-028 — `tests/test_document_memory.py`

SHA-256 `c421ae7671f155d1e11407b43f10383fcca12cfe625a2855334e749108b47445`. 6 test definitions; 24 assert nodes.
- `test_split_text_into_chunks_preserves_paragraphs` at line 45; asserts 3, raises contexts 0.
- `test_custom_splitter_returns_chunk_metadata` at line 55; asserts 7, raises contexts 0.
- `test_langchain_splitter_adapter_works_when_installed` at line 70; asserts 5, raises contexts 0.
- `test_langchain_splitter_falls_back_to_custom_when_unavailable` at line 87; asserts 4, raises contexts 0.
- `test_document_retrieval_flows_through_dispatcher_when_enabled` at line 104; asserts 2, raises contexts 0.
- `test_document_candidates_reach_context_packet_document_section` at line 126; asserts 3, raises contexts 0.

## TS-029 — `tests/test_document_product_lifecycle.py`

SHA-256 `86311f80b248fd0f6a4ea787c7c7ffefae40c3c1d2b5de54bf193b3f18f755ed`. 15 test definitions; 34 assert nodes.
- `test_document_lifecycle_and_chat_association_survive_reload` at line 86; asserts 1, raises contexts 0.
- `test_document_association_is_persisted_after_indexing_reaches_ready` at line 100; asserts 2, raises contexts 0.
- `test_same_turn_attachment_forces_scoped_retrieval_without_duplicate_user_message` at line 139; asserts 8, raises contexts 0.
- `test_index_failure_persists_failed_state_and_never_ready` at line 192; asserts 3, raises contexts 1.
- `test_document_retrieval_is_scoped_to_current_chat` at line 210; asserts 2, raises contexts 0.
- `test_explicit_filename_and_ambiguity_resolution` at line 239; asserts 1, raises contexts 1.
- `test_empty_explicit_document_scope_never_searches_all_documents` at line 253; asserts 2, raises contexts 0.
- `test_retriever_exception_is_captured_without_false_evidence` at line 281; asserts 2, raises contexts 0.
- `test_repeated_database_initialization_is_idempotent_upgrade` at line 310; asserts 3, raises contexts 0.
- `test_document_association_foreign_keys_are_enforced` at line 351; asserts 0, raises contexts 2.
- `test_duplicate_upload_operation_reuses_exact_ready_document` at line 363; asserts 3, raises contexts 0.
- `test_retry_after_failed_indexing_reuses_document_identity` at line 387; asserts 3, raises contexts 1.
- `test_ready_update_failure_leaves_truthful_indexing_state` at line 412; asserts 1, raises contexts 1.
- `test_ready_document_without_candidates_returns_no_false_evidence` at line 438; asserts 2, raises contexts 0.
- `test_scoped_retrieval_rejects_chunks_with_incomplete_metadata` at line 476; asserts 1, raises contexts 0.

## TS-030 — `tests/test_document_qa_answer_generation.py`

SHA-256 `0070220e6715d6ab70a86c7c1ed85273f501956198e89f7fed8841b3c986e3f5`. 4 test definitions; 10 assert nodes.
- `test_grounded_qa_prompt_requires_context_only_answer` at line 10; asserts 5, raises contexts 0.
- `test_format_contexts_numbers_contexts` at line 23; asserts 1, raises contexts 0.
- `test_format_contexts_handles_empty_contexts` at line 27; asserts 1, raises contexts 0.
- `test_answer_is_unknown_detects_declines` at line 31; asserts 3, raises contexts 0.

## TS-031 — `tests/test_document_qa_compare.py`

SHA-256 `fe4bdf34eb0800a4dab8de8fe7d35d4aedcbac5058f184cb562175b402e0db95`. 5 test definitions; 26 assert nodes.
- `test_aggregate_mode_results_computes_rates_and_failed_cases` at line 44; asserts 11, raises contexts 0.
- `test_comparison_row_marks_skipped_mode_with_reason` at line 66; asserts 4, raises contexts 0.
- `test_format_row_uses_fixed_width_columns` at line 92; asserts 1, raises contexts 0.
- `test_result_to_dict_is_json_ready` at line 98; asserts 5, raises contexts 0.
- `test_model_answer_mode_uses_answer_generator` at line 134; asserts 5, raises contexts 0.

## TS-032 — `tests/test_document_qa_diagnostics.py`

SHA-256 `d28eccc8ec61246f3530f4a992e6c8d45931210fb8e1de9a1dc7401e6fed344d`. 1 test definitions; 7 assert nodes.
- `test_diagnose_rows_reports_duplicates_and_anchor_position` at line 6; asserts 7, raises contexts 0.

## TS-033 — `tests/test_document_qa_langchain_baseline.py`

SHA-256 `3f5372045032d92e84147ffe5d887d79e58924794a412c1eaee7834d42feef66`. 4 test definitions; 16 assert nodes.
- `test_load_baseline_cases_supports_limit` at line 16; asserts 2, raises contexts 0.
- `test_split_unique_documents_deduplicates_identical_texts` at line 47; asserts 3, raises contexts 0.
- `test_aggregate_results_computes_rates_and_failed_cases` at line 70; asserts 6, raises contexts 0.
- `test_skipped_summary_and_json_output_are_stable` at line 101; asserts 5, raises contexts 0.

## TS-034 — `tests/test_document_qa_metrics.py`

SHA-256 `0a5b9d247686654e125878700b293f201eab119816a601db85e3558fbee73cbd`. 3 test definitions; 13 assert nodes.
- `test_answer_metrics_are_case_and_whitespace_insensitive` at line 12; asserts 3, raises contexts 0.
- `test_context_metrics_check_any_context` at line 20; asserts 3, raises contexts 0.
- `test_ragas_compatible_row_shape` at line 34; asserts 7, raises contexts 0.

## TS-035 — `tests/test_document_qa_prepare.py`

SHA-256 `f9e9a8e9a36383b5ea1f800b4ebfa557c7384584d4d63dbbb5dc1b51a91ddaff`. 2 test definitions; 1 assert nodes.
- `test_squad_example_to_row_maps_required_fields` at line 8; asserts 1, raises contexts 0.
- `test_squad_example_to_row_rejects_missing_answers` at line 35; asserts 0, raises contexts 1.

## TS-036 — `tests/test_document_qa_prepare_nq.py`

SHA-256 `a15e009b171a98ec961cefb96e3e2a237f3234647e042a171f34c22f7c090725`. 9 test definitions; 17 assert nodes.
- `test_nq_example_to_row_converts_valid_example` at line 26; asserts 9, raises contexts 0.
- `test_nq_example_to_row_handles_natural_questions_short_shape` at line 45; asserts 3, raises contexts 0.
- `test_nq_example_to_row_skips_missing_question` at line 72; asserts 0, raises contexts 1.
- `test_nq_example_to_row_skips_missing_context` at line 80; asserts 0, raises contexts 1.
- `test_nq_example_to_row_skips_missing_answer` at line 88; asserts 0, raises contexts 1.
- `test_nq_example_to_row_skips_answer_not_in_context_when_required` at line 96; asserts 0, raises contexts 1.
- `test_nq_example_allows_answer_not_in_context_when_not_required` at line 110; asserts 1, raises contexts 0.
- `test_evidence_for_answer_returns_excerpt_around_anchor` at line 125; asserts 2, raises contexts 0.
- `test_convert_dataset_counts_written_and_skipped_examples` at line 134; asserts 2, raises contexts 0.

## TS-037 — `tests/test_document_qa_ragas_export.py`

SHA-256 `67a67356b83244d6a6157bd99cb8cb208ce34436577c9945994e1e357268adcf`. 3 test definitions; 21 assert nodes.
- `test_result_to_ragas_row_adds_required_fields_and_metadata` at line 56; asserts 15, raises contexts 0.
- `test_results_to_ragas_rows_preserves_alignment` at line 83; asserts 3, raises contexts 0.
- `test_write_ragas_jsonl_writes_without_ragas_dependency` at line 97; asserts 3, raises contexts 0.

## TS-038 — `tests/test_document_qa_topk_curves.py`

SHA-256 `6cb871074637b3566f8f71f279d3a3576242d5a55aaa81e3bf75fac5fe999589`. 5 test definitions; 18 assert nodes.
- `test_normalized_top_k_values_keeps_positive_unique_values` at line 34; asserts 1, raises contexts 0.
- `test_topk_result_from_comparison_copies_retrieval_metrics` at line 38; asserts 8, raises contexts 0.
- `test_backend_for_mode_labels_chroma_only` at line 54; asserts 2, raises contexts 0.
- `test_topk_row_and_json_output_are_stable` at line 59; asserts 2, raises contexts 0.
- `test_evaluate_topk_curves_aggregates_modes_and_k_values` at line 86; asserts 5, raises contexts 0.

## TS-039 — `tests/test_dynamic_memory_budget.py`

SHA-256 `a00e61dfb89317feb8ba46f6ef33d2f283c67e38d43e35453a14824dee680f3e`. 11 test definitions; 38 assert nodes.
- `test_route_specific_caps` at line 142; asserts 3, raises contexts 0; decorators `pytest.mark.parametrize(('route_plan', 'expected_cap', 'expected_reason'), [(route(('recent_messages',)), 4096, 'base_recent_or_general'), (route(('structured_m`.
- `test_required_floor_smaller_than_base_does_not_shrink_base` at line 158; asserts 2, raises contexts 0.
- `test_memory_recall_profile_uses_moderate_requested_budget` at line 169; asserts 2, raises contexts 0.
- `test_global_summary_profile_uses_large_budget_with_explicit_reserve` at line 183; asserts 4, raises contexts 0.
- `test_global_summary_budget_never_consumes_reserved_hard_headroom` at line 199; asserts 2, raises contexts 0.
- `test_required_floor_larger_than_base_expands_working_budget` at line 219; asserts 3, raises contexts 0.
- `test_required_floor_can_exceed_route_cap_but_not_available_budget` at line 231; asserts 4, raises contexts 0.
- `test_optional_selection_stops_below_configured_utility` at line 250; asserts 3, raises contexts 0.
- `test_manager_reports_missing_and_oversized_required_evidence` at line 269; asserts 5, raises contexts 0.
- `test_explicit_document_synthesis_can_use_more_than_base_budget` at line 320; asserts 4, raises contexts 0.
- `test_context_profiles_reach_final_packet_without_hidden_4096_cap` at line 359; asserts 6, raises contexts 0.

## TS-040 — `tests/test_e2e_scenarios.py`

SHA-256 `44029b0685939fc03f023898dfeb7f5957ed7c9fe5781799b575fb52568b627b`. 6 test definitions; 32 assert nodes.
- `test_e2e_scenario_dataset_loads_controlled_cases` at line 18; asserts 2, raises contexts 0.
- `test_mock_e2e_document_scenario_runs_real_coordinator` at line 31; asserts 9, raises contexts 0.
- `test_e2e_abstain_scenario_avoids_forbidden_claims` at line 55; asserts 3, raises contexts 0.
- `test_model_mode_accepts_injected_fake_model_without_network` at line 69; asserts 3, raises contexts 0.
- `test_e2e_report_export_schema` at line 84; asserts 6, raises contexts 0.
- `test_all_mock_e2e_scenarios_pass` at line 101; asserts 9, raises contexts 0.

## TS-041 — `tests/test_evidence_constrained_selector.py`

SHA-256 `e3dbb82fb33ca728feb39318243d11e09faec3eade154df68ba1268632392523`. 17 test definitions; 37 assert nodes.
- `test_rank_one_raw_regressions_fit_global_budget` at line 114; asserts 4, raises contexts 0; decorators `pytest.mark.parametrize('case', ['q5', 'q11', 'q17', 'q19'])`.
- `test_required_document_and_current_chat_are_both_admitted` at line 145; asserts 2, raises contexts 0.
- `test_required_document_and_previous_chat_are_both_admitted` at line 169; asserts 2, raises contexts 0.
- `test_selected_raw_child_folds_parent_gist` at line 195; asserts 2, raises contexts 0.
- `test_parent_gist_remains_when_raw_child_does_not_fit` at line 220; asserts 1, raises contexts 0.
- `test_identical_candidates_are_deduplicated` at line 241; asserts 2, raises contexts 0.
- `test_highly_overlapping_spans_only_consume_budget_once` at line 268; asserts 4, raises contexts 0.
- `test_overlap_below_threshold_keeps_both_spans` at line 302; asserts 1, raises contexts 0.
- `test_unique_anchor_prevents_overlap_from_discarding_distinct_evidence` at line 328; asserts 1, raises contexts 0.
- `test_global_summary_includes_complete_history_when_it_fits` at line 356; asserts 3, raises contexts 0.
- `test_global_summary_oversized_history_covers_beginning_middle_and_end` at line 389; asserts 3, raises contexts 0.
- `test_global_summary_time_range_count_matches_disjoint_selected_ranges` at line 422; asserts 2, raises contexts 0.
- `test_optional_candidates_share_global_pool_and_disabled_sources_are_excluded` at line 456; asserts 1, raises contexts 0.
- `test_recent_messages_preserve_newest_contiguous_suffix` at line 471; asserts 2, raises contexts 0.
- `test_missing_required_evidence_is_reported` at line 499; asserts 2, raises contexts 0.
- `test_context_manager_respects_working_and_hard_budgets` at line 511; asserts 2, raises contexts 0.
- `test_native_and_langgraph_use_same_budget_policy_selector_and_read_only_graph` at line 577; asserts 3, raises contexts 0.

## TS-042 — `tests/test_final_eval_wrappers.py`

SHA-256 `708cbb31b0887a90b5edc126f027dc3ead9507566a9fac4818c17ea260aa87de`. 16 test definitions; 75 assert nodes.
- `test_fresh_run_directories_are_distinct_and_never_reused` at line 70; asserts 7, raises contexts 0.
- `test_explicit_resume_rejects_completed_or_unrelated_directories` at line 94; asserts 4, raises contexts 0.
- `test_explicit_resume_accepts_only_incomplete_compatible_run` at line 123; asserts 1, raises contexts 0.
- `test_answer_wrapper_has_no_implicit_pointer_resume` at line 141; asserts 7, raises contexts 0.
- `test_answer_wrapper_hf_defaults_and_check_mode_are_safe` at line 152; asserts 9, raises contexts 0.
- `test_online_mode_unsets_offline_values_loaded_from_environment` at line 167; asserts 2, raises contexts 0.
- `test_online_mode_prevents_python_from_reloading_offline_dotenv_values` at line 181; asserts 1, raises contexts 0.
- `test_combined_real_run_child_receives_offline_variables_unset` at line 200; asserts 2, raises contexts 0.
- `test_answer_run_validator_accepts_complete_and_rejects_incomplete` at line 261; asserts 5, raises contexts 0.
- `test_judge_requires_exact_answer_path_and_writes_separate_copy` at line 304; asserts 9, raises contexts 0.
- `test_combined_launcher_is_sequential_and_stops_on_answer_failure` at line 317; asserts 6, raises contexts 0.
- `test_combined_records_answer_failure_and_never_invokes_judge` at line 331; asserts 5, raises contexts 0.
- `test_zero_exit_with_missing_results_fails_cleanly_without_judge` at line 362; asserts 6, raises contexts 0.
- `test_combined_waits_for_answer_and_hands_exact_path_to_judge` at line 414; asserts 4, raises contexts 0.
- `test_validator_missing_results_has_no_traceback` at line 483; asserts 3, raises contexts 0.
- `test_unknown_arguments_fail_clearly` at line 515; asserts 2, raises contexts 0; decorators `pytest.mark.parametrize(('script', 'expected'), [(ANSWER_SCRIPT, 'unknown argument: --not-a-real-option'), (JUDGE_SCRIPT, 'unknown argument: --not-a-real-option`.

## TS-043 — `tests/test_generated_answer_eval.py`

SHA-256 `91955c5f9b20f2081f2ed9853b9f04c6452cde6742d08305aedcbace02dda078`. 6 test definitions; 24 assert nodes.
- `test_generated_answer_dataset_loads_adapter_ready_cases` at line 29; asserts 3, raises contexts 0.
- `test_mock_eval_passes_controlled_dataset` at line 44; asserts 8, raises contexts 0.
- `test_abstain_case_requires_unknown_answer` at line 58; asserts 4, raises contexts 0.
- `test_forbidden_claim_is_reported` at line 73; asserts 3, raises contexts 0.
- `test_model_mode_uses_injected_fake_generator` at line 103; asserts 2, raises contexts 0.
- `test_replay_answers_and_report_export` at line 129; asserts 4, raises contexts 0.

## TS-044 — `tests/test_gist_memory_infrastructure.py`

SHA-256 `130d91aa7b0677cdc1a797bbd18b52197e73d55e73a272be2154cc021d9e2295`. 11 test definitions; 52 assert nodes.
- `test_memory_source_labels_include_gist_sources` at line 16; asserts 4, raises contexts 0.
- `test_insert_and_read_chat_gists` at line 34; asserts 7, raises contexts 0.
- `test_fetch_raw_messages_by_message_id_span` at line 62; asserts 3, raises contexts 0.
- `test_gist_retrievers_return_empty_when_no_gists_exist` at line 80; asserts 2, raises contexts 0.
- `test_current_chat_gist_retriever_returns_candidate_metadata` at line 97; asserts 8, raises contexts 0.
- `test_previous_chat_gist_retriever_reads_by_source_type` at line 132; asserts 4, raises contexts 0.
- `test_raw_message_span_retriever_returns_source_messages_from_gist_span` at line 157; asserts 8, raises contexts 0.
- `test_raw_message_span_retriever_accepts_direct_span_filters` at line 192; asserts 3, raises contexts 0.
- `test_raw_message_span_retriever_accepts_alias_span_filters` at line 215; asserts 3, raises contexts 0.
- `test_raw_message_span_retriever_truncates_long_spans` at line 239; asserts 4, raises contexts 0.
- `test_raw_message_span_plan_can_be_derived_from_gist_candidate` at line 263; asserts 6, raises contexts 0.

## TS-045 — `tests/test_gist_processing_state.py`

SHA-256 `feaeb61a2fe68f3daa5b8c6ba42d255bdb1479d0598d07e980c188fd7ddf4998`. 1 test definitions; 4 assert nodes.
- `test_gist_processed_schema_migration_is_idempotent` at line 9; asserts 4, raises contexts 0.

## TS-046 — `tests/test_gist_raw_span_expansion.py`

SHA-256 `193a35168bd16d355c6d49c3ddc7f416746ca317dfbffad0c40f42cc476e264a`. 11 test definitions; 60 assert nodes.
- `test_finalized_previous_gist_expands_to_exact_raw_context` at line 46; asserts 10, raises contexts 0.
- `test_exact_quote_query_reranks_expanded_raw_span_above_gist` at line 106; asserts 3, raises contexts 0.
- `test_missing_gist_provenance_keeps_orientation_without_malformed_span` at line 145; asserts 2, raises contexts 0.
- `test_large_gist_range_expansion_is_query_centered_and_bounded` at line 161; asserts 7, raises contexts 0.
- `test_overlapping_gist_expansions_merge_and_preserve_parent_links` at line 200; asserts 4, raises contexts 0.
- `test_small_provenance_includes_all_messages_with_diagnostics` at line 241; asserts 7, raises contexts 0.
- `test_large_provenance_selects_near_end_query_anchor_and_neighbors` at line 282; asserts 9, raises contexts 0.
- `test_adjacent_gists_keep_independent_query_centered_windows` at line 327; asserts 6, raises contexts 0.
- `test_window_diagnostics_are_bounded` at line 419; asserts 4, raises contexts 0.
- `test_current_gist_expands_only_when_source_is_explicitly_enabled` at line 448; asserts 4, raises contexts 0.
- `test_expansion_respects_tight_context_budget` at line 495; asserts 4, raises contexts 0.

## TS-047 — `tests/test_langchain_chroma_retriever.py`

SHA-256 `a090a148d6d3f951877ca56b17c60bbaebf12eef1c787a5cb945ce716ea27621`. 3 test definitions; 12 assert nodes.
- `test_langchain_document_to_memory_candidate_preserves_metadata` at line 38; asserts 9, raises contexts 0.
- `test_langchain_chroma_retriever_falls_back_when_unavailable` at line 63; asserts 2, raises contexts 0.
- `test_dispatcher_selects_langchain_chroma_by_default` at line 80; asserts 1, raises contexts 0.

## TS-048 — `tests/test_langgraph_demo_regression.py`

SHA-256 `56983faa896753c62aa524f68d5ab6b6d851f13d359a907d0b5511acd2849916`. 1 test definitions; 9 assert nodes.
- `test_compact_cross_chat_document_and_casual_demo_regression` at line 64; asserts 9, raises contexts 0.

## TS-049 — `tests/test_langgraph_memory_pipeline.py`

SHA-256 `1137d8a431084589debb2e4f4277f8ead20f3a96d72aa3cf72a493609dd0afff`. 8 test definitions; 48 assert nodes.
- `test_exact_quote_with_current_raw_span_passes_contract` at line 82; asserts 6, raises contexts 0.
- `test_gist_only_fails_exact_quote_contract` at line 119; asserts 5, raises contexts 0.
- `test_previous_gist_expands_to_exact_raw_span` at line 148; asserts 6, raises contexts 0.
- `test_spike_remains_explicit_and_default_off` at line 194; asserts 2, raises contexts 0.
- `test_trace_is_bounded_and_graph_has_no_write_nodes` at line 201; asserts 9, raises contexts 0.
- `test_semantic_router_exact_quote_reaches_current_raw_span` at line 240; asserts 11, raises contexts 0.
- `test_semantic_router_exact_quote_fails_closed_with_gist_only` at line 289; asserts 5, raises contexts 0.
- `test_semantic_router_required_scopes_are_visible_in_graph_trace` at line 330; asserts 4, raises contexts 0.

## TS-050 — `tests/test_langmem_structured_memory.py`

SHA-256 `f9612e4d0828411e8e6bb81550b569cb3a801143e73f38867e342a45ef4463b1`. 8 test definitions; 21 assert nodes.
- `test_langmem_outputs_map_to_current_memory_record_shape` at line 44; asserts 1, raises contexts 0.
- `test_langmem_normalization_rejects_invalid_category_and_transcript` at line 74; asserts 1, raises contexts 0.
- `test_langmem_normalization_attaches_supported_source_ids_when_missing` at line 97; asserts 3, raises contexts 0.
- `test_short_term_memory_uses_langmem_backend_and_stores_memory` at line 119; asserts 7, raises contexts 0.
- `test_empty_langmem_output_does_not_mark_messages_summarized` at line 176; asserts 3, raises contexts 0.
- `test_langmem_update_preserves_existing_memory_records` at line 200; asserts 2, raises contexts 0.
- `test_processed_messages_marked_only_after_successful_storage` at line 251; asserts 2, raises contexts 0.
- `test_failed_langmem_update_does_not_mark_messages` at line 282; asserts 2, raises contexts 0.

## TS-051 — `tests/test_long_term_memory_vector_retrieval.py`

SHA-256 `1560b7268a7b0e96dfd3208a7f859e03af3a375efdf95d00e632ce9391cf4767`. 5 test definitions; 20 assert nodes.
- `test_memory_record_to_index_text_is_compact_and_semantic` at line 63; asserts 3, raises contexts 0.
- `test_long_term_memory_vector_index_indexes_memory_records` at line 78; asserts 6, raises contexts 0.
- `test_structured_memory_vector_retrieval_returns_expected_memory` at line 98; asserts 6, raises contexts 0.
- `test_structured_memory_hybrid_retrieval_deduplicates_by_memory_id` at line 126; asserts 2, raises contexts 0.
- `test_structured_memory_vector_retrieval_falls_back_to_sqlite` at line 155; asserts 2, raises contexts 0.

## TS-052 — `tests/test_long_term_store.py`

SHA-256 `ae5e9212c574195df874adbd5ecc8636be8641b0b2e9ec0dd9a4c51b2faa704c`. 4 test definitions; 22 assert nodes.
- `test_sqlite_long_term_store_roundtrip_and_namespace_search` at line 39; asserts 7, raises contexts 0.
- `test_langgraph_in_memory_store_adapter_roundtrip` at line 91; asserts 5, raises contexts 0.
- `test_cross_chat_structured_memory_is_visible_across_chats` at line 114; asserts 7, raises contexts 0.
- `test_chat_memory_state_compatibility_still_reads_legacy_blob` at line 157; asserts 3, raises contexts 0.

## TS-053 — `tests/test_longmemeval_adapter.py`

SHA-256 `64efe2c72ec504a0ba1bf2937af42701961eba1a208437dd4e53c7084e9f92bb`. 10 test definitions; 50 assert nodes.
- `test_fixture_loads_and_normalizes_common_fields` at line 31; asserts 5, raises contexts 0.
- `test_loader_preserves_parallel_official_session_ids` at line 41; asserts 3, raises contexts 0.
- `test_schema_rejects_missing_history` at line 61; asserts 0, raises contexts 1.
- `test_limit_is_applied` at line 72; asserts 1, raises contexts 0.
- `test_scoring_contains_exact_and_abstain` at line 78; asserts 6, raises contexts 0.
- `test_mock_runner_produces_report_without_live_model` at line 100; asserts 18, raises contexts 0.
- `test_recent_only_report_and_json_export` at line 130; asserts 3, raises contexts 0.
- `test_session_history_is_split_into_provenance_spans` at line 145; asserts 5, raises contexts 0.
- `test_span_retrieval_finds_fixture_fact` at line 164; asserts 6, raises contexts 0.
- `test_span_retrieval_mode_uses_raw_message_candidates` at line 186; asserts 3, raises contexts 0.

## TS-054 — `tests/test_longmemeval_answer_eval.py`

SHA-256 `db71548ab00b11daec211bd75382f5b7c32ef8b29a22609ff45b894c11ac6f25`. 8 test definitions; 36 assert nodes.
- `test_manifest_resolves_fixture_case` at line 148; asserts 3, raises contexts 0.
- `test_dry_run_validates_without_writing` at line 157; asserts 4, raises contexts 0.
- `test_judge_only_uses_frozen_answers_without_replay_or_generation` at line 178; asserts 9, raises contexts 0.
- `test_judge_only_rejects_invalid_frozen_answer_sets` at line 253; asserts 0, raises contexts 1; decorators `pytest.mark.parametrize(('mutation', 'expected'), [(lambda rows: [], 'missing LongMemEval answer rows'), (lambda rows: [*rows, dict(rows[0])], 'duplicate LongMe`.
- `test_longmemeval_history_replay_finalizes_each_session_and_preserves_boundaries` at line 284; asserts 13, raises contexts 0.
- `test_empty_message_skipping_preserves_session_boundaries` at line 367; asserts 3, raises contexts 0.
- `test_longmemeval_replay_batches_offline_updates_once_per_session` at line 449; asserts 2, raises contexts 0.
- `test_timestamp_status_prefers_message_then_session_timestamps` at line 505; asserts 2, raises contexts 0.

## TS-055 — `tests/test_mab_answer_eval.py`

SHA-256 `697ff11061e3fc50c98057ce0d95b065ae32253085f6d21c2582b58c97ab2437`. 39 test definitions; 125 assert nodes.
- `test_manifest_parsing_preserves_deterministic_order` at line 213; asserts 2, raises contexts 0.
- `test_manifest_rejects_duplicate_case_ids` at line 220; asserts 0, raises contexts 1.
- `test_case_resolution_rejects_unknown_case` at line 228; asserts 0, raises contexts 1.
- `test_dry_run_makes_no_calls_or_artifact_writes` at line 237; asserts 4, raises contexts 0.
- `test_normalized_token_f1_metric_scores_partial_overlap` at line 259; asserts 3, raises contexts 0.
- `test_banking77_normalization_extracts_single_numeric_label` at line 271; asserts 3, raises contexts 0.
- `test_banking77_normalization_accepts_only_explicit_label_forms` at line 300; asserts 2, raises contexts 0; decorators `pytest.mark.parametrize('prediction', ('50', 'label: 50', 'The answer is label 50'))`.
- `test_banking77_normalization_ignores_unlabelled_explanation_number` at line 317; asserts 3, raises contexts 0.
- `test_banking77_normalization_rejects_conflicting_labels` at line 338; asserts 3, raises contexts 0.
- `test_detectiveqa_normalization_extracts_answer_from_fenced_json` at line 359; asserts 3, raises contexts 0.
- `test_detectiveqa_normalization_extracts_option_from_explanatory_prose` at line 381; asserts 3, raises contexts 0.
- `test_detectiveqa_normalization_accepts_unambiguous_option_forms` at line 411; asserts 2, raises contexts 0; decorators `pytest.mark.parametrize('prediction', ('D', 'The answer is D.', 'D. Charlotte Blacklock'))`.
- `test_detectiveqa_normalization_does_not_guess_from_malformed_json` at line 429; asserts 3, raises contexts 0.
- `test_detectiveqa_normalization_rejects_ambiguous_options` at line 450; asserts 3, raises contexts 0.
- `test_detectiveqa_normalization_rejects_conflicting_json_answer_fields` at line 471; asserts 3, raises contexts 0.
- `test_detectiveqa_normalization_rejects_json_array_mimicking_object_pairs` at line 492; asserts 3, raises contexts 0.
- `test_answer_and_judge_endpoint_configuration_are_independent` at line 513; asserts 6, raises contexts 0.
- `test_judge_client_error_does_not_expose_credentials` at line 539; asserts 1, raises contexts 1.
- `test_answer_execution_uses_existing_answer_agent_and_graph_path` at line 559; asserts 4, raises contexts 0.
- `test_formal_mab_execution_uses_production_updater_not_noop` at line 593; asserts 3, raises contexts 0.
- `test_same_history_is_prepared_once_for_multiple_questions` at line 670; asserts 2, raises contexts 0.
- `test_mab_history_finalization_persists_memory_gist_and_inactive_chat` at line 782; asserts 11, raises contexts 0.
- `test_mab_prepared_snapshot_metadata_reports_structured_memory_skip` at line 829; asserts 4, raises contexts 0.
- `test_result_is_persisted_and_failure_keeps_prior_case` at line 915; asserts 2, raises contexts 0.
- `test_resume_reuses_completed_answer_and_judge` at line 935; asserts 4, raises contexts 0.
- `test_resume_continues_from_failed_case` at line 969; asserts 1, raises contexts 0.
- `test_changing_judge_model_invalidates_only_judge_cache` at line 996; asserts 5, raises contexts 0.
- `test_changing_judge_endpoint_invalidates_only_judge_cache` at line 1030; asserts 7, raises contexts 0.
- `test_changed_answer_invalidates_judge_cache_key` at line 1070; asserts 1, raises contexts 0.
- `test_malformed_judge_output_is_rejected` at line 1092; asserts 0, raises contexts 1.
- `test_empty_judge_output_receives_at_most_one_retry` at line 1097; asserts 3, raises contexts 0.
- `test_judge_allows_one_bounded_repair_attempt` at line 1112; asserts 3, raises contexts 0.
- `test_second_malformed_judge_response_is_not_a_pass` at line 1127; asserts 3, raises contexts 0.
- `test_malformed_judge_is_persisted_as_invalid_not_passing` at line 1142; asserts 5, raises contexts 0.
- `test_official_metric_and_judge_are_persisted_separately` at line 1168; asserts 3, raises contexts 0.
- `test_normalized_metric_keeps_raw_answer_for_storage_judge_and_cache` at line 1190; asserts 6, raises contexts 0.
- `test_compact_summary_and_disagreement_artifacts` at line 1235; asserts 4, raises contexts 0.
- `test_artifacts_do_not_store_secrets_prompts_or_evidence_by_default` at line 1259; asserts 3, raises contexts 0.
- `test_context_pipeline_contract_fields_are_preserved` at line 1286; asserts 4, raises contexts 0.

## TS-056 — `tests/test_memory_agent_bench_adapter.py`

SHA-256 `6c66c31cb4605bf697c3bbe852a1c9aad95306ca9d87c9b7e6129a1e8f5cfa18`. 29 test definitions; 125 assert nodes.
- `test_fixture_parses_normalized_example` at line 177; asserts 5, raises contexts 0.
- `test_official_context_shape_is_chunked_and_question_limited` at line 187; asserts 7, raises contexts 0.
- `test_huggingface_source_filter_is_eval_only_and_accounted` at line 213; asserts 4, raises contexts 0.
- `test_likely_single_evidence_filter_is_conservative_and_reported` at line 249; asserts 4, raises contexts 0.
- `test_selected_ruler_suite_requests_only_qa1_source` at line 286; asserts 6, raises contexts 0.
- `test_selected_test_time_learning_uses_whole_split` at line 306; asserts 3, raises contexts 0.
- `test_selected_suite_output_is_bounded_and_aggregated` at line 320; asserts 11, raises contexts 0.
- `test_context_split_rejects_unreasonably_small_bound` at line 382; asserts 0, raises contexts 1.
- `test_incremental_replay_calls_memory_update_and_session_lifecycle` at line 387; asserts 5, raises contexts 0.
- `test_roleless_history_skips_structured_memory_but_finalizes_gist_and_inactive_chat` at line 402; asserts 10, raises contexts 0.
- `test_multi_session_calls_chat_end_between_sessions` at line 440; asserts 2, raises contexts 0.
- `test_context_evidence_and_provenance_are_reported` at line 450; asserts 8, raises contexts 0.
- `test_comparison_evidence_requires_biographical_facts_for_both_operands` at line 472; asserts 2, raises contexts 0.
- `test_noncomparison_evidence_keeps_literal_diagnostic_contract` at line 501; asserts 1, raises contexts 0.
- `test_literal_answer_without_local_relation_is_not_complete_evidence` at line 509; asserts 2, raises contexts 0.
- `test_mock_answer_mode_is_labeled_honestly` at line 533; asserts 6, raises contexts 0.
- `test_cross_encoder_ablation_is_explicit_and_traceable` at line 545; asserts 5, raises contexts 0.
- `test_simple_answer_metrics` at line 562; asserts 4, raises contexts 0.
- `test_jsonl_report_contains_summary_and_results` at line 575; asserts 2, raises contexts 0.
- `test_huggingface_support_is_lazy_and_optional` at line 589; asserts 0, raises contexts 1.
- `test_eval_raw_replay_retrieval_finds_old_chunk_with_provenance` at line 596; asserts 7, raises contexts 0.
- `test_raw_replay_diagnostic_is_disabled_by_default` at line 633; asserts 4, raises contexts 0.
- `test_raw_replay_retrieval_uses_query_not_gold` at line 643; asserts 2, raises contexts 0.
- `test_raw_replay_candidates_are_bounded` at line 672; asserts 3, raises contexts 0.
- `test_enabled_raw_replay_reaches_context_packet` at line 702; asserts 10, raises contexts 0.
- `test_raw_replay_embedding_mode_is_opt_in` at line 725; asserts 2, raises contexts 0.
- `test_raw_replay_embedding_mode_finds_low_overlap_semantic_chunk` at line 757; asserts 3, raises contexts 0.
- `test_raw_replay_hybrid_fuses_lexical_and_embedding_ranks` at line 792; asserts 2, raises contexts 0.
- `test_raw_replay_pool_and_rank_diagnostics_are_bounded_and_post_hoc` at line 836; asserts 4, raises contexts 0.

## TS-057 — `tests/test_memory_context_acceptance.py`

SHA-256 `687de32a99e5ad4e737d7b9e05fd1779bfc48370b916d169e053d6d31760447b`. 5 test definitions; 32 assert nodes.
- `test_production_previous_chat_raw_child_folds_gist_in_context_packet` at line 55; asserts 6, raises contexts 0.
- `test_ended_chat_gist_routes_by_intent_and_expands_exact_evidence` at line 106; asserts 8, raises contexts 0.
- `test_production_recent_messages_keep_old_fact_and_current_query_once` at line 180; asserts 6, raises contexts 0.
- `test_explicit_raw_span_drill_down_reaches_context_with_provenance` at line 240; asserts 7, raises contexts 0.
- `test_production_disabled_previous_gist_does_not_retrieve_or_reach_context` at line 312; asserts 4, raises contexts 0.

## TS-058 — `tests/test_memory_reranker.py`

SHA-256 `fdf7b246183796be89a7db6ca6014db90b5cdb273732437a269815de1bcd080f`. 28 test definitions; 91 assert nodes.
- `test_deterministic_source_prior_prefers_structured_memory` at line 58; asserts 1, raises contexts 0.
- `test_deterministic_lexical_overlap_prefers_matching_content` at line 70; asserts 2, raises contexts 0.
- `test_raw_message_span_gets_provenance_query_boost` at line 85; asserts 2, raises contexts 0.
- `test_previous_chat_gist_gets_earlier_discussion_boost` at line 102; asserts 1, raises contexts 0.
- `test_document_memory_gets_document_query_boost` at line 115; asserts 1, raises contexts 0.
- `test_structured_memory_gets_preference_query_boost` at line 128; asserts 1, raises contexts 0.
- `test_deterministic_ties_preserve_original_order` at line 141; asserts 3, raises contexts 0.
- `test_hybrid_mode_applies_valid_llm_order` at line 155; asserts 5, raises contexts 0.
- `test_hybrid_falls_back_on_invalid_json` at line 184; asserts 2, raises contexts 0.
- `test_hybrid_falls_back_on_low_confidence` at line 203; asserts 3, raises contexts 0.
- `test_hybrid_falls_back_on_model_exception` at line 226; asserts 2, raises contexts 0.
- `test_hybrid_falls_back_when_model_is_missing` at line 245; asserts 2, raises contexts 0.
- `test_trace_contains_feature_contributions_and_ranks` at line 264; asserts 7, raises contexts 0.
- `test_cross_encoder_mode_combines_mocked_scores_and_reorders` at line 292; asserts 7, raises contexts 0.
- `test_cross_encoder_mode_limits_scoring_to_top_k` at line 316; asserts 4, raises contexts 0.
- `test_cross_encoder_equal_scores_preserve_source_aware_deterministic_boost` at line 338; asserts 2, raises contexts 0.
- `test_cross_encoder_falls_back_on_backend_exception` at line 360; asserts 3, raises contexts 0.
- `test_cross_encoder_falls_back_when_backend_is_unavailable` at line 379; asserts 2, raises contexts 0.
- `test_cross_encoder_falls_back_on_empty_scores` at line 399; asserts 2, raises contexts 0.
- `test_deterministic_mode_never_calls_cross_encoder_backend` at line 416; asserts 2, raises contexts 0.
- `test_hybrid_auto_uses_cross_encoder_and_skips_llm_for_large_margin` at line 437; asserts 8, raises contexts 0.
- `test_hybrid_auto_skips_llm_when_top_candidates_share_source` at line 468; asserts 4, raises contexts 0.
- `test_hybrid_auto_uses_llm_for_small_cross_source_margin` at line 495; asserts 6, raises contexts 0.
- `test_provenance_gist_raw_conflict_triggers_llm_despite_large_margin` at line 524; asserts 2, raises contexts 0.
- `test_hybrid_cross_encoder_backend_never_calls_llm` at line 550; asserts 4, raises contexts 0.
- `test_hybrid_llm_backend_never_calls_cross_encoder` at line 576; asserts 4, raises contexts 0.
- `test_hybrid_cross_encoder_failure_preserves_deterministic_order` at line 604; asserts 4, raises contexts 0.
- `test_hybrid_llm_failure_preserves_cross_encoder_order` at line 626; asserts 5, raises contexts 0.

## TS-059 — `tests/test_memory_trace.py`

SHA-256 `74a456ac742a9fe5f5dbaaf84218cad4981cc961761560450546496a9c7f1c9a`. 6 test definitions; 30 assert nodes.
- `test_format_saved_memory_trace_includes_demo_fields` at line 21; asserts 7, raises contexts 0.
- `test_format_retrieved_memory_trace_includes_source_chat` at line 44; asserts 6, raises contexts 0.
- `test_memory_record_to_inspector_row_is_script_ready` at line 66; asserts 1, raises contexts 0.
- `test_saved_memories_markdown_is_chainlit_demo_ready` at line 95; asserts 5, raises contexts 0.
- `test_retrieved_memories_markdown_is_chainlit_demo_ready` at line 116; asserts 5, raises contexts 0.
- `test_document_retrieval_markdown_is_chainlit_demo_ready` at line 142; asserts 6, raises contexts 0.

## TS-060 — `tests/test_model_token_accounting.py`

SHA-256 `3955e108a832f541624daeea21b957021ff04c7b501319d62a1f23fdbb369281`. 21 test definitions; 79 assert nodes.
- `test_gemma_profile_has_official_context_metadata` at line 114; asserts 3, raises contexts 0.
- `test_pillow_is_an_explicit_runtime_dependency` at line 122; asserts 1, raises contexts 0.
- `test_sliding_window_is_not_an_effective_input_limit` at line 126; asserts 3, raises contexts 0.
- `test_smaller_endpoint_limit_wins` at line 137; asserts 2, raises contexts 0.
- `test_smaller_application_cap_wins` at line 148; asserts 2, raises contexts 0.
- `test_unknown_endpoint_uses_default_gemma_native_cap` at line 159; asserts 5, raises contexts 0.
- `test_context_limit_environment_overrides_are_resolved` at line 169; asserts 3, raises contexts 0.
- `test_exact_processor_counts_text_and_chat_template_overhead` at line 181; asserts 4, raises contexts 0.
- `test_empty_messages_return_zero_without_loading_or_calling_backends` at line 197; asserts 3, raises contexts 0.
- `test_empty_messages_do_not_downgrade_resolved_text_tokenizer` at line 222; asserts 5, raises contexts 0.
- `test_processor_template_failure_uses_tokenizer_for_only_that_call` at line 242; asserts 3, raises contexts 0.
- `test_tokenizer_template_failure_uses_text_serialization_for_that_call` at line 261; asserts 4, raises contexts 0.
- `test_all_per_call_tokenizer_failures_are_temporary` at line 286; asserts 6, raises contexts 0.
- `test_valid_english_messages_remain_on_initialized_tokenizer` at line 318; asserts 4, raises contexts 0.
- `test_processor_is_lazy_and_cached_by_estimator` at line 338; asserts 2, raises contexts 0.
- `test_default_processor_cache_is_process_wide` at line 356; asserts 2, raises contexts 0.
- `test_processor_failure_uses_text_tokenizer_and_is_traced` at line 380; asserts 4, raises contexts 0.
- `test_processor_and_tokenizer_failure_use_approximate_fallback` at line 401; asserts 4, raises contexts 0.
- `test_processor_and_tokenizer_caches_are_independent` at line 421; asserts 6, raises contexts 0.
- `test_fallback_is_visible_in_context_trace` at line 453; asserts 9, raises contexts 0.
- `test_allocator_selection_is_unchanged_with_equivalent_injected_counter` at line 484; asserts 1, raises contexts 0.

## TS-061 — `tests/test_multi_source_retrieval_eval.py`

SHA-256 `d232b468a3a2b9786b4ccb580e9fe05d5b176c0068dc75c765a3e380265328a1`. 5 test definitions; 20 assert nodes.
- `test_load_jsonl_reads_sample_dataset` at line 17; asserts 2, raises contexts 0.
- `test_source_selection_and_retrieval_case_passes` at line 29; asserts 6, raises contexts 0.
- `test_abstain_case_requires_no_retrieved_candidates` at line 61; asserts 3, raises contexts 0.
- `test_forbidden_source_violation_is_reported` at line 80; asserts 2, raises contexts 0.
- `test_summary_and_trace_export_schema` at line 104; asserts 7, raises contexts 0.

## TS-062 — `tests/test_orchestration_demo_modes.py`

SHA-256 `ecce939292e38072ad9a9a5451580983a9f3c2e226567b0ca775c8fd640f13dc`. 5 test definitions; 22 assert nodes.
- `test_native_remains_default_and_does_not_run_graph` at line 63; asserts 3, raises contexts 0.
- `test_langgraph_demo_context_packet_is_used_for_model_answer` at line 83; asserts 7, raises contexts 0.
- `test_langgraph_shadow_keeps_native_context_authoritative` at line 115; asserts 5, raises contexts 0.
- `test_langgraph_demo_failure_visibly_falls_back_to_native` at line 133; asserts 4, raises contexts 0.
- `test_direct_langgraph_execution_is_read_only_for_all_sqlite_tables` at line 163; asserts 3, raises contexts 0.

## TS-063 — `tests/test_previous_chat_gist_generation.py`

SHA-256 `43bba761635875f191e5af60a0cfe5ca91b4b8dbcb2a02a60d30d18fdf83cd7c`. 13 test definitions; 38 assert nodes.
- `test_previous_chat_gist_generator_creates_gist_for_existing_chat` at line 59; asserts 11, raises contexts 0.
- `test_previous_chat_gist_generator_skips_active_and_existing_gists` at line 89; asserts 3, raises contexts 0.
- `test_previous_chat_gist_retrieval_returns_memory_candidate` at line 116; asserts 5, raises contexts 0.
- `test_global_summary_gist_retrieval_exposes_complete_chronology` at line 143; asserts 2, raises contexts 0.
- `test_route_planner_enables_previous_chat_gist_by_default_for_previous_intent` at line 180; asserts 2, raises contexts 0.
- `test_route_planner_emergency_gate_can_disable_previous_chat_gist` at line 192; asserts 1, raises contexts 0.
- `test_route_planner_does_not_enable_previous_gist_for_unrelated_queries` at line 208; asserts 1, raises contexts 0; decorators `pytest.mark.parametrize('query', ['How are you?', 'What is the capital of France?'])`.
- `test_previous_chat_exact_quote_reserves_gist_and_raw_span` at line 223; asserts 2, raises contexts 0.
- `test_same_chat_recall_keeps_current_chat_span_without_previous_gist` at line 235; asserts 2, raises contexts 0.
- `test_chat_service_runs_previous_gist_generation_only_when_enabled` at line 249; asserts 2, raises contexts 0.
- `test_deterministic_previous_gist_extractor_requires_no_model` at line 269; asserts 3, raises contexts 0.
- `test_invalid_previous_gist_does_not_advance_gist_state` at line 294; asserts 3, raises contexts 0.
- `test_failed_previous_gist_insert_does_not_advance_gist_state` at line 314; asserts 1, raises contexts 1.

## TS-064 — `tests/test_product_failure_atomicity.py`

SHA-256 `b0af3275d12733c4e169ef28ac136f659369775c61c5e407d00870d9b4b5a895`. 3 test definitions; 12 assert nodes.
- `test_answer_timeout_preserves_user_without_fake_assistant` at line 53; asserts 6, raises contexts 0.
- `test_send_and_end_share_one_atomic_chat_guard` at line 73; asserts 4, raises contexts 0.
- `test_send_after_end_is_rejected_before_persistence` at line 95; asserts 2, raises contexts 0.

## TS-065 — `tests/test_product_navigation_asset.py`

SHA-256 `908d85c52bcd6edc97c8d328dedd1e74c7887369456136467fb4808cb245ee19`. 2 test definitions; 19 assert nodes.
- `test_chainlit_loads_product_navigation_asset` at line 7; asserts 13, raises contexts 0.
- `test_product_navigation_has_no_backend_or_model_calls` at line 26; asserts 6, raises contexts 0.

## TS-066 — `tests/test_prompt_messages.py`

SHA-256 `f8fcc12cb56f1a257e50edb60d9d5bfd1a6026182f03559895cab446108f9245`. 6 test definitions; 13 assert nodes.
- `test_context_packet_to_model_messages_accepts_valid_packet` at line 24; asserts 3, raises contexts 0.
- `test_context_packet_to_model_messages_rejects_missing_latest_user_message` at line 32; asserts 2, raises contexts 0.
- `test_context_packet_to_model_messages_rejects_empty_content` at line 47; asserts 2, raises contexts 0.
- `test_context_packet_to_model_messages_rejects_invalid_role` at line 63; asserts 2, raises contexts 0.
- `test_context_packet_to_model_messages_rejects_duplicate_latest_user_message` at line 79; asserts 2, raises contexts 0.
- `test_context_packet_to_model_messages_rejects_severe_comparison_warning` at line 95; asserts 2, raises contexts 0.

## TS-067 — `tests/test_provider_settings.py`

SHA-256 `f192bd287eae451a38bb3415c6314791b2b41543187661dc498e7a376636654a`. 9 test definitions; 30 assert nodes.
- `test_deepseek_is_shared_and_ignores_legacy_endpoint` at line 40; asserts 4, raises contexts 0.
- `test_local_key_and_environment_override` at line 53; asserts 5, raises contexts 0.
- `test_custom_preserves_existing_configuration` at line 67; asserts 5, raises contexts 0.
- `test_invalid_provider_is_rejected` at line 79; asserts 0, raises contexts 1.
- `test_missing_key_is_rejected_by_both_clients` at line 85; asserts 0, raises contexts 2.
- `test_chat_sends_deepseek_request_without_network` at line 93; asserts 5, raises contexts 0.
- `test_langmem_receives_deepseek_options` at line 133; asserts 4, raises contexts 0.
- `test_resumed_chats_use_selected_provider_model` at line 154; asserts 4, raises contexts 0.
- `test_langchain_serializes_deepseek_tool_request_without_network` at line 177; asserts 3, raises contexts 0.

## TS-068 — `tests/test_raw_span_anchor_truncation.py`

SHA-256 `6b69d4043e16d57e666de88c31fa11a115b2623feb8d8e5a0f7a49eefd7e20c9`. 8 test definitions; 33 assert nodes.
- `test_gist_expansion_preserves_middle_anchor_under_small_limit` at line 24; asserts 8, raises contexts 0.
- `test_current_chat_span_preserves_matched_anchor_under_small_limit` at line 70; asserts 5, raises contexts 0.
- `test_context_packet_keeps_anchor_with_tight_budget` at line 109; asserts 5, raises contexts 0.
- `test_overlong_anchor_keeps_query_relevant_window` at line 173; asserts 3, raises contexts 0.
- `test_overlong_anchor_prefers_dense_relation_and_preserves_answer_phrase` at line 195; asserts 2, raises contexts 0.
- `test_conflicting_updates_remain_chronological_when_both_fit` at line 234; asserts 1, raises contexts 0.
- `test_non_raw_candidate_content_is_unchanged` at line 260; asserts 1, raises contexts 0.
- `test_gist_expansion_preserves_multiple_tied_anchor_messages` at line 270; asserts 8, raises contexts 0.

## TS-069 — `tests/test_retrieval_query_simplification.py`

SHA-256 `d972b519ebaa329ffb4b533d58e8ef0232eedec6ab1a080350a526d00f537bae`. 6 test definitions; 12 assert nodes.
- `test_entity_age_comparison_is_compact_and_preserves_direction` at line 12; asserts 2, raises contexts 0.
- `test_unsafe_or_already_compact_queries_fall_back_to_original` at line 34; asserts 2, raises contexts 0; decorators `pytest.mark.parametrize('query', ('Who founded Acme Labs?', 'Who led Acme Labs on 14 March 2024?', 'Which person did not lead Acme Labs?', 'What did I call "Pro`.
- `test_global_summary_query_retains_scope` at line 41; asserts 2, raises contexts 0.
- `test_long_boilerplate_is_removed_deterministically` at line 53; asserts 2, raises contexts 0.
- `test_capitalized_comparison_is_simplified_for_birth_date_retrieval` at line 66; asserts 2, raises contexts 0.
- `test_reranking_uses_retrieval_query_without_mutating_original_query` at line 77; asserts 2, raises contexts 0.

## TS-070 — `tests/test_routing_agent.py`

SHA-256 `29ac21bbff03d46ca8d5f7d01d1cd9e23fe902c4476f85244c43ec488c654dff`. 10 test definitions; 63 assert nodes.
- `test_routing_agent_representative_query_table` at line 33; asserts 11, raises contexts 0.
- `test_routing_agent_enables_gist_and_direct_raw_previous_sources` at line 89; asserts 8, raises contexts 0.
- `test_routing_agent_trace_fields_are_stable` at line 103; asserts 1, raises contexts 0.
- `test_routing_agent_rule_mode_is_default_and_does_not_call_model` at line 122; asserts 5, raises contexts 0.
- `test_routing_agent_llm_mode_uses_valid_structured_output` at line 137; asserts 14, raises contexts 0.
- `test_routing_agent_hybrid_mode_preserves_core_memory_sources` at line 163; asserts 5, raises contexts 0.
- `test_routing_agent_llm_mode_falls_back_when_model_missing` at line 179; asserts 7, raises contexts 0.
- `test_routing_agent_llm_mode_falls_back_on_invalid_json` at line 192; asserts 4, raises contexts 0.
- `test_routing_agent_llm_mode_falls_back_on_low_confidence` at line 203; asserts 4, raises contexts 0.
- `test_routing_agent_llm_mode_falls_back_on_model_error` at line 217; asserts 4, raises contexts 0.

## TS-071 — `tests/test_semantic_router.py`

SHA-256 `d74053f42b40d42833a110d7bf98e493187acf93c8a3fc36d5141c2e619b9c55`. 22 test definitions; 80 assert nodes.
- `test_english_quote_paraphrases_require_raw_evidence` at line 32; asserts 4, raises contexts 0; decorators `pytest.mark.parametrize('query', ['Quote exactly what I said about router.', 'What exact phrase did I use about router?', 'What were my exact words about router`.
- `test_document_question_requires_document_citation` at line 45; asserts 6, raises contexts 0.
- `test_same_turn_document_context_routes_generic_question_to_document_memory` at line 58; asserts 3, raises contexts 0.
- `test_current_chat_question_remains_current_chat_scoped` at line 69; asserts 2, raises contexts 0.
- `test_document_and_current_chat_query_unions_required_sources` at line 78; asserts 4, raises contexts 0.
- `test_document_and_previous_chat_query_unions_required_sources` at line 96; asserts 3, raises contexts 0.
- `test_document_and_previous_exact_wording_keeps_raw_span_contract` at line 114; asserts 5, raises contexts 0.
- `test_structured_preference_recall_requires_structured_memory` at line 134; asserts 3, raises contexts 0.
- `test_casual_chat_only_uses_recent_messages` at line 142; asserts 4, raises contexts 0.
- `test_original_query_and_generated_variants_remain_typed_hints` at line 151; asserts 6, raises contexts 0.
- `test_exact_quote_sources_follow_temporal_scope` at line 178; asserts 2, raises contexts 0.
- `test_previous_orientation_enables_gist_and_direct_raw_paths` at line 196; asserts 1, raises contexts 0.
- `test_factual_memory_question_without_temporal_wording_is_not_casual` at line 206; asserts 5, raises contexts 0.
- `test_memory_qa_task_context_is_generic_and_bounded` at line 224; asserts 5, raises contexts 0.
- `test_non_retrieval_requests_remain_recent_only` at line 252; asserts 3, raises contexts 0; decorators `pytest.mark.parametrize('query', ['Hello!', 'Thanks.', 'How are you?', 'Rewrite this paragraph to be clearer.', 'Brainstorm a product name.'])`.
- `test_book_summary_request_is_not_routed_as_casual_chat` at line 260; asserts 5, raises contexts 0.
- `test_summary_of_earlier_user_content_is_memory_grounded` at line 274; asserts 3, raises contexts 0.
- `test_previous_conversation_summary_prefers_previous_chat_memory` at line 282; asserts 4, raises contexts 0.
- `test_inline_summary_does_not_require_historical_memory` at line 295; asserts 4, raises contexts 0.
- `test_direct_memory_question_uses_memory_recall_profile` at line 305; asserts 1, raises contexts 0.
- `test_simplified_query_is_used_only_for_candidate_retrieval` at line 312; asserts 4, raises contexts 0.
- `test_summary_routing_does_not_change_casual_messages` at line 339; asserts 3, raises contexts 0; decorators `pytest.mark.parametrize('query', ('Hello, how are you?', 'Tell me a joke.'))`.

## TS-072 — `tests/test_semantic_router_v2_validation.py`

SHA-256 `58d160ae1f57d94eba0cd2e14087eca8b5e97dabe2296abc4368e5f9bb3260fe`. 4 test definitions; 34 assert nodes.
- `test_same_chat_quote_paraphrases_reach_exact_raw_span` at line 84; asserts 11, raises contexts 0; decorators `pytest.mark.parametrize(('query', 'exact_sentence'), [('What exact phrase did I use about router principle?', 'My router principle is: gist tells where to look,`.
- `test_previous_chat_quote_expands_finalized_gist_to_raw_span` at line 146; asserts 9, raises contexts 0.
- `test_gist_only_quote_fails_closed_through_semantic_graph` at line 193; asserts 6, raises contexts 0.
- `test_casual_chat_uses_only_recent_messages_in_semantic_graph` at line 221; asserts 8, raises contexts 0.

## TS-073 — `tests/test_short_term_memory_scheduling.py`

SHA-256 `2db06f7ff88bcb20053791bfe16cd4a3f2f0202b074466fe46e3278b7a56582f`. 13 test definitions; 31 assert nodes.
- `test_below_trigger_content_does_not_update_online` at line 90; asserts 2, raises contexts 0.
- `test_token_threshold_triggers_update_and_keeps_turn_together` at line 102; asserts 2, raises contexts 0.
- `test_assistant_only_pending_does_not_invoke_online_updater` at line 122; asserts 2, raises contexts 0.
- `test_oversized_individual_message_is_preserved` at line 133; asserts 2, raises contexts 0.
- `test_chat_end_flushes_below_trigger_remainder` at line 144; asserts 3, raises contexts 0.
- `test_online_protected_suffix_is_token_based` at line 159; asserts 2, raises contexts 0.
- `test_protection_boundary_snaps_to_turn_boundary` at line 178; asserts 3, raises contexts 0.
- `test_no_split_sequence_user_then_assistant_plus_next_user` at line 208; asserts 3, raises contexts 0.
- `test_consecutive_user_messages_make_progress_deterministically` at line 229; asserts 2, raises contexts 0.
- `test_assistant_only_prefix_does_not_loop_and_chat_end_flushes_progress` at line 247; asserts 3, raises contexts 0.
- `test_live_deferred_post_answer_update_keeps_turns_intact` at line 267; asserts 4, raises contexts 0.
- `test_recent_message_pool_uses_recent_messages_max_count_not_raw_message_limit` at line 305; asserts 1, raises contexts 0.
- `test_legacy_raw_message_limit_env_does_not_shrink_recent_retrieval` at line 329; asserts 2, raises contexts 0.

## TS-074 — `tests/test_structured_memory_eval.py`

SHA-256 `6d085de567cb465aac07354a22f02f0eb2b55d46ea5777ab083d26a806273fc8`. 6 test definitions; 30 assert nodes.
- `test_structured_memory_metrics_score_write_retrieval_and_answer_use` at line 9; asserts 4, raises contexts 0.
- `test_structured_memory_metrics_score_abstain_case` at line 32; asserts 3, raises contexts 0.
- `test_structured_memory_summary_rates_ignore_unavailable_answer_metrics` at line 53; asserts 5, raises contexts 0.
- `test_lifecycle_metrics_score_update_and_stale_memory` at line 88; asserts 4, raises contexts 0.
- `test_lifecycle_eval_runs_local_sample_dataset` at line 113; asserts 8, raises contexts 0.
- `test_structured_memory_eval_runs_local_sample_dataset` at line 129; asserts 6, raises contexts 0.

## TS-075 — `tests/test_structured_memory_vector_sync.py`

SHA-256 `bed217ee08d901f400c0200d606ff392c6c987966ae3f95d150f75e24ea433b1`. 8 test definitions; 34 assert nodes.
- `test_langmem_production_write_syncs_insert_with_typed_metadata` at line 132; asserts 9, raises contexts 0.
- `test_update_replaces_stable_vector_entry_without_stale_text` at line 173; asserts 3, raises contexts 0.
- `test_delete_and_inactive_upsert_remove_vector_entry_idempotently` at line 189; asserts 4, raises contexts 0.
- `test_repeated_sync_is_idempotent_by_stable_vector_id` at line 207; asserts 1, raises contexts 0.
- `test_vector_failure_is_explicit_but_sqlite_mode_requires_no_backend` at line 219; asserts 2, raises contexts 1.
- `test_backfill_repairs_missing_entries_without_duplicates` at line 258; asserts 4, raises contexts 0.
- `test_synced_vector_memory_reaches_context_with_sqlite_provenance` at line 288; asserts 7, raises contexts 0.
- `test_sqlite_recall_remains_independent_of_vector_backend` at line 329; asserts 4, raises contexts 0.

## TS-076 — `tests/test_targeted_eval_wrapper.py`

SHA-256 `d4f37cc6c357c27cd290712edb94ba0d12abe437bc1216fca22a48d6b32e1ce5`. 2 test definitions; 7 assert nodes.
- `test_targeted_wrapper_accepts_manifest_in_either_order` at line 36; asserts 5, raises contexts 0; decorators `pytest.mark.parametrize('arguments', (('--check', '--manifest', str(MANIFEST)), ('--manifest', str(MANIFEST), '--check')))`.
- `test_targeted_wrapper_rejects_unknown_arguments` at line 56; asserts 2, raises contexts 0.

## TS-077 — `tests/test_typed_memory_e2e_benchmark.py`

SHA-256 `2dbd25c28b7dd38de4b33d4faa45daff3f58a4e53781e8019ed68db1ab1679af`. 7 test definitions; 21 assert nodes.
- `test_runner_executes_one_case` at line 11; asserts 3, raises contexts 0.
- `test_missing_required_text_fails_case` at line 19; asserts 2, raises contexts 0.
- `test_missing_raw_span_fails_exact_quote_case` at line 32; asserts 2, raises contexts 0.
- `test_provenance_validation_works` at line 47; asserts 3, raises contexts 0.
- `test_aggregate_summary_and_case_filters` at line 59; asserts 5, raises contexts 0.
- `test_jsonl_output_is_bounded` at line 81; asserts 4, raises contexts 0.
- `test_benchmark_has_at_least_thirty_cases` at line 94; asserts 2, raises contexts 0.

## TS-078 — `test_upload.py`

SHA-256 `e12ffef95c631a5f1d9f8fc7d46828a979468bea2420e2a76022b3ce11eaf7ca`. 1 test definitions; 0 assert nodes.
- `test_socket_upload` at line 7; asserts 0, raises contexts 0.

## TS-079 — `test_upload_real.py`

SHA-256 `c3ac23f18d7789dd462d8acc715e1c31c121eab2e8e53d4d3dce41d6aaf21de0`. 1 test definitions; 0 assert nodes.
- `test_upload` at line 4; asserts 0, raises contexts 0.

## TS-080 — `evals/test_short_term_memory.py`

SHA-256 `0117e21ec42654abf2ccae32965a1718c2b490d2d6f821a40db890ad20050501`. 0 test definitions; 0 assert nodes.
- No `test_*` function definitions; may be helper, fixture or explicit CLI.
