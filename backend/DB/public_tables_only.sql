--
-- PostgreSQL database dump
--

\restrict hjyLyjTlX5FyLwNH6Bxzca3zJzP2CqKKtkaHkQOZpAsGsLhJxJnbz8c0XbsGINA

-- Dumped from database version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.11 (Ubuntu 16.11-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_pkey PRIMARY KEY (id);


--
-- Name: auth_user_groups auth_user_groups_user_id_group_id_94350c0c_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_group_id_94350c0c_uniq UNIQUE (user_id, group_id);


--
-- Name: auth_user auth_user_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_permission_id_14a6b632_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_permission_id_14a6b632_uniq UNIQUE (user_id, permission_id);


--
-- Name: auth_user auth_user_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user
    ADD CONSTRAINT auth_user_username_key UNIQUE (username);


--
-- Name: core_channelanalysis core_channelanalysis_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_channelanalysis
    ADD CONSTRAINT core_channelanalysis_pkey PRIMARY KEY (id);


--
-- Name: core_client core_client_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_client
    ADD CONSTRAINT core_client_pkey PRIMARY KEY (id);


--
-- Name: core_client core_client_slug_key; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_client
    ADD CONSTRAINT core_client_slug_key UNIQUE (slug);


--
-- Name: core_connection core_connection_client_id_provider_account_id_6f293e74_uniq; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_connection
    ADD CONSTRAINT core_connection_client_id_provider_account_id_6f293e74_uniq UNIQUE (client_id, provider, account_id);


--
-- Name: core_connection core_connection_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_connection
    ADD CONSTRAINT core_connection_pkey PRIMARY KEY (id);


--
-- Name: core_contenttemplate core_contenttemplate_client_id_name_dd21913c_uniq; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_contenttemplate
    ADD CONSTRAINT core_contenttemplate_client_id_name_dd21913c_uniq UNIQUE (client_id, name);


--
-- Name: core_contenttemplate core_contenttemplate_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_contenttemplate
    ADD CONSTRAINT core_contenttemplate_pkey PRIMARY KEY (id);


--
-- Name: core_post core_post_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_post
    ADD CONSTRAINT core_post_pkey PRIMARY KEY (id);


--
-- Name: core_postimage core_postimage_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_postimage
    ADD CONSTRAINT core_postimage_pkey PRIMARY KEY (id);


--
-- Name: core_postjob core_postjob_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_postjob
    ADD CONSTRAINT core_postjob_pkey PRIMARY KEY (id);


--
-- Name: core_posttone core_posttone_client_id_value_44805736_uniq; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_posttone
    ADD CONSTRAINT core_posttone_client_id_value_44805736_uniq UNIQUE (client_id, value);


--
-- Name: core_posttone core_posttone_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_posttone
    ADD CONSTRAINT core_posttone_pkey PRIMARY KEY (id);


--
-- Name: core_posttype core_posttype_client_id_value_f499900b_uniq; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_posttype
    ADD CONSTRAINT core_posttype_client_id_value_f499900b_uniq UNIQUE (client_id, value);


--
-- Name: core_posttype core_posttype_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_posttype
    ADD CONSTRAINT core_posttype_pkey PRIMARY KEY (id);


--
-- Name: core_postvideo core_postvideo_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_postvideo
    ADD CONSTRAINT core_postvideo_pkey PRIMARY KEY (id);


--
-- Name: core_schedule core_schedule_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_schedule
    ADD CONSTRAINT core_schedule_pkey PRIMARY KEY (id);


--
-- Name: core_seokeywordset core_seokeywordset_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_seokeywordset
    ADD CONSTRAINT core_seokeywordset_pkey PRIMARY KEY (id);


--
-- Name: core_socialaccount core_socialaccount_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_socialaccount
    ADD CONSTRAINT core_socialaccount_pkey PRIMARY KEY (id);


--
-- Name: core_story core_story_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_story
    ADD CONSTRAINT core_story_pkey PRIMARY KEY (id);


--
-- Name: core_systemsetting core_systemsetting_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_systemsetting
    ADD CONSTRAINT core_systemsetting_pkey PRIMARY KEY (id);


--
-- Name: core_topic core_topic_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_topic
    ADD CONSTRAINT core_topic_pkey PRIMARY KEY (id);


--
-- Name: core_trenditem core_trenditem_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_trenditem
    ADD CONSTRAINT core_trenditem_pkey PRIMARY KEY (id);


--
-- Name: core_usertenantrole core_usertenantrole_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_usertenantrole
    ADD CONSTRAINT core_usertenantrole_pkey PRIMARY KEY (id);


--
-- Name: core_usertenantrole core_usertenantrole_user_id_client_id_a79928dd_uniq; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_usertenantrole
    ADD CONSTRAINT core_usertenantrole_user_id_client_id_a79928dd_uniq UNIQUE (user_id, client_id);


--
-- Name: core_vkintegration core_vkintegration_client_id_group_id_c81e6614_uniq; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_vkintegration
    ADD CONSTRAINT core_vkintegration_client_id_group_id_c81e6614_uniq UNIQUE (client_id, group_id);


--
-- Name: core_vkintegration core_vkintegration_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_vkintegration
    ADD CONSTRAINT core_vkintegration_pkey PRIMARY KEY (id);


--
-- Name: core_weeklysourcebatch core_weeklysourcebatch_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_weeklysourcebatch
    ADD CONSTRAINT core_weeklysourcebatch_pkey PRIMARY KEY (id);


--
-- Name: core_weeklysourcereport core_weeklysourcereport_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_weeklysourcereport
    ADD CONSTRAINT core_weeklysourcereport_pkey PRIMARY KEY (id);


--
-- Name: core_wordstatquery core_wordstatquery_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_wordstatquery
    ADD CONSTRAINT core_wordstatquery_pkey PRIMARY KEY (id);


--
-- Name: core_wordstatresult core_wordstatresult_pkey; Type: CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_wordstatresult
    ADD CONSTRAINT core_wordstatresult_pkey PRIMARY KEY (id);


--
-- Name: django_admin_log django_admin_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_pkey PRIMARY KEY (id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: django_session django_session_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_session
    ADD CONSTRAINT django_session_pkey PRIMARY KEY (session_key);


--
-- Name: home_homepage home_homepage_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.home_homepage
    ADD CONSTRAINT home_homepage_pkey PRIMARY KEY (page_ptr_id);


--
-- Name: taggit_tag taggit_tag_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.taggit_tag
    ADD CONSTRAINT taggit_tag_name_key UNIQUE (name);


--
-- Name: taggit_tag taggit_tag_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.taggit_tag
    ADD CONSTRAINT taggit_tag_pkey PRIMARY KEY (id);


--
-- Name: taggit_tag taggit_tag_slug_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.taggit_tag
    ADD CONSTRAINT taggit_tag_slug_key UNIQUE (slug);


--
-- Name: taggit_taggeditem taggit_taggeditem_content_type_id_object_id_tag_id_4bb97a8e_uni; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.taggit_taggeditem
    ADD CONSTRAINT taggit_taggeditem_content_type_id_object_id_tag_id_4bb97a8e_uni UNIQUE (content_type_id, object_id, tag_id);


--
-- Name: taggit_taggeditem taggit_taggeditem_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.taggit_taggeditem
    ADD CONSTRAINT taggit_taggeditem_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_grouppagepermission unique_permission; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_grouppagepermission
    ADD CONSTRAINT unique_permission UNIQUE (group_id, page_id, permission_id);


--
-- Name: wagtailadmin_admin wagtailadmin_admin_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailadmin_admin
    ADD CONSTRAINT wagtailadmin_admin_pkey PRIMARY KEY (id);


--
-- Name: wagtailadmin_editingsession wagtailadmin_editingsession_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailadmin_editingsession
    ADD CONSTRAINT wagtailadmin_editingsession_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_collection wagtailcore_collection_path_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_collection
    ADD CONSTRAINT wagtailcore_collection_path_key UNIQUE (path);


--
-- Name: wagtailcore_collection wagtailcore_collection_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_collection
    ADD CONSTRAINT wagtailcore_collection_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_collectionviewrestriction_groups wagtailcore_collectionvi_collectionviewrestrictio_988995ae_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_collectionviewrestriction_groups
    ADD CONSTRAINT wagtailcore_collectionvi_collectionviewrestrictio_988995ae_uniq UNIQUE (collectionviewrestriction_id, group_id);


--
-- Name: wagtailcore_collectionviewrestriction_groups wagtailcore_collectionviewrestriction_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_collectionviewrestriction_groups
    ADD CONSTRAINT wagtailcore_collectionviewrestriction_groups_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_collectionviewrestriction wagtailcore_collectionviewrestriction_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_collectionviewrestriction
    ADD CONSTRAINT wagtailcore_collectionviewrestriction_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_comment wagtailcore_comment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_comment
    ADD CONSTRAINT wagtailcore_comment_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_commentreply wagtailcore_commentreply_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_commentreply
    ADD CONSTRAINT wagtailcore_commentreply_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_groupapprovaltask_groups wagtailcore_groupapprova_groupapprovaltask_id_gro_bb5ee7eb_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupapprovaltask_groups
    ADD CONSTRAINT wagtailcore_groupapprova_groupapprovaltask_id_gro_bb5ee7eb_uniq UNIQUE (groupapprovaltask_id, group_id);


--
-- Name: wagtailcore_groupapprovaltask_groups wagtailcore_groupapprovaltask_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupapprovaltask_groups
    ADD CONSTRAINT wagtailcore_groupapprovaltask_groups_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_groupapprovaltask wagtailcore_groupapprovaltask_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupapprovaltask
    ADD CONSTRAINT wagtailcore_groupapprovaltask_pkey PRIMARY KEY (task_ptr_id);


--
-- Name: wagtailcore_groupcollectionpermission wagtailcore_groupcollect_group_id_collection_id_p_a21cefe9_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupcollectionpermission
    ADD CONSTRAINT wagtailcore_groupcollect_group_id_collection_id_p_a21cefe9_uniq UNIQUE (group_id, collection_id, permission_id);


--
-- Name: wagtailcore_groupcollectionpermission wagtailcore_groupcollectionpermission_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupcollectionpermission
    ADD CONSTRAINT wagtailcore_groupcollectionpermission_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_grouppagepermission wagtailcore_grouppagepermission_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_grouppagepermission
    ADD CONSTRAINT wagtailcore_grouppagepermission_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_groupsitepermission wagtailcore_groupsiteper_group_id_site_id_permiss_a58ee30d_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupsitepermission
    ADD CONSTRAINT wagtailcore_groupsiteper_group_id_site_id_permiss_a58ee30d_uniq UNIQUE (group_id, site_id, permission_id);


--
-- Name: wagtailcore_groupsitepermission wagtailcore_groupsitepermission_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupsitepermission
    ADD CONSTRAINT wagtailcore_groupsitepermission_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_locale wagtailcore_locale_language_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_locale
    ADD CONSTRAINT wagtailcore_locale_language_code_key UNIQUE (language_code);


--
-- Name: wagtailcore_locale wagtailcore_locale_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_locale
    ADD CONSTRAINT wagtailcore_locale_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_modellogentry wagtailcore_modellogentry_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_modellogentry
    ADD CONSTRAINT wagtailcore_modellogentry_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_page wagtailcore_page_path_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_path_key UNIQUE (path);


--
-- Name: wagtailcore_page wagtailcore_page_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_page wagtailcore_page_translation_key_locale_id_9b041bad_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_translation_key_locale_id_9b041bad_uniq UNIQUE (translation_key, locale_id);


--
-- Name: wagtailcore_pagelogentry wagtailcore_pagelogentry_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pagelogentry
    ADD CONSTRAINT wagtailcore_pagelogentry_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_revision wagtailcore_pagerevision_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_revision
    ADD CONSTRAINT wagtailcore_pagerevision_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_pagesubscription wagtailcore_pagesubscription_page_id_user_id_0cef73ed_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pagesubscription
    ADD CONSTRAINT wagtailcore_pagesubscription_page_id_user_id_0cef73ed_uniq UNIQUE (page_id, user_id);


--
-- Name: wagtailcore_pagesubscription wagtailcore_pagesubscription_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pagesubscription
    ADD CONSTRAINT wagtailcore_pagesubscription_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_pageviewrestriction_groups wagtailcore_pageviewrest_pageviewrestriction_id_g_d23f80bb_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pageviewrestriction_groups
    ADD CONSTRAINT wagtailcore_pageviewrest_pageviewrestriction_id_g_d23f80bb_uniq UNIQUE (pageviewrestriction_id, group_id);


--
-- Name: wagtailcore_pageviewrestriction_groups wagtailcore_pageviewrestriction_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pageviewrestriction_groups
    ADD CONSTRAINT wagtailcore_pageviewrestriction_groups_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_pageviewrestriction wagtailcore_pageviewrestriction_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pageviewrestriction
    ADD CONSTRAINT wagtailcore_pageviewrestriction_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_referenceindex wagtailcore_referenceind_base_content_type_id_obj_9e6ccd6a_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_referenceindex
    ADD CONSTRAINT wagtailcore_referenceind_base_content_type_id_obj_9e6ccd6a_uniq UNIQUE (base_content_type_id, object_id, to_content_type_id, to_object_id, content_path_hash);


--
-- Name: wagtailcore_referenceindex wagtailcore_referenceindex_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_referenceindex
    ADD CONSTRAINT wagtailcore_referenceindex_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_site wagtailcore_site_hostname_port_2c626d70_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_site
    ADD CONSTRAINT wagtailcore_site_hostname_port_2c626d70_uniq UNIQUE (hostname, port);


--
-- Name: wagtailcore_site wagtailcore_site_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_site
    ADD CONSTRAINT wagtailcore_site_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_task wagtailcore_task_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_task
    ADD CONSTRAINT wagtailcore_task_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_taskstate wagtailcore_taskstate_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_taskstate
    ADD CONSTRAINT wagtailcore_taskstate_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_uploadedfile wagtailcore_uploadedfile_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_uploadedfile
    ADD CONSTRAINT wagtailcore_uploadedfile_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_workflow wagtailcore_workflow_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflow
    ADD CONSTRAINT wagtailcore_workflow_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_workflowcontenttype wagtailcore_workflowcontenttype_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowcontenttype
    ADD CONSTRAINT wagtailcore_workflowcontenttype_pkey PRIMARY KEY (content_type_id);


--
-- Name: wagtailcore_workflowpage wagtailcore_workflowpage_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowpage
    ADD CONSTRAINT wagtailcore_workflowpage_pkey PRIMARY KEY (page_id);


--
-- Name: wagtailcore_workflowstate wagtailcore_workflowstate_current_task_state_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowstate
    ADD CONSTRAINT wagtailcore_workflowstate_current_task_state_id_key UNIQUE (current_task_state_id);


--
-- Name: wagtailcore_workflowstate wagtailcore_workflowstate_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowstate
    ADD CONSTRAINT wagtailcore_workflowstate_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_workflowtask wagtailcore_workflowtask_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowtask
    ADD CONSTRAINT wagtailcore_workflowtask_pkey PRIMARY KEY (id);


--
-- Name: wagtailcore_workflowtask wagtailcore_workflowtask_workflow_id_task_id_4ec7a62b_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowtask
    ADD CONSTRAINT wagtailcore_workflowtask_workflow_id_task_id_4ec7a62b_uniq UNIQUE (workflow_id, task_id);


--
-- Name: wagtaildocs_document wagtaildocs_document_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtaildocs_document
    ADD CONSTRAINT wagtaildocs_document_pkey PRIMARY KEY (id);


--
-- Name: wagtailembeds_embed wagtailembeds_embed_hash_c9bd8c9a_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailembeds_embed
    ADD CONSTRAINT wagtailembeds_embed_hash_c9bd8c9a_uniq UNIQUE (hash);


--
-- Name: wagtailembeds_embed wagtailembeds_embed_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailembeds_embed
    ADD CONSTRAINT wagtailembeds_embed_pkey PRIMARY KEY (id);


--
-- Name: wagtailforms_formsubmission wagtailforms_formsubmission_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailforms_formsubmission
    ADD CONSTRAINT wagtailforms_formsubmission_pkey PRIMARY KEY (id);


--
-- Name: wagtailimages_image wagtailimages_image_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailimages_image
    ADD CONSTRAINT wagtailimages_image_pkey PRIMARY KEY (id);


--
-- Name: wagtailimages_rendition wagtailimages_rendition_image_id_filter_spec_foc_323c8fe0_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailimages_rendition
    ADD CONSTRAINT wagtailimages_rendition_image_id_filter_spec_foc_323c8fe0_uniq UNIQUE (image_id, filter_spec, focal_point_key);


--
-- Name: wagtailimages_rendition wagtailimages_rendition_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailimages_rendition
    ADD CONSTRAINT wagtailimages_rendition_pkey PRIMARY KEY (id);


--
-- Name: wagtailredirects_redirect wagtailredirects_redirect_old_path_site_id_783622d7_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailredirects_redirect
    ADD CONSTRAINT wagtailredirects_redirect_old_path_site_id_783622d7_uniq UNIQUE (old_path, site_id);


--
-- Name: wagtailredirects_redirect wagtailredirects_redirect_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailredirects_redirect
    ADD CONSTRAINT wagtailredirects_redirect_pkey PRIMARY KEY (id);


--
-- Name: wagtailsearch_indexentry wagtailsearch_indexentry_content_type_id_object_i_bcd7ba73_uniq; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailsearch_indexentry
    ADD CONSTRAINT wagtailsearch_indexentry_content_type_id_object_i_bcd7ba73_uniq UNIQUE (content_type_id, object_id);


--
-- Name: wagtailsearch_indexentry wagtailsearch_indexentry_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailsearch_indexentry
    ADD CONSTRAINT wagtailsearch_indexentry_pkey PRIMARY KEY (id);


--
-- Name: wagtailusers_userprofile wagtailusers_userprofile_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailusers_userprofile
    ADD CONSTRAINT wagtailusers_userprofile_pkey PRIMARY KEY (id);


--
-- Name: wagtailusers_userprofile wagtailusers_userprofile_user_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailusers_userprofile
    ADD CONSTRAINT wagtailusers_userprofile_user_id_key UNIQUE (user_id);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: auth_user_groups_group_id_97559544; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_user_groups_group_id_97559544 ON public.auth_user_groups USING btree (group_id);


--
-- Name: auth_user_groups_user_id_6a12ed8b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_user_groups_user_id_6a12ed8b ON public.auth_user_groups USING btree (user_id);


--
-- Name: auth_user_user_permissions_permission_id_1fbb5f2c; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_user_user_permissions_permission_id_1fbb5f2c ON public.auth_user_user_permissions USING btree (permission_id);


--
-- Name: auth_user_user_permissions_user_id_a95ead1b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_user_user_permissions_user_id_a95ead1b ON public.auth_user_user_permissions USING btree (user_id);


--
-- Name: auth_user_username_6821ab7c_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX auth_user_username_6821ab7c_like ON public.auth_user USING btree (username varchar_pattern_ops);


--
-- Name: base_content_object_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX base_content_object_idx ON public.wagtailcore_revision USING btree (base_content_type_id, object_id);


--
-- Name: content_object_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX content_object_idx ON public.wagtailcore_revision USING btree (content_type_id, object_id);


--
-- Name: core_channelanalysis_client_id_1d3b01c2; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_channelanalysis_client_id_1d3b01c2 ON public.core_channelanalysis USING btree (client_id);


--
-- Name: core_client_slug_40c22521_like; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_client_slug_40c22521_like ON public.core_client USING btree (slug varchar_pattern_ops);


--
-- Name: core_connection_client_id_bd3ebbed; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_connection_client_id_bd3ebbed ON public.core_connection USING btree (client_id);


--
-- Name: core_connection_created_by_id_77c921b8; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_connection_created_by_id_77c921b8 ON public.core_connection USING btree (created_by_id);


--
-- Name: core_contenttemplate_client_id_2e1a9899; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_contenttemplate_client_id_2e1a9899 ON public.core_contenttemplate USING btree (client_id);


--
-- Name: core_post_client_id_88f5b031; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_post_client_id_88f5b031 ON public.core_post USING btree (client_id);


--
-- Name: core_post_created_by_id_e76054c9; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_post_created_by_id_e76054c9 ON public.core_post USING btree (created_by_id);


--
-- Name: core_post_story_id_31e37d95; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_post_story_id_31e37d95 ON public.core_post USING btree (story_id);


--
-- Name: core_post_template_id_acd96195; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_post_template_id_acd96195 ON public.core_post USING btree (template_id);


--
-- Name: core_postimage_post_id_5d452adf; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_postimage_post_id_5d452adf ON public.core_postimage USING btree (post_id);


--
-- Name: core_postjob_client_id_042d1556; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_postjob_client_id_042d1556 ON public.core_postjob USING btree (client_id);


--
-- Name: core_postjob_connection_id_3ee9a4db; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_postjob_connection_id_3ee9a4db ON public.core_postjob USING btree (connection_id);


--
-- Name: core_postjob_schedule_id_2907b87f; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_postjob_schedule_id_2907b87f ON public.core_postjob USING btree (schedule_id);


--
-- Name: core_posttone_client_id_8d03519a; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_posttone_client_id_8d03519a ON public.core_posttone USING btree (client_id);


--
-- Name: core_posttype_client_id_1d44d7e8; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_posttype_client_id_1d44d7e8 ON public.core_posttype USING btree (client_id);


--
-- Name: core_postvideo_post_id_216bc28b; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_postvideo_post_id_216bc28b ON public.core_postvideo USING btree (post_id);


--
-- Name: core_schedule_client_id_8ba0f82e; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_schedule_client_id_8ba0f82e ON public.core_schedule USING btree (client_id);


--
-- Name: core_schedule_connection_id_ff5dc738; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_schedule_connection_id_ff5dc738 ON public.core_schedule USING btree (connection_id);


--
-- Name: core_schedule_post_id_50a128a1; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_schedule_post_id_50a128a1 ON public.core_schedule USING btree (post_id);


--
-- Name: core_schedule_social_account_id_c5ac05ed; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_schedule_social_account_id_c5ac05ed ON public.core_schedule USING btree (social_account_id);


--
-- Name: core_seokeywordset_client_id_77a3745e; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_seokeywordset_client_id_77a3745e ON public.core_seokeywordset USING btree (client_id);


--
-- Name: core_seokeywordset_topic_id_179f903f; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_seokeywordset_topic_id_179f903f ON public.core_seokeywordset USING btree (topic_id);


--
-- Name: core_socialaccount_client_id_878f9264; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_socialaccount_client_id_878f9264 ON public.core_socialaccount USING btree (client_id);


--
-- Name: core_story_client_id_a104b187; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_story_client_id_a104b187 ON public.core_story USING btree (client_id);


--
-- Name: core_story_created_by_id_1ce6750c; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_story_created_by_id_1ce6750c ON public.core_story USING btree (created_by_id);


--
-- Name: core_story_template_id_8a2d322c; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_story_template_id_8a2d322c ON public.core_story USING btree (template_id);


--
-- Name: core_story_trend_item_id_3b684fdc; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_story_trend_item_id_3b684fdc ON public.core_story USING btree (trend_item_id);


--
-- Name: core_topic_client_id_70f88e24; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_topic_client_id_70f88e24 ON public.core_topic USING btree (client_id);


--
-- Name: core_trenditem_client_id_bce5f984; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_trenditem_client_id_bce5f984 ON public.core_trenditem USING btree (client_id);


--
-- Name: core_trenditem_topic_id_f2452ce3; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_trenditem_topic_id_f2452ce3 ON public.core_trenditem USING btree (topic_id);


--
-- Name: core_trenditem_used_for_post_id_fb3f4342; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_trenditem_used_for_post_id_fb3f4342 ON public.core_trenditem USING btree (used_for_post_id);


--
-- Name: core_usertenantrole_client_id_0023ee92; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_usertenantrole_client_id_0023ee92 ON public.core_usertenantrole USING btree (client_id);


--
-- Name: core_usertenantrole_user_id_14786ac6; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_usertenantrole_user_id_14786ac6 ON public.core_usertenantrole USING btree (user_id);


--
-- Name: core_vkintegration_client_id_5dde4dc0; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_vkintegration_client_id_5dde4dc0 ON public.core_vkintegration USING btree (client_id);


--
-- Name: core_vkintegration_owner_id_ccfbe785; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_vkintegration_owner_id_ccfbe785 ON public.core_vkintegration USING btree (owner_id);


--
-- Name: core_weekly_client__84fb5e_idx; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_weekly_client__84fb5e_idx ON public.core_weeklysourcereport USING btree (client_id, source_type, week_start);


--
-- Name: core_weeklysourcereport_client_id_3f8efd85; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_weeklysourcereport_client_id_3f8efd85 ON public.core_weeklysourcereport USING btree (client_id);


--
-- Name: core_wordst_client__69e49e_idx; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_wordst_client__69e49e_idx ON public.core_wordstatquery USING btree (client_id, request_phrase);


--
-- Name: core_wordst_client__e432bf_idx; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_wordst_client__e432bf_idx ON public.core_wordstatquery USING btree (client_id, created_at);


--
-- Name: core_wordst_query_i_3276be_idx; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_wordst_query_i_3276be_idx ON public.core_wordstatresult USING btree (query_id, result_type, count);


--
-- Name: core_wordstatquery_client_id_986c7f6b; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_wordstatquery_client_id_986c7f6b ON public.core_wordstatquery USING btree (client_id);


--
-- Name: core_wordstatresult_query_id_b33b01a1; Type: INDEX; Schema: public; Owner: us
--

CREATE INDEX core_wordstatresult_query_id_b33b01a1 ON public.core_wordstatresult USING btree (query_id);


--
-- Name: django_admin_log_content_type_id_c4bce8eb; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX django_admin_log_content_type_id_c4bce8eb ON public.django_admin_log USING btree (content_type_id);


--
-- Name: django_admin_log_user_id_c564eba6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX django_admin_log_user_id_c564eba6 ON public.django_admin_log USING btree (user_id);


--
-- Name: django_session_expire_date_a5c62663; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX django_session_expire_date_a5c62663 ON public.django_session USING btree (expire_date);


--
-- Name: django_session_session_key_c0390e0f_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX django_session_session_key_c0390e0f_like ON public.django_session USING btree (session_key varchar_pattern_ops);


--
-- Name: referenceindex_source_object; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX referenceindex_source_object ON public.wagtailcore_referenceindex USING btree (base_content_type_id, object_id);


--
-- Name: referenceindex_target_object; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX referenceindex_target_object ON public.wagtailcore_referenceindex USING btree (to_content_type_id, to_object_id);


--
-- Name: taggit_tag_name_58eb2ed9_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX taggit_tag_name_58eb2ed9_like ON public.taggit_tag USING btree (name varchar_pattern_ops);


--
-- Name: taggit_tag_slug_6be58b2c_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX taggit_tag_slug_6be58b2c_like ON public.taggit_tag USING btree (slug varchar_pattern_ops);


--
-- Name: taggit_tagg_content_8fc721_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX taggit_tagg_content_8fc721_idx ON public.taggit_taggeditem USING btree (content_type_id, object_id);


--
-- Name: taggit_taggeditem_content_type_id_9957a03c; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX taggit_taggeditem_content_type_id_9957a03c ON public.taggit_taggeditem USING btree (content_type_id);


--
-- Name: taggit_taggeditem_object_id_e2d7d1df; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX taggit_taggeditem_object_id_e2d7d1df ON public.taggit_taggeditem USING btree (object_id);


--
-- Name: taggit_taggeditem_tag_id_f4f5b767; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX taggit_taggeditem_tag_id_f4f5b767 ON public.taggit_taggeditem USING btree (tag_id);


--
-- Name: unique_in_progress_workflow; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX unique_in_progress_workflow ON public.wagtailcore_workflowstate USING btree (base_content_type_id, object_id) WHERE ((status)::text = ANY (ARRAY[('in_progress'::character varying)::text, ('needs_changes'::character varying)::text]));


--
-- Name: wagtailadmi_content_717955_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailadmi_content_717955_idx ON public.wagtailadmin_editingsession USING btree (content_type_id, object_id);


--
-- Name: wagtailadmin_editingsession_content_type_id_4df7730e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailadmin_editingsession_content_type_id_4df7730e ON public.wagtailadmin_editingsession USING btree (content_type_id);


--
-- Name: wagtailadmin_editingsession_user_id_6e1a9b70; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailadmin_editingsession_user_id_6e1a9b70 ON public.wagtailadmin_editingsession USING btree (user_id);


--
-- Name: wagtailcore_collection_path_d848dc19_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_collection_path_d848dc19_like ON public.wagtailcore_collection USING btree (path varchar_pattern_ops);


--
-- Name: wagtailcore_collectionview_collectionviewrestriction__47320efd; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_collectionview_collectionviewrestriction__47320efd ON public.wagtailcore_collectionviewrestriction_groups USING btree (collectionviewrestriction_id);


--
-- Name: wagtailcore_collectionviewrestriction_collection_id_761908ec; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_collectionviewrestriction_collection_id_761908ec ON public.wagtailcore_collectionviewrestriction USING btree (collection_id);


--
-- Name: wagtailcore_collectionviewrestriction_groups_group_id_1823f2a3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_collectionviewrestriction_groups_group_id_1823f2a3 ON public.wagtailcore_collectionviewrestriction_groups USING btree (group_id);


--
-- Name: wagtailcore_comment_page_id_108444b5; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_comment_page_id_108444b5 ON public.wagtailcore_comment USING btree (page_id);


--
-- Name: wagtailcore_comment_resolved_by_id_a282aa0e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_comment_resolved_by_id_a282aa0e ON public.wagtailcore_comment USING btree (resolved_by_id);


--
-- Name: wagtailcore_comment_revision_created_id_1d058279; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_comment_revision_created_id_1d058279 ON public.wagtailcore_comment USING btree (revision_created_id);


--
-- Name: wagtailcore_comment_user_id_0c577ca6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_comment_user_id_0c577ca6 ON public.wagtailcore_comment USING btree (user_id);


--
-- Name: wagtailcore_commentreply_comment_id_afc7e027; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_commentreply_comment_id_afc7e027 ON public.wagtailcore_commentreply USING btree (comment_id);


--
-- Name: wagtailcore_commentreply_user_id_d0b3b9c3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_commentreply_user_id_d0b3b9c3 ON public.wagtailcore_commentreply USING btree (user_id);


--
-- Name: wagtailcore_groupapprovalt_groupapprovaltask_id_9a9255ea; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_groupapprovalt_groupapprovaltask_id_9a9255ea ON public.wagtailcore_groupapprovaltask_groups USING btree (groupapprovaltask_id);


--
-- Name: wagtailcore_groupapprovaltask_groups_group_id_2e64b61f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_groupapprovaltask_groups_group_id_2e64b61f ON public.wagtailcore_groupapprovaltask_groups USING btree (group_id);


--
-- Name: wagtailcore_groupcollectionpermission_collection_id_5423575a; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_groupcollectionpermission_collection_id_5423575a ON public.wagtailcore_groupcollectionpermission USING btree (collection_id);


--
-- Name: wagtailcore_groupcollectionpermission_group_id_05d61460; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_groupcollectionpermission_group_id_05d61460 ON public.wagtailcore_groupcollectionpermission USING btree (group_id);


--
-- Name: wagtailcore_groupcollectionpermission_permission_id_1b626275; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_groupcollectionpermission_permission_id_1b626275 ON public.wagtailcore_groupcollectionpermission USING btree (permission_id);


--
-- Name: wagtailcore_grouppagepermission_group_id_fc07e671; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_grouppagepermission_group_id_fc07e671 ON public.wagtailcore_grouppagepermission USING btree (group_id);


--
-- Name: wagtailcore_grouppagepermission_page_id_710b114a; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_grouppagepermission_page_id_710b114a ON public.wagtailcore_grouppagepermission USING btree (page_id);


--
-- Name: wagtailcore_grouppagepermission_permission_id_05acb22e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_grouppagepermission_permission_id_05acb22e ON public.wagtailcore_grouppagepermission USING btree (permission_id);


--
-- Name: wagtailcore_groupsitepermission_group_id_e5cdbee4; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_groupsitepermission_group_id_e5cdbee4 ON public.wagtailcore_groupsitepermission USING btree (group_id);


--
-- Name: wagtailcore_groupsitepermission_permission_id_459b1f38; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_groupsitepermission_permission_id_459b1f38 ON public.wagtailcore_groupsitepermission USING btree (permission_id);


--
-- Name: wagtailcore_groupsitepermission_site_id_245de488; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_groupsitepermission_site_id_245de488 ON public.wagtailcore_groupsitepermission USING btree (site_id);


--
-- Name: wagtailcore_locale_language_code_03149338_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_locale_language_code_03149338_like ON public.wagtailcore_locale USING btree (language_code varchar_pattern_ops);


--
-- Name: wagtailcore_modellogentry_action_d2d856ee; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_action_d2d856ee ON public.wagtailcore_modellogentry USING btree (action);


--
-- Name: wagtailcore_modellogentry_action_d2d856ee_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_action_d2d856ee_like ON public.wagtailcore_modellogentry USING btree (action varchar_pattern_ops);


--
-- Name: wagtailcore_modellogentry_content_changed_8bc39742; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_content_changed_8bc39742 ON public.wagtailcore_modellogentry USING btree (content_changed);


--
-- Name: wagtailcore_modellogentry_content_type_id_68849e77; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_content_type_id_68849e77 ON public.wagtailcore_modellogentry USING btree (content_type_id);


--
-- Name: wagtailcore_modellogentry_object_id_e0e7d4ef; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_object_id_e0e7d4ef ON public.wagtailcore_modellogentry USING btree (object_id);


--
-- Name: wagtailcore_modellogentry_object_id_e0e7d4ef_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_object_id_e0e7d4ef_like ON public.wagtailcore_modellogentry USING btree (object_id varchar_pattern_ops);


--
-- Name: wagtailcore_modellogentry_revision_id_df6ca33a; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_revision_id_df6ca33a ON public.wagtailcore_modellogentry USING btree (revision_id);


--
-- Name: wagtailcore_modellogentry_timestamp_9694521b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_timestamp_9694521b ON public.wagtailcore_modellogentry USING btree ("timestamp");


--
-- Name: wagtailcore_modellogentry_user_id_0278d1bf; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_modellogentry_user_id_0278d1bf ON public.wagtailcore_modellogentry USING btree (user_id);


--
-- Name: wagtailcore_page_alias_of_id_12945502; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_alias_of_id_12945502 ON public.wagtailcore_page USING btree (alias_of_id);


--
-- Name: wagtailcore_page_content_type_id_c28424df; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_content_type_id_c28424df ON public.wagtailcore_page USING btree (content_type_id);


--
-- Name: wagtailcore_page_first_published_at_2b5dd637; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_first_published_at_2b5dd637 ON public.wagtailcore_page USING btree (first_published_at);


--
-- Name: wagtailcore_page_latest_revision_id_e60fef51; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_latest_revision_id_e60fef51 ON public.wagtailcore_page USING btree (latest_revision_id);


--
-- Name: wagtailcore_page_live_revision_id_930bd822; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_live_revision_id_930bd822 ON public.wagtailcore_page USING btree (live_revision_id);


--
-- Name: wagtailcore_page_locale_id_3c7e30a6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_locale_id_3c7e30a6 ON public.wagtailcore_page USING btree (locale_id);


--
-- Name: wagtailcore_page_locked_by_id_bcb86245; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_locked_by_id_bcb86245 ON public.wagtailcore_page USING btree (locked_by_id);


--
-- Name: wagtailcore_page_owner_id_fbf7c332; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_owner_id_fbf7c332 ON public.wagtailcore_page USING btree (owner_id);


--
-- Name: wagtailcore_page_path_98eba2c8_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_path_98eba2c8_like ON public.wagtailcore_page USING btree (path varchar_pattern_ops);


--
-- Name: wagtailcore_page_slug_e7c11b8f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_slug_e7c11b8f ON public.wagtailcore_page USING btree (slug);


--
-- Name: wagtailcore_page_slug_e7c11b8f_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_page_slug_e7c11b8f_like ON public.wagtailcore_page USING btree (slug varchar_pattern_ops);


--
-- Name: wagtailcore_pagelogentry_action_c2408198; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagelogentry_action_c2408198 ON public.wagtailcore_pagelogentry USING btree (action);


--
-- Name: wagtailcore_pagelogentry_action_c2408198_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagelogentry_action_c2408198_like ON public.wagtailcore_pagelogentry USING btree (action varchar_pattern_ops);


--
-- Name: wagtailcore_pagelogentry_content_changed_99f27ade; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagelogentry_content_changed_99f27ade ON public.wagtailcore_pagelogentry USING btree (content_changed);


--
-- Name: wagtailcore_pagelogentry_content_type_id_74e7708a; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagelogentry_content_type_id_74e7708a ON public.wagtailcore_pagelogentry USING btree (content_type_id);


--
-- Name: wagtailcore_pagelogentry_page_id_8464e327; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagelogentry_page_id_8464e327 ON public.wagtailcore_pagelogentry USING btree (page_id);


--
-- Name: wagtailcore_pagelogentry_revision_id_8043d103; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagelogentry_revision_id_8043d103 ON public.wagtailcore_pagelogentry USING btree (revision_id);


--
-- Name: wagtailcore_pagelogentry_timestamp_deb774c4; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagelogentry_timestamp_deb774c4 ON public.wagtailcore_pagelogentry USING btree ("timestamp");


--
-- Name: wagtailcore_pagelogentry_user_id_604ccfd8; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagelogentry_user_id_604ccfd8 ON public.wagtailcore_pagelogentry USING btree (user_id);


--
-- Name: wagtailcore_pagerevision_approved_go_live_at_e56afc67; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagerevision_approved_go_live_at_e56afc67 ON public.wagtailcore_revision USING btree (approved_go_live_at);


--
-- Name: wagtailcore_pagerevision_created_at_66954e3b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagerevision_created_at_66954e3b ON public.wagtailcore_revision USING btree (created_at);


--
-- Name: wagtailcore_pagerevision_user_id_2409d2f4; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagerevision_user_id_2409d2f4 ON public.wagtailcore_revision USING btree (user_id);


--
-- Name: wagtailcore_pagesubscription_page_id_a085e7a6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagesubscription_page_id_a085e7a6 ON public.wagtailcore_pagesubscription USING btree (page_id);


--
-- Name: wagtailcore_pagesubscription_user_id_89d7def9; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pagesubscription_user_id_89d7def9 ON public.wagtailcore_pagesubscription USING btree (user_id);


--
-- Name: wagtailcore_pageviewrestri_pageviewrestriction_id_f147a99a; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pageviewrestri_pageviewrestriction_id_f147a99a ON public.wagtailcore_pageviewrestriction_groups USING btree (pageviewrestriction_id);


--
-- Name: wagtailcore_pageviewrestriction_groups_group_id_6460f223; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pageviewrestriction_groups_group_id_6460f223 ON public.wagtailcore_pageviewrestriction_groups USING btree (group_id);


--
-- Name: wagtailcore_pageviewrestriction_page_id_15a8bea6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_pageviewrestriction_page_id_15a8bea6 ON public.wagtailcore_pageviewrestriction USING btree (page_id);


--
-- Name: wagtailcore_referenceindex_base_content_type_id_313cf40f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_referenceindex_base_content_type_id_313cf40f ON public.wagtailcore_referenceindex USING btree (base_content_type_id);


--
-- Name: wagtailcore_referenceindex_content_type_id_766e0336; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_referenceindex_content_type_id_766e0336 ON public.wagtailcore_referenceindex USING btree (content_type_id);


--
-- Name: wagtailcore_referenceindex_to_content_type_id_93690bbd; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_referenceindex_to_content_type_id_93690bbd ON public.wagtailcore_referenceindex USING btree (to_content_type_id);


--
-- Name: wagtailcore_revision_base_content_type_id_5b4ef7bd; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_revision_base_content_type_id_5b4ef7bd ON public.wagtailcore_revision USING btree (base_content_type_id);


--
-- Name: wagtailcore_revision_content_type_id_c8cb69c0; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_revision_content_type_id_c8cb69c0 ON public.wagtailcore_revision USING btree (content_type_id);


--
-- Name: wagtailcore_site_hostname_96b20b46; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_site_hostname_96b20b46 ON public.wagtailcore_site USING btree (hostname);


--
-- Name: wagtailcore_site_hostname_96b20b46_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_site_hostname_96b20b46_like ON public.wagtailcore_site USING btree (hostname varchar_pattern_ops);


--
-- Name: wagtailcore_site_root_page_id_e02fb95c; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_site_root_page_id_e02fb95c ON public.wagtailcore_site USING btree (root_page_id);


--
-- Name: wagtailcore_task_content_type_id_249ab8ba; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_task_content_type_id_249ab8ba ON public.wagtailcore_task USING btree (content_type_id);


--
-- Name: wagtailcore_taskstate_content_type_id_0a758fdc; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_taskstate_content_type_id_0a758fdc ON public.wagtailcore_taskstate USING btree (content_type_id);


--
-- Name: wagtailcore_taskstate_finished_by_id_13f98229; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_taskstate_finished_by_id_13f98229 ON public.wagtailcore_taskstate USING btree (finished_by_id);


--
-- Name: wagtailcore_taskstate_page_revision_id_9f52c88e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_taskstate_page_revision_id_9f52c88e ON public.wagtailcore_taskstate USING btree (revision_id);


--
-- Name: wagtailcore_taskstate_task_id_c3677c34; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_taskstate_task_id_c3677c34 ON public.wagtailcore_taskstate USING btree (task_id);


--
-- Name: wagtailcore_taskstate_workflow_state_id_9239a775; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_taskstate_workflow_state_id_9239a775 ON public.wagtailcore_taskstate USING btree (workflow_state_id);


--
-- Name: wagtailcore_uploadedfile_for_content_type_id_b0fc87b2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_uploadedfile_for_content_type_id_b0fc87b2 ON public.wagtailcore_uploadedfile USING btree (for_content_type_id);


--
-- Name: wagtailcore_uploadedfile_uploaded_by_user_id_c7580fe8; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_uploadedfile_uploaded_by_user_id_c7580fe8 ON public.wagtailcore_uploadedfile USING btree (uploaded_by_user_id);


--
-- Name: wagtailcore_workflowcontenttype_workflow_id_9aad7cd2; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_workflowcontenttype_workflow_id_9aad7cd2 ON public.wagtailcore_workflowcontenttype USING btree (workflow_id);


--
-- Name: wagtailcore_workflowpage_workflow_id_56f56ff6; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_workflowpage_workflow_id_56f56ff6 ON public.wagtailcore_workflowpage USING btree (workflow_id);


--
-- Name: wagtailcore_workflowstate_base_content_type_id_a30dc576; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_workflowstate_base_content_type_id_a30dc576 ON public.wagtailcore_workflowstate USING btree (base_content_type_id);


--
-- Name: wagtailcore_workflowstate_content_type_id_2bb78ce1; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_workflowstate_content_type_id_2bb78ce1 ON public.wagtailcore_workflowstate USING btree (content_type_id);


--
-- Name: wagtailcore_workflowstate_requested_by_id_4090bca3; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_workflowstate_requested_by_id_4090bca3 ON public.wagtailcore_workflowstate USING btree (requested_by_id);


--
-- Name: wagtailcore_workflowstate_workflow_id_1f18378f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_workflowstate_workflow_id_1f18378f ON public.wagtailcore_workflowstate USING btree (workflow_id);


--
-- Name: wagtailcore_workflowtask_task_id_ce7716fe; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_workflowtask_task_id_ce7716fe ON public.wagtailcore_workflowtask USING btree (task_id);


--
-- Name: wagtailcore_workflowtask_workflow_id_b9717175; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailcore_workflowtask_workflow_id_b9717175 ON public.wagtailcore_workflowtask USING btree (workflow_id);


--
-- Name: wagtaildocs_document_collection_id_23881625; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtaildocs_document_collection_id_23881625 ON public.wagtaildocs_document USING btree (collection_id);


--
-- Name: wagtaildocs_document_uploaded_by_user_id_17258b41; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtaildocs_document_uploaded_by_user_id_17258b41 ON public.wagtaildocs_document USING btree (uploaded_by_user_id);


--
-- Name: wagtailembeds_embed_cache_until_26c94bb0; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailembeds_embed_cache_until_26c94bb0 ON public.wagtailembeds_embed USING btree (cache_until);


--
-- Name: wagtailembeds_embed_hash_c9bd8c9a_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailembeds_embed_hash_c9bd8c9a_like ON public.wagtailembeds_embed USING btree (hash varchar_pattern_ops);


--
-- Name: wagtailforms_formsubmission_page_id_e48e93e7; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailforms_formsubmission_page_id_e48e93e7 ON public.wagtailforms_formsubmission USING btree (page_id);


--
-- Name: wagtailimages_image_collection_id_c2f8af7e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailimages_image_collection_id_c2f8af7e ON public.wagtailimages_image USING btree (collection_id);


--
-- Name: wagtailimages_image_created_at_86fa6cd4; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailimages_image_created_at_86fa6cd4 ON public.wagtailimages_image USING btree (created_at);


--
-- Name: wagtailimages_image_file_hash_fb5bbb23; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailimages_image_file_hash_fb5bbb23 ON public.wagtailimages_image USING btree (file_hash);


--
-- Name: wagtailimages_image_file_hash_fb5bbb23_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailimages_image_file_hash_fb5bbb23_like ON public.wagtailimages_image USING btree (file_hash varchar_pattern_ops);


--
-- Name: wagtailimages_image_uploaded_by_user_id_5d73dc75; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailimages_image_uploaded_by_user_id_5d73dc75 ON public.wagtailimages_image USING btree (uploaded_by_user_id);


--
-- Name: wagtailimages_rendition_filter_spec_1cba3201; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailimages_rendition_filter_spec_1cba3201 ON public.wagtailimages_rendition USING btree (filter_spec);


--
-- Name: wagtailimages_rendition_filter_spec_1cba3201_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailimages_rendition_filter_spec_1cba3201_like ON public.wagtailimages_rendition USING btree (filter_spec varchar_pattern_ops);


--
-- Name: wagtailimages_rendition_image_id_3e1fd774; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailimages_rendition_image_id_3e1fd774 ON public.wagtailimages_rendition USING btree (image_id);


--
-- Name: wagtailredirects_redirect_old_path_bb35247b; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailredirects_redirect_old_path_bb35247b ON public.wagtailredirects_redirect USING btree (old_path);


--
-- Name: wagtailredirects_redirect_old_path_bb35247b_like; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailredirects_redirect_old_path_bb35247b_like ON public.wagtailredirects_redirect USING btree (old_path varchar_pattern_ops);


--
-- Name: wagtailredirects_redirect_redirect_page_id_b5728a8f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailredirects_redirect_redirect_page_id_b5728a8f ON public.wagtailredirects_redirect USING btree (redirect_page_id);


--
-- Name: wagtailredirects_redirect_site_id_780a0e1e; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailredirects_redirect_site_id_780a0e1e ON public.wagtailredirects_redirect USING btree (site_id);


--
-- Name: wagtailsear_autocom_476c89_gin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailsear_autocom_476c89_gin ON public.wagtailsearch_indexentry USING gin (autocomplete);


--
-- Name: wagtailsear_body_90c85d_gin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailsear_body_90c85d_gin ON public.wagtailsearch_indexentry USING gin (body);


--
-- Name: wagtailsear_title_9caae0_gin; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailsear_title_9caae0_gin ON public.wagtailsearch_indexentry USING gin (title);


--
-- Name: wagtailsearch_indexentry_content_type_id_62ed694f; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX wagtailsearch_indexentry_content_type_id_62ed694f ON public.wagtailsearch_indexentry USING btree (content_type_id);


--
-- Name: workflowstate_base_ct_id_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX workflowstate_base_ct_id_idx ON public.wagtailcore_workflowstate USING btree (base_content_type_id, object_id);


--
-- Name: workflowstate_ct_id_idx; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX workflowstate_ct_id_idx ON public.wagtailcore_workflowstate USING btree (content_type_id, object_id);


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_group_id_97559544_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_group_id_97559544_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_groups auth_user_groups_user_id_6a12ed8b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user_groups
    ADD CONSTRAINT auth_user_groups_user_id_6a12ed8b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_user_user_permissions auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auth_user_user_permissions
    ADD CONSTRAINT auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_channelanalysis core_channelanalysis_client_id_1d3b01c2_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_channelanalysis
    ADD CONSTRAINT core_channelanalysis_client_id_1d3b01c2_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_connection core_connection_client_id_bd3ebbed_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_connection
    ADD CONSTRAINT core_connection_client_id_bd3ebbed_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_connection core_connection_created_by_id_77c921b8_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_connection
    ADD CONSTRAINT core_connection_created_by_id_77c921b8_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_contenttemplate core_contenttemplate_client_id_2e1a9899_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_contenttemplate
    ADD CONSTRAINT core_contenttemplate_client_id_2e1a9899_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_post core_post_client_id_88f5b031_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_post
    ADD CONSTRAINT core_post_client_id_88f5b031_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_post core_post_created_by_id_e76054c9_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_post
    ADD CONSTRAINT core_post_created_by_id_e76054c9_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_post core_post_story_id_31e37d95_fk_core_story_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_post
    ADD CONSTRAINT core_post_story_id_31e37d95_fk_core_story_id FOREIGN KEY (story_id) REFERENCES public.core_story(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_post core_post_template_id_acd96195_fk_core_contenttemplate_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_post
    ADD CONSTRAINT core_post_template_id_acd96195_fk_core_contenttemplate_id FOREIGN KEY (template_id) REFERENCES public.core_contenttemplate(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_postimage core_postimage_post_id_5d452adf_fk_core_post_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_postimage
    ADD CONSTRAINT core_postimage_post_id_5d452adf_fk_core_post_id FOREIGN KEY (post_id) REFERENCES public.core_post(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_postjob core_postjob_client_id_042d1556_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_postjob
    ADD CONSTRAINT core_postjob_client_id_042d1556_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_postjob core_postjob_connection_id_3ee9a4db_fk_core_connection_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_postjob
    ADD CONSTRAINT core_postjob_connection_id_3ee9a4db_fk_core_connection_id FOREIGN KEY (connection_id) REFERENCES public.core_connection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_postjob core_postjob_schedule_id_2907b87f_fk_core_schedule_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_postjob
    ADD CONSTRAINT core_postjob_schedule_id_2907b87f_fk_core_schedule_id FOREIGN KEY (schedule_id) REFERENCES public.core_schedule(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_posttone core_posttone_client_id_8d03519a_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_posttone
    ADD CONSTRAINT core_posttone_client_id_8d03519a_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_posttype core_posttype_client_id_1d44d7e8_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_posttype
    ADD CONSTRAINT core_posttype_client_id_1d44d7e8_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_postvideo core_postvideo_post_id_216bc28b_fk_core_post_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_postvideo
    ADD CONSTRAINT core_postvideo_post_id_216bc28b_fk_core_post_id FOREIGN KEY (post_id) REFERENCES public.core_post(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_schedule core_schedule_client_id_8ba0f82e_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_schedule
    ADD CONSTRAINT core_schedule_client_id_8ba0f82e_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_schedule core_schedule_connection_id_ff5dc738_fk_core_connection_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_schedule
    ADD CONSTRAINT core_schedule_connection_id_ff5dc738_fk_core_connection_id FOREIGN KEY (connection_id) REFERENCES public.core_connection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_schedule core_schedule_post_id_50a128a1_fk_core_post_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_schedule
    ADD CONSTRAINT core_schedule_post_id_50a128a1_fk_core_post_id FOREIGN KEY (post_id) REFERENCES public.core_post(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_schedule core_schedule_social_account_id_c5ac05ed_fk_core_soci; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_schedule
    ADD CONSTRAINT core_schedule_social_account_id_c5ac05ed_fk_core_soci FOREIGN KEY (social_account_id) REFERENCES public.core_socialaccount(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_seokeywordset core_seokeywordset_client_id_77a3745e_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_seokeywordset
    ADD CONSTRAINT core_seokeywordset_client_id_77a3745e_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_seokeywordset core_seokeywordset_topic_id_179f903f_fk_core_topic_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_seokeywordset
    ADD CONSTRAINT core_seokeywordset_topic_id_179f903f_fk_core_topic_id FOREIGN KEY (topic_id) REFERENCES public.core_topic(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_socialaccount core_socialaccount_client_id_878f9264_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_socialaccount
    ADD CONSTRAINT core_socialaccount_client_id_878f9264_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_story core_story_client_id_a104b187_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_story
    ADD CONSTRAINT core_story_client_id_a104b187_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_story core_story_created_by_id_1ce6750c_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_story
    ADD CONSTRAINT core_story_created_by_id_1ce6750c_fk_auth_user_id FOREIGN KEY (created_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_story core_story_template_id_8a2d322c_fk_core_contenttemplate_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_story
    ADD CONSTRAINT core_story_template_id_8a2d322c_fk_core_contenttemplate_id FOREIGN KEY (template_id) REFERENCES public.core_contenttemplate(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_story core_story_trend_item_id_3b684fdc_fk_core_trenditem_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_story
    ADD CONSTRAINT core_story_trend_item_id_3b684fdc_fk_core_trenditem_id FOREIGN KEY (trend_item_id) REFERENCES public.core_trenditem(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_topic core_topic_client_id_70f88e24_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_topic
    ADD CONSTRAINT core_topic_client_id_70f88e24_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_trenditem core_trenditem_client_id_bce5f984_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_trenditem
    ADD CONSTRAINT core_trenditem_client_id_bce5f984_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_trenditem core_trenditem_topic_id_f2452ce3_fk_core_topic_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_trenditem
    ADD CONSTRAINT core_trenditem_topic_id_f2452ce3_fk_core_topic_id FOREIGN KEY (topic_id) REFERENCES public.core_topic(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_trenditem core_trenditem_used_for_post_id_fb3f4342_fk_core_post_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_trenditem
    ADD CONSTRAINT core_trenditem_used_for_post_id_fb3f4342_fk_core_post_id FOREIGN KEY (used_for_post_id) REFERENCES public.core_post(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_usertenantrole core_usertenantrole_client_id_0023ee92_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_usertenantrole
    ADD CONSTRAINT core_usertenantrole_client_id_0023ee92_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_usertenantrole core_usertenantrole_user_id_14786ac6_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_usertenantrole
    ADD CONSTRAINT core_usertenantrole_user_id_14786ac6_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_vkintegration core_vkintegration_client_id_5dde4dc0_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_vkintegration
    ADD CONSTRAINT core_vkintegration_client_id_5dde4dc0_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_vkintegration core_vkintegration_owner_id_ccfbe785_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_vkintegration
    ADD CONSTRAINT core_vkintegration_owner_id_ccfbe785_fk_auth_user_id FOREIGN KEY (owner_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_weeklysourcebatch core_weeklysourcebatch_client_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_weeklysourcebatch
    ADD CONSTRAINT core_weeklysourcebatch_client_id_fkey FOREIGN KEY (client_id) REFERENCES public.core_client(id);


--
-- Name: core_weeklysourcereport core_weeklysourcereport_batch_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_weeklysourcereport
    ADD CONSTRAINT core_weeklysourcereport_batch_id_fkey FOREIGN KEY (batch_id) REFERENCES public.core_weeklysourcebatch(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_weeklysourcereport core_weeklysourcereport_client_id_3f8efd85_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_weeklysourcereport
    ADD CONSTRAINT core_weeklysourcereport_client_id_3f8efd85_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_wordstatquery core_wordstatquery_client_id_986c7f6b_fk_core_client_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_wordstatquery
    ADD CONSTRAINT core_wordstatquery_client_id_986c7f6b_fk_core_client_id FOREIGN KEY (client_id) REFERENCES public.core_client(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: core_wordstatresult core_wordstatresult_query_id_b33b01a1_fk_core_wordstatquery_id; Type: FK CONSTRAINT; Schema: public; Owner: us
--

ALTER TABLE ONLY public.core_wordstatresult
    ADD CONSTRAINT core_wordstatresult_query_id_b33b01a1_fk_core_wordstatquery_id FOREIGN KEY (query_id) REFERENCES public.core_wordstatquery(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_content_type_id_c4bce8eb_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_content_type_id_c4bce8eb_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: django_admin_log django_admin_log_user_id_c564eba6_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.django_admin_log
    ADD CONSTRAINT django_admin_log_user_id_c564eba6_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: home_homepage home_homepage_page_ptr_id_e5b77cf7_fk_wagtailcore_page_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.home_homepage
    ADD CONSTRAINT home_homepage_page_ptr_id_e5b77cf7_fk_wagtailcore_page_id FOREIGN KEY (page_ptr_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: taggit_taggeditem taggit_taggeditem_content_type_id_9957a03c_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.taggit_taggeditem
    ADD CONSTRAINT taggit_taggeditem_content_type_id_9957a03c_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: taggit_taggeditem taggit_taggeditem_tag_id_f4f5b767_fk_taggit_tag_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.taggit_taggeditem
    ADD CONSTRAINT taggit_taggeditem_tag_id_f4f5b767_fk_taggit_tag_id FOREIGN KEY (tag_id) REFERENCES public.taggit_tag(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailadmin_editingsession wagtailadmin_editing_content_type_id_4df7730e_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailadmin_editingsession
    ADD CONSTRAINT wagtailadmin_editing_content_type_id_4df7730e_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailadmin_editingsession wagtailadmin_editingsession_user_id_6e1a9b70_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailadmin_editingsession
    ADD CONSTRAINT wagtailadmin_editingsession_user_id_6e1a9b70_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_collectionviewrestriction wagtailcore_collecti_collection_id_761908ec_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_collectionviewrestriction
    ADD CONSTRAINT wagtailcore_collecti_collection_id_761908ec_fk_wagtailco FOREIGN KEY (collection_id) REFERENCES public.wagtailcore_collection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_collectionviewrestriction_groups wagtailcore_collecti_collectionviewrestri_47320efd_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_collectionviewrestriction_groups
    ADD CONSTRAINT wagtailcore_collecti_collectionviewrestri_47320efd_fk_wagtailco FOREIGN KEY (collectionviewrestriction_id) REFERENCES public.wagtailcore_collectionviewrestriction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_collectionviewrestriction_groups wagtailcore_collecti_group_id_1823f2a3_fk_auth_grou; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_collectionviewrestriction_groups
    ADD CONSTRAINT wagtailcore_collecti_group_id_1823f2a3_fk_auth_grou FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_comment wagtailcore_comment_page_id_108444b5_fk_wagtailcore_page_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_comment
    ADD CONSTRAINT wagtailcore_comment_page_id_108444b5_fk_wagtailcore_page_id FOREIGN KEY (page_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_comment wagtailcore_comment_resolved_by_id_a282aa0e_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_comment
    ADD CONSTRAINT wagtailcore_comment_resolved_by_id_a282aa0e_fk_auth_user_id FOREIGN KEY (resolved_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_comment wagtailcore_comment_revision_created_id_1d058279_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_comment
    ADD CONSTRAINT wagtailcore_comment_revision_created_id_1d058279_fk_wagtailco FOREIGN KEY (revision_created_id) REFERENCES public.wagtailcore_revision(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_comment wagtailcore_comment_user_id_0c577ca6_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_comment
    ADD CONSTRAINT wagtailcore_comment_user_id_0c577ca6_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_commentreply wagtailcore_commentr_comment_id_afc7e027_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_commentreply
    ADD CONSTRAINT wagtailcore_commentr_comment_id_afc7e027_fk_wagtailco FOREIGN KEY (comment_id) REFERENCES public.wagtailcore_comment(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_commentreply wagtailcore_commentreply_user_id_d0b3b9c3_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_commentreply
    ADD CONSTRAINT wagtailcore_commentreply_user_id_d0b3b9c3_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupapprovaltask_groups wagtailcore_groupapp_group_id_2e64b61f_fk_auth_grou; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupapprovaltask_groups
    ADD CONSTRAINT wagtailcore_groupapp_group_id_2e64b61f_fk_auth_grou FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupapprovaltask_groups wagtailcore_groupapp_groupapprovaltask_id_9a9255ea_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupapprovaltask_groups
    ADD CONSTRAINT wagtailcore_groupapp_groupapprovaltask_id_9a9255ea_fk_wagtailco FOREIGN KEY (groupapprovaltask_id) REFERENCES public.wagtailcore_groupapprovaltask(task_ptr_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupapprovaltask wagtailcore_groupapp_task_ptr_id_cfe58781_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupapprovaltask
    ADD CONSTRAINT wagtailcore_groupapp_task_ptr_id_cfe58781_fk_wagtailco FOREIGN KEY (task_ptr_id) REFERENCES public.wagtailcore_task(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupcollectionpermission wagtailcore_groupcol_collection_id_5423575a_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupcollectionpermission
    ADD CONSTRAINT wagtailcore_groupcol_collection_id_5423575a_fk_wagtailco FOREIGN KEY (collection_id) REFERENCES public.wagtailcore_collection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupcollectionpermission wagtailcore_groupcol_group_id_05d61460_fk_auth_grou; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupcollectionpermission
    ADD CONSTRAINT wagtailcore_groupcol_group_id_05d61460_fk_auth_grou FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupcollectionpermission wagtailcore_groupcol_permission_id_1b626275_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupcollectionpermission
    ADD CONSTRAINT wagtailcore_groupcol_permission_id_1b626275_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_grouppagepermission wagtailcore_grouppag_group_id_fc07e671_fk_auth_grou; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_grouppagepermission
    ADD CONSTRAINT wagtailcore_grouppag_group_id_fc07e671_fk_auth_grou FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_grouppagepermission wagtailcore_grouppag_page_id_710b114a_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_grouppagepermission
    ADD CONSTRAINT wagtailcore_grouppag_page_id_710b114a_fk_wagtailco FOREIGN KEY (page_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_grouppagepermission wagtailcore_grouppag_permission_id_05acb22e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_grouppagepermission
    ADD CONSTRAINT wagtailcore_grouppag_permission_id_05acb22e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupsitepermission wagtailcore_groupsit_group_id_e5cdbee4_fk_auth_grou; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupsitepermission
    ADD CONSTRAINT wagtailcore_groupsit_group_id_e5cdbee4_fk_auth_grou FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupsitepermission wagtailcore_groupsit_permission_id_459b1f38_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupsitepermission
    ADD CONSTRAINT wagtailcore_groupsit_permission_id_459b1f38_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_groupsitepermission wagtailcore_groupsit_site_id_245de488_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_groupsitepermission
    ADD CONSTRAINT wagtailcore_groupsit_site_id_245de488_fk_wagtailco FOREIGN KEY (site_id) REFERENCES public.wagtailcore_site(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_modellogentry wagtailcore_modellog_content_type_id_68849e77_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_modellogentry
    ADD CONSTRAINT wagtailcore_modellog_content_type_id_68849e77_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_page wagtailcore_page_alias_of_id_12945502_fk_wagtailcore_page_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_alias_of_id_12945502_fk_wagtailcore_page_id FOREIGN KEY (alias_of_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_page wagtailcore_page_content_type_id_c28424df_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_content_type_id_c28424df_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_page wagtailcore_page_latest_revision_id_e60fef51_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_latest_revision_id_e60fef51_fk_wagtailco FOREIGN KEY (latest_revision_id) REFERENCES public.wagtailcore_revision(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_page wagtailcore_page_live_revision_id_930bd822_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_live_revision_id_930bd822_fk_wagtailco FOREIGN KEY (live_revision_id) REFERENCES public.wagtailcore_revision(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_page wagtailcore_page_locale_id_3c7e30a6_fk_wagtailcore_locale_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_locale_id_3c7e30a6_fk_wagtailcore_locale_id FOREIGN KEY (locale_id) REFERENCES public.wagtailcore_locale(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_page wagtailcore_page_locked_by_id_bcb86245_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_locked_by_id_bcb86245_fk_auth_user_id FOREIGN KEY (locked_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_page wagtailcore_page_owner_id_fbf7c332_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_page
    ADD CONSTRAINT wagtailcore_page_owner_id_fbf7c332_fk_auth_user_id FOREIGN KEY (owner_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_pagelogentry wagtailcore_pageloge_content_type_id_74e7708a_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pagelogentry
    ADD CONSTRAINT wagtailcore_pageloge_content_type_id_74e7708a_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_revision wagtailcore_pagerevision_user_id_2409d2f4_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_revision
    ADD CONSTRAINT wagtailcore_pagerevision_user_id_2409d2f4_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_pagesubscription wagtailcore_pagesubs_page_id_a085e7a6_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pagesubscription
    ADD CONSTRAINT wagtailcore_pagesubs_page_id_a085e7a6_fk_wagtailco FOREIGN KEY (page_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_pagesubscription wagtailcore_pagesubscription_user_id_89d7def9_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pagesubscription
    ADD CONSTRAINT wagtailcore_pagesubscription_user_id_89d7def9_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_pageviewrestriction_groups wagtailcore_pageview_group_id_6460f223_fk_auth_grou; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pageviewrestriction_groups
    ADD CONSTRAINT wagtailcore_pageview_group_id_6460f223_fk_auth_grou FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_pageviewrestriction wagtailcore_pageview_page_id_15a8bea6_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pageviewrestriction
    ADD CONSTRAINT wagtailcore_pageview_page_id_15a8bea6_fk_wagtailco FOREIGN KEY (page_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_pageviewrestriction_groups wagtailcore_pageview_pageviewrestriction__f147a99a_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_pageviewrestriction_groups
    ADD CONSTRAINT wagtailcore_pageview_pageviewrestriction__f147a99a_fk_wagtailco FOREIGN KEY (pageviewrestriction_id) REFERENCES public.wagtailcore_pageviewrestriction(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_referenceindex wagtailcore_referenc_base_content_type_id_313cf40f_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_referenceindex
    ADD CONSTRAINT wagtailcore_referenc_base_content_type_id_313cf40f_fk_django_co FOREIGN KEY (base_content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_referenceindex wagtailcore_referenc_content_type_id_766e0336_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_referenceindex
    ADD CONSTRAINT wagtailcore_referenc_content_type_id_766e0336_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_referenceindex wagtailcore_referenc_to_content_type_id_93690bbd_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_referenceindex
    ADD CONSTRAINT wagtailcore_referenc_to_content_type_id_93690bbd_fk_django_co FOREIGN KEY (to_content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_revision wagtailcore_revision_base_content_type_id_5b4ef7bd_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_revision
    ADD CONSTRAINT wagtailcore_revision_base_content_type_id_5b4ef7bd_fk_django_co FOREIGN KEY (base_content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_revision wagtailcore_revision_content_type_id_c8cb69c0_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_revision
    ADD CONSTRAINT wagtailcore_revision_content_type_id_c8cb69c0_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_site wagtailcore_site_root_page_id_e02fb95c_fk_wagtailcore_page_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_site
    ADD CONSTRAINT wagtailcore_site_root_page_id_e02fb95c_fk_wagtailcore_page_id FOREIGN KEY (root_page_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_task wagtailcore_task_content_type_id_249ab8ba_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_task
    ADD CONSTRAINT wagtailcore_task_content_type_id_249ab8ba_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_taskstate wagtailcore_taskstat_content_type_id_0a758fdc_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_taskstate
    ADD CONSTRAINT wagtailcore_taskstat_content_type_id_0a758fdc_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_taskstate wagtailcore_taskstat_revision_id_df25a499_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_taskstate
    ADD CONSTRAINT wagtailcore_taskstat_revision_id_df25a499_fk_wagtailco FOREIGN KEY (revision_id) REFERENCES public.wagtailcore_revision(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_taskstate wagtailcore_taskstat_workflow_state_id_9239a775_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_taskstate
    ADD CONSTRAINT wagtailcore_taskstat_workflow_state_id_9239a775_fk_wagtailco FOREIGN KEY (workflow_state_id) REFERENCES public.wagtailcore_workflowstate(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_taskstate wagtailcore_taskstate_finished_by_id_13f98229_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_taskstate
    ADD CONSTRAINT wagtailcore_taskstate_finished_by_id_13f98229_fk_auth_user_id FOREIGN KEY (finished_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_taskstate wagtailcore_taskstate_task_id_c3677c34_fk_wagtailcore_task_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_taskstate
    ADD CONSTRAINT wagtailcore_taskstate_task_id_c3677c34_fk_wagtailcore_task_id FOREIGN KEY (task_id) REFERENCES public.wagtailcore_task(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_uploadedfile wagtailcore_uploaded_for_content_type_id_b0fc87b2_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_uploadedfile
    ADD CONSTRAINT wagtailcore_uploaded_for_content_type_id_b0fc87b2_fk_django_co FOREIGN KEY (for_content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_uploadedfile wagtailcore_uploaded_uploaded_by_user_id_c7580fe8_fk_auth_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_uploadedfile
    ADD CONSTRAINT wagtailcore_uploaded_uploaded_by_user_id_c7580fe8_fk_auth_user FOREIGN KEY (uploaded_by_user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowstate wagtailcore_workflow_base_content_type_id_a30dc576_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowstate
    ADD CONSTRAINT wagtailcore_workflow_base_content_type_id_a30dc576_fk_django_co FOREIGN KEY (base_content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowstate wagtailcore_workflow_content_type_id_2bb78ce1_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowstate
    ADD CONSTRAINT wagtailcore_workflow_content_type_id_2bb78ce1_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowcontenttype wagtailcore_workflow_content_type_id_b261bb37_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowcontenttype
    ADD CONSTRAINT wagtailcore_workflow_content_type_id_b261bb37_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowstate wagtailcore_workflow_current_task_state_i_3a1a0632_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowstate
    ADD CONSTRAINT wagtailcore_workflow_current_task_state_i_3a1a0632_fk_wagtailco FOREIGN KEY (current_task_state_id) REFERENCES public.wagtailcore_taskstate(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowpage wagtailcore_workflow_page_id_81e7bab6_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowpage
    ADD CONSTRAINT wagtailcore_workflow_page_id_81e7bab6_fk_wagtailco FOREIGN KEY (page_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowstate wagtailcore_workflow_requested_by_id_4090bca3_fk_auth_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowstate
    ADD CONSTRAINT wagtailcore_workflow_requested_by_id_4090bca3_fk_auth_user FOREIGN KEY (requested_by_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowtask wagtailcore_workflow_task_id_ce7716fe_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowtask
    ADD CONSTRAINT wagtailcore_workflow_task_id_ce7716fe_fk_wagtailco FOREIGN KEY (task_id) REFERENCES public.wagtailcore_task(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowstate wagtailcore_workflow_workflow_id_1f18378f_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowstate
    ADD CONSTRAINT wagtailcore_workflow_workflow_id_1f18378f_fk_wagtailco FOREIGN KEY (workflow_id) REFERENCES public.wagtailcore_workflow(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowpage wagtailcore_workflow_workflow_id_56f56ff6_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowpage
    ADD CONSTRAINT wagtailcore_workflow_workflow_id_56f56ff6_fk_wagtailco FOREIGN KEY (workflow_id) REFERENCES public.wagtailcore_workflow(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowcontenttype wagtailcore_workflow_workflow_id_9aad7cd2_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowcontenttype
    ADD CONSTRAINT wagtailcore_workflow_workflow_id_9aad7cd2_fk_wagtailco FOREIGN KEY (workflow_id) REFERENCES public.wagtailcore_workflow(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailcore_workflowtask wagtailcore_workflow_workflow_id_b9717175_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailcore_workflowtask
    ADD CONSTRAINT wagtailcore_workflow_workflow_id_b9717175_fk_wagtailco FOREIGN KEY (workflow_id) REFERENCES public.wagtailcore_workflow(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtaildocs_document wagtaildocs_document_collection_id_23881625_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtaildocs_document
    ADD CONSTRAINT wagtaildocs_document_collection_id_23881625_fk_wagtailco FOREIGN KEY (collection_id) REFERENCES public.wagtailcore_collection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtaildocs_document wagtaildocs_document_uploaded_by_user_id_17258b41_fk_auth_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtaildocs_document
    ADD CONSTRAINT wagtaildocs_document_uploaded_by_user_id_17258b41_fk_auth_user FOREIGN KEY (uploaded_by_user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailforms_formsubmission wagtailforms_formsub_page_id_e48e93e7_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailforms_formsubmission
    ADD CONSTRAINT wagtailforms_formsub_page_id_e48e93e7_fk_wagtailco FOREIGN KEY (page_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailimages_image wagtailimages_image_collection_id_c2f8af7e_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailimages_image
    ADD CONSTRAINT wagtailimages_image_collection_id_c2f8af7e_fk_wagtailco FOREIGN KEY (collection_id) REFERENCES public.wagtailcore_collection(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailimages_image wagtailimages_image_uploaded_by_user_id_5d73dc75_fk_auth_user; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailimages_image
    ADD CONSTRAINT wagtailimages_image_uploaded_by_user_id_5d73dc75_fk_auth_user FOREIGN KEY (uploaded_by_user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailimages_rendition wagtailimages_rendit_image_id_3e1fd774_fk_wagtailim; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailimages_rendition
    ADD CONSTRAINT wagtailimages_rendit_image_id_3e1fd774_fk_wagtailim FOREIGN KEY (image_id) REFERENCES public.wagtailimages_image(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailredirects_redirect wagtailredirects_red_redirect_page_id_b5728a8f_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailredirects_redirect
    ADD CONSTRAINT wagtailredirects_red_redirect_page_id_b5728a8f_fk_wagtailco FOREIGN KEY (redirect_page_id) REFERENCES public.wagtailcore_page(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailredirects_redirect wagtailredirects_red_site_id_780a0e1e_fk_wagtailco; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailredirects_redirect
    ADD CONSTRAINT wagtailredirects_red_site_id_780a0e1e_fk_wagtailco FOREIGN KEY (site_id) REFERENCES public.wagtailcore_site(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailsearch_indexentry wagtailsearch_indexe_content_type_id_62ed694f_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailsearch_indexentry
    ADD CONSTRAINT wagtailsearch_indexe_content_type_id_62ed694f_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: wagtailusers_userprofile wagtailusers_userprofile_user_id_59c92331_fk_auth_user_id; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.wagtailusers_userprofile
    ADD CONSTRAINT wagtailusers_userprofile_user_id_59c92331_fk_auth_user_id FOREIGN KEY (user_id) REFERENCES public.auth_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: DEFAULT PRIVILEGES FOR SEQUENCES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON SEQUENCES TO us;


--
-- Name: DEFAULT PRIVILEGES FOR FUNCTIONS; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON FUNCTIONS TO us;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: public; Owner: postgres
--

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public GRANT ALL ON TABLES TO us;


--
-- PostgreSQL database dump complete
--

\unrestrict hjyLyjTlX5FyLwNH6Bxzca3zJzP2CqKKtkaHkQOZpAsGsLhJxJnbz8c0XbsGINA

