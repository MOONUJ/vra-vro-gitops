# -*- coding: utf-8 -*-
import os
import sys
import json
import zipfile
import shutil
import tempfile
import argparse
import uuid
import logging
import re
from datetime import datetime
from urllib.parse import quote
from vro_client import VroClient
from vra_client import VraClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("vcf_provision")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    """
    Loads config.json. If it doesn't exist, warns the user.
    """
    if not os.path.exists(CONFIG_PATH):
        logger.error(f"Configuration file not found at {CONFIG_PATH}.")
        logger.error("Please copy config.json.template to config.json and fill in your details.")
        sys.exit(1)
        
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def zip_dir(dir_path, zip_file_path):
    """
    Compresses a directory into a zip file.
    """
    logger.info(f"Compressing {dir_path} to {zip_file_path}...")
    with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_full_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_full_path, dir_path)
                zip_file.write(file_full_path, rel_path)

def unzip_file(zip_file_path, dest_dir):
    """
    Extracts a zip file to a destination directory.
    """
    logger.info(f"Extracting {zip_file_path} to {dest_dir}...")
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        zip_ref.extractall(dest_dir)

def backup(vra_client, vro_client, config, version, output_dir):
    """
    Day-1 Backup: Fetches all logical catalogs/configurations from target server
    and generates a deployment artifact package (zip for vRA, .package for vRO).
    """
    tag = config.get("gitops_tag")
    if not tag:
        logger.error("No 'gitops_tag' configured in config.json. Cannot run backup.")
        sys.exit(1)

    target_projects = config.get("projects", [])
    logger.info(f"=== Starting Day-1 Backup for version: {version} (Tag: {tag}) ===")

    # Create target output folder
    target_output_dir = os.path.abspath(os.path.join(output_dir, version))
    os.makedirs(target_output_dir, exist_ok=True)

    # 1. Fetch projects cache
    try:
        projects = vra_client.get_projects()
        projects_by_id = {p["id"]: p for p in projects}
        projects_by_name = {p["name"]: p["id"] for p in projects}
    except Exception as e:
        logger.error(f"Failed to fetch projects cache: {e}")
        projects_by_id = {}
        projects_by_name = {}

    target_project_ids = [projects_by_name[name] for name in target_projects if name in projects_by_name]
    
    def is_project_allowed(proj_id):
        if not target_projects:
            return True
        return proj_id in target_project_ids

    # Create a temporary folder for vRA files
    vra_temp_dir = tempfile.mkdtemp()
    
    manifest_components = {
        "blueprints": [],
        "abx_actions": [],
        "custom_resources": [],
        "resource_actions": [],
        "catalog_sources": [],
        "policies": [],
        "subscriptions": [],
        "custom_forms": [],
        "workflow_sources": [],
        "workflow_forms": [],
        "naming_policies": [],
        "vro_package": None
    }

    try:
        # 1. Backup Blueprints
        logger.info("Backing up vRA Blueprints...")
        blueprints = vra_client.list_blueprints()
        matching_bps = [bp for bp in blueprints if is_project_allowed(bp.get("projectId"))]
        
        bp_dir = os.path.join(vra_temp_dir, "blueprints")
        os.makedirs(bp_dir, exist_ok=True)
        for bp in matching_bps:
            bp_id = bp["id"]
            bp_name = bp["name"]
            try:
                full_bp = vra_client.get_blueprint(bp_id)
                content = (full_bp.get("content") or "") if full_bp else ""
                proj_id = full_bp.get("projectId") if full_bp else None
                proj_name = projects_by_id.get(proj_id, {}).get("name", "global")
                
                bp_sub_dir = os.path.join(bp_dir, bp_name)
                os.makedirs(bp_sub_dir, exist_ok=True)
                
                meta = dict(full_bp)
                meta.pop("content", None)
                meta["projectName"] = proj_name
                
                with open(os.path.join(bp_sub_dir, "blueprint.json"), "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=4, ensure_ascii=False)
                with open(os.path.join(bp_sub_dir, "blueprint.yaml"), "w", encoding="utf-8") as f:
                    f.write(content)
                    
                manifest_components["blueprints"].append(bp_name)
                logger.info(f"  - Blueprint: '{bp_name}' (Project: {proj_name})")
            except Exception as e:
                logger.error(f"Failed to backup blueprint '{bp_name}': {e}")

        # 2. Backup ABX Actions
        logger.info("Backing up ABX Actions...")
        abx_actions = vra_client.list_abx_actions()
        matching_abxs = [act for act in abx_actions if is_project_allowed(act.get("projectId"))]
        
        abx_dir = os.path.join(vra_temp_dir, "abx")
        os.makedirs(abx_dir, exist_ok=True)
        for act in matching_abxs:
            act_id = act["id"]
            act_name = act["name"]
            try:
                proj_id = act.get("projectId")
                proj_name = projects_by_id.get(proj_id, {}).get("name", "global")
                
                act_sub_dir = os.path.join(abx_dir, act_name)
                os.makedirs(act_sub_dir, exist_ok=True)
                
                script_code = act.get("source", "")
                runtime = act.get("runtime", "python")
                ext = "js" if "node" in runtime else "py"
                
                with open(os.path.join(act_sub_dir, f"source.{ext}"), "w", encoding="utf-8") as f:
                    f.write(script_code)
                
                meta = dict(act)
                meta.pop("source", None)
                meta["projectName"] = proj_name
                
                with open(os.path.join(act_sub_dir, "init.json"), "w", encoding="utf-8") as f:
                    json.dump(meta, f, indent=4, ensure_ascii=False)
                    
                manifest_components["abx_actions"].append(act_name)
                logger.info(f"  - ABX Action: '{act_name}' (Project: {proj_name})")
            except Exception as e:
                logger.error(f"Failed to backup ABX Action '{act_name}': {e}")

        # Flat resources helper
        def backup_flats(sub_folder, list_func, get_func, label, manifest_key):
            logger.info(f"Backing up {label}...")
            items = list_func()
            
            # Apply project filter if needed
            if label == "Catalog Source" and target_projects:
                items = [i for i in items if not i.get("projectId") or is_project_allowed(i.get("projectId"))]
            elif label == "Catalog Policy" and target_projects:
                # Filter policies by project matching
                filtered = []
                for p in items:
                    proj_id = p.get("projectId")
                    if proj_id and is_project_allowed(proj_id):
                        filtered.append(p)
                        continue
                    # Check properties.projects
                    proj_list = p.get("properties", {}).get("projects", [])
                    if any(p_id in target_project_ids for p_id in proj_list):
                        filtered.append(p)
                        continue
                    # Org level / no projects
                    if not proj_id and not proj_list:
                        filtered.append(p)
                        continue
                items = filtered
            elif label == "Naming Policy" and target_projects:
                filtered = []
                for n in items:
                    scope = n.get("scope")
                    if scope == "organization":
                        filtered.append(n)
                        continue
                    n_projs = n.get("projects", [])
                    if any(p.get("projectId") == "*" or p.get("projectId") in target_project_ids for p in n_projs):
                        filtered.append(n)
                        continue
                items = filtered

            folder_path = os.path.join(vra_temp_dir, sub_folder)
            os.makedirs(folder_path, exist_ok=True)
            
            for item in items:
                name = item.get("name") or item.get("displayName") or item.get("id")
                item_id = item.get("id")
                try:
                    full_item = get_func(item_id) if get_func else item
                    if full_item is None:
                        full_item = item
                    with open(os.path.join(folder_path, f"{name}.json"), "w", encoding="utf-8") as f:
                        json.dump(full_item, f, indent=4, ensure_ascii=False)
                    manifest_components[manifest_key].append(name)
                    logger.info(f"  - {label}: '{name}'")
                except Exception as e:
                    logger.error(f"Failed to backup {label} '{name}': {e}")

        # 3. Custom Resources
        backup_flats("custom_resources", vra_client.list_custom_resources, vra_client.get_custom_resource, "Custom Resource", "custom_resources")
        # 4. Resource Actions
        backup_flats("resource_actions", vra_client.list_resource_actions, vra_client.get_resource_action, "Resource Action", "resource_actions")
        # 5. Catalog Sources
        backup_flats("catalog_sources", vra_client.list_catalog_sources, vra_client.get_catalog_source, "Catalog Source", "catalog_sources")
        # 6. Policies
        backup_flats("policies", vra_client.list_policies, vra_client.get_policy, "Catalog Policy", "policies")
        # 7. Subscriptions
        backup_flats("subscriptions", lambda: [s for s in vra_client.list_subscriptions() if not s.get("system", False) and s.get("type") == "RUNNABLE"], vra_client.get_subscription, "Subscription", "subscriptions")
        # 7.5 Naming Policies
        backup_flats("naming_policies", vra_client.list_naming_policies, vra_client.get_naming_policy, "Naming Policy", "naming_policies")

        # 8. Custom Forms
        logger.info("Backing up Custom Forms...")
        items = vra_client.list_catalog_items()
        form_dir = os.path.join(vra_temp_dir, "custom_forms")
        os.makedirs(form_dir, exist_ok=True)
        for item in items:
            proj_id = item.get("projectId")
            if target_projects and proj_id and not is_project_allowed(proj_id):
                continue
            item_id = item.get("id")
            item_name = item.get("name")
            item_type = item.get("type", {}).get("id")
            try:
                form_data = vra_client.get_custom_form(item_type, item_id)
                if form_data and form_data.get("status") == "ON":
                    with open(os.path.join(form_dir, f"{item_name}.json"), "w", encoding="utf-8") as f:
                        json.dump(form_data, f, indent=4, ensure_ascii=False)
                    manifest_components["custom_forms"].append(item_name)
                    logger.info(f"  - Custom Form: '{item_name}'")
            except Exception as e:
                logger.debug(f"Failed to backup Custom Form for '{item_name}': {e}")

        # 8.5 Backup Workflow Sources and Forms
        logger.info("Backing up Workflow Sources and forms...")
        wf_sources_dir = os.path.join(vra_temp_dir, "workflow_sources")
        wf_forms_dir = os.path.join(vra_temp_dir, "workflow_forms")
        os.makedirs(wf_sources_dir, exist_ok=True)
        os.makedirs(wf_forms_dir, exist_ok=True)

        try:
            catalog_sources = vra_client.list_catalog_sources()
            wf_sources = [s for s in catalog_sources if s.get("typeId") == "com.vmw.vro.workflow"]
            
            for source in wf_sources:
                source_name = source.get("name")
                # Save workflow source metadata
                with open(os.path.join(wf_sources_dir, f"{source_name}.json"), "w", encoding="utf-8") as f:
                    json.dump(source, f, indent=4, ensure_ascii=False)
                manifest_components["workflow_sources"].append(source_name)
                logger.info(f"  - Workflow Source: '{source_name}'")

                # Get workflows inside this source and search custom forms for them
                config_workflows = source.get("config", {}).get("workflows", [])
                for wf in config_workflows:
                    wf_name = wf.get("name")
                    try:
                        search_url = f"/form-service/api/forms/search?term={quote(wf_name)}"
                        search_resp = vra_client.request("GET", search_url)
                        if search_resp.status_code < 400:
                            search_results = search_resp.json()
                            form_list = search_results.get("content", search_results) if isinstance(search_results, dict) else search_results
                            if not isinstance(form_list, list):
                                form_list = [form_list] if form_list else []
                            for form_summary in form_list:
                                form_id = form_summary.get("formId") or form_summary.get("id")
                                if not form_id:
                                    continue
                                # Fetch full form
                                form_resp = vra_client.request("GET", f"/form-service/api/forms/{form_id}")
                                if form_resp.status_code < 400:
                                    form_data = form_resp.json()
                                    if form_data.get("status") == "ON" and form_data.get("formName") == wf_name:
                                        with open(os.path.join(wf_forms_dir, f"{wf_name}.json"), "w", encoding="utf-8") as f_out:
                                            json.dump(form_data, f_out, indent=4, ensure_ascii=False)
                                        manifest_components["workflow_forms"].append(wf_name)
                                        logger.info(f"  - Workflow Custom Form: '{wf_name}'")
                                        break
                    except Exception as e:
                        logger.warning(f"Failed to backup workflow custom form for '{wf_name}': {e}")
        except Exception as e:
            logger.error(f"Failed to backup workflow sources: {e}")

        # Compress all vRA configs into zip
        zip_file_name = f"vra-artifacts-{version}.zip"
        zip_file_path = os.path.join(target_output_dir, zip_file_name)
        zip_dir(vra_temp_dir, zip_file_path)
        manifest_components["vra_artifacts_zip"] = zip_file_name

    finally:
        shutil.rmtree(vra_temp_dir)

    # 9. Backup vRO Package
    logger.info("Backing up vRO Package...")
    pkg_config = config.get("package", {})
    pkg_name = pkg_config.get("name")
    if pkg_name:
        package_file_name = f"vro-package-{version}.package"
        package_dest_path = os.path.join(target_output_dir, package_file_name)
        try:
            # Rebuild package with tagged components first
            logger.info(f"Re-assembling package '{pkg_name}' elements on the server before export...")
            discovered_workflows = vro_client.find_resources_by_tag("Workflow", tag)
            discovered_actions = vro_client.find_resources_by_tag("Action", tag)
            discovered_configs = vro_client.find_resources_by_tag("ConfigurationElement", tag)
            discovered_resources = vro_client.find_resources_by_tag("ResourceElement", tag)

            # Bump versions of discoverable items on the server to match target version
            logger.info(f"Bumping version numbers of discovered items on server to '{version}'...")
            for wf in discovered_workflows:
                try:
                    wf_meta = vro_client.get_workflow(wf["id"])
                    if wf_meta:
                        wf_meta["version"] = version
                        vro_client.update_workflow(wf["id"], wf_meta)
                        logger.info(f"  - Bumped workflow '{wf['name']}' to version {version}")
                except Exception as e:
                    logger.warning(f"Failed to bump version for workflow '{wf['name']}': {e}")

            for act in discovered_actions:
                try:
                    act_meta = vro_client.get_action(act["id"])
                    if act_meta:
                        act_meta["version"] = version
                        vro_client.update_action(act["id"], act_meta)
                        logger.info(f"  - Bumped action '{act['name']}' to version {version}")
                except Exception as e:
                    logger.warning(f"Failed to bump version for action '{act['name']}': {e}")

            for cfg in discovered_configs:
                try:
                    cfg_meta = vro_client.get_configuration(cfg["id"])
                    if cfg_meta:
                        cfg_meta["version"] = version
                        vro_client.update_configuration(cfg["id"], cfg_meta)
                        logger.info(f"  - Bumped configuration '{cfg['name']}' to version {version}")
                except Exception as e:
                    logger.warning(f"Failed to bump version for configuration '{cfg['name']}': {e}")

            for res in discovered_resources:
                try:
                    res_meta = vro_client.get_resource(res["id"])
                    if res_meta:
                        res_meta["version"] = version
                        vro_client.update_resource_metadata(res["id"], res_meta)
                        logger.info(f"  - Bumped resource '{res['name']}' to version {version}")
                except Exception as e:
                    logger.warning(f"Failed to bump version for resource '{res['name']}': {e}")

            workflow_ids = [w["id"] for w in discovered_workflows]
            action_ids = [a["id"] for a in discovered_actions]
            config_ids = [c["id"] for c in discovered_configs]
            resource_ids = [r["id"] for r in discovered_resources]

            vro_client.create_or_update_package(
                package_name=pkg_name,
                workflow_ids=workflow_ids,
                action_ids=action_ids,
                config_ids=config_ids,
                resource_ids=resource_ids
            )
            # Export the package binary
            vro_client.export_package(pkg_name, package_dest_path)
            manifest_components["vro_package"] = package_file_name
        except Exception as e:
            logger.error(f"Failed to export vRO Package '{pkg_name}': {e}")
    else:
        logger.warning("No vRO package name configured. Skipping vRO package backup.")

    # 10. Generate manifest.json
    manifest_data = {
        "version": version,
        "backup_timestamp": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "gitops_tag": tag,
        "components": manifest_components
    }
    with open(os.path.join(target_output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest_data, f, indent=4, ensure_ascii=False)

    logger.info(f"=== Day-1 Backup completed for version: {version}. Artifacts saved at {target_output_dir} ===")

def restore(vra_client, vro_client, config, version, input_dir):
    """
    Day-1 Restore: Loads the deployment artifacts (zip & .package) for a specific version
    and applies them to the target server, creating skeletons or initializing configurations.
    """
    logger.info(f"=== Starting Day-1 Restore for version: {version} ===")
    
    artifact_path = os.path.abspath(os.path.join(input_dir, version))
    manifest_file = os.path.join(artifact_path, "manifest.json")
    if not os.path.exists(manifest_file):
        logger.error(f"Manifest file not found at {manifest_file}. Cannot proceed.")
        sys.exit(1)

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    components = manifest.get("components", {})
    vro_package_name = components.get("vro_package")
    vra_artifacts_zip = components.get("vra_artifacts_zip")

    # 1. Provision vRO Package
    if vro_package_name:
        package_file_path = os.path.join(artifact_path, vro_package_name)
        if os.path.exists(package_file_path):
            try:
                logger.info(f"Importing vRO package: {vro_package_name}...")
                vro_client.import_package(package_file_path, overwrite=True)
                logger.info("vRO package imported successfully.")
            except Exception as e:
                logger.error(f"Failed to import vRO package: {e}")
        else:
            logger.warning(f"vRO package file not found at {package_file_path}")

    # 2. Provision vRA Configurations
    if vra_artifacts_zip:
        zip_file_path = os.path.join(artifact_path, vra_artifacts_zip)
        if not os.path.exists(zip_file_path):
            logger.error(f"vRA artifacts zip file not found at {zip_file_path}")
            sys.exit(1)

        # Extract zip to temp directory
        vra_temp_dir = tempfile.mkdtemp()
        try:
            unzip_file(zip_file_path, vra_temp_dir)
            
            # Fetch target projects map for ID resolution
            try:
                projects = vra_client.get_projects()
                projects_by_name = {p["name"]: p["id"] for p in projects}
            except Exception as e:
                logger.error(f"Failed to fetch projects cache: {e}")
                projects_by_name = {}

            target_projects_config = config.get("projects", [])
            target_project_id = None
            if target_projects_config and target_projects_config[0] in projects_by_name:
                target_project_id = projects_by_name[target_projects_config[0]]
            else:
                target_project_id = list(projects_by_name.values())[0] if projects_by_name else "default-project-id"

            def resolve_project_id(proj_name):
                if proj_name in projects_by_name:
                    return projects_by_name[proj_name]
                if target_projects_config and target_projects_config[0] in projects_by_name:
                    return projects_by_name[target_projects_config[0]]
                return target_project_id

            # Fetch target project name for name normalization to prevent catalog source duplicates
            try:
                proj_resp = vra_client.request("GET", f"/iaas/api/projects/{target_project_id}")
                target_project_name = proj_resp.json().get("name", "admin") if proj_resp.status_code < 400 else "admin"
            except Exception as e:
                logger.warning(f"Failed to fetch target project name: {e}")
                target_project_name = "admin"

            # Build old_id_to_name map for catalog sources to map policies correctly
            old_id_to_name = {}
            catalog_sources_backup_dir = os.path.join(vra_temp_dir, "catalog_sources")
            if os.path.exists(catalog_sources_backup_dir):
                for file in os.listdir(catalog_sources_backup_dir):
                    if file.endswith(".json"):
                        try:
                            with open(os.path.join(catalog_sources_backup_dir, file), "r", encoding="utf-8") as f:
                                cs_data = json.load(f)
                                if cs_data.get("id") and cs_data.get("name"):
                                    old_id_to_name[cs_data["id"]] = cs_data["name"]
                        except Exception as e:
                            logger.warning(f"Failed to read catalog source for ID mapping: {e}")

            catalog_source_name_to_id = {}

            # 2.1 Provision Blueprints
            bp_root = os.path.join(vra_temp_dir, "blueprints")
            if os.path.exists(bp_root):
                for bp_name in os.listdir(bp_root):
                    bp_dir = os.path.join(bp_root, bp_name)
                    if not os.path.isdir(bp_dir):
                        continue
                    
                    json_path = os.path.join(bp_dir, "blueprint.json")
                    yaml_path = os.path.join(bp_dir, "blueprint.yaml")
                    if os.path.exists(json_path) and os.path.exists(yaml_path):
                        try:
                            with open(json_path, "r", encoding="utf-8") as f:
                                bp_meta = json.load(f)
                            with open(yaml_path, "r", encoding="utf-8") as f:
                                yaml_content = f.read()
                                
                            proj_name = bp_meta.get("projectName", "global")
                            proj_id = resolve_project_id(proj_name)
                            
                            payload = dict(bp_meta)
                            payload["content"] = yaml_content
                            payload["projectId"] = proj_id
                            payload.pop("projectName", None)
                            
                            # Check existence
                            server_bps = vra_client.list_blueprints()
                            existing_bp = next((b for b in server_bps if b["name"] == bp_name), None)
                            
                            if existing_bp:
                                logger.info(f"Updating blueprint '{bp_name}'...")
                                vra_client.update_blueprint(existing_bp["id"], payload)
                            else:
                                logger.info(f"Creating blueprint '{bp_name}'...")
                                vra_client.create_blueprint(payload)
                                
                            # Publish version (Unrelease any existing released versions first to match Install Value Pack workflow)
                            try:
                                # Re-list to ensure we have the correct ID
                                updated_bps = vra_client.list_blueprints()
                                final_bp = next((b for b in updated_bps if b["name"] == bp_name), None)
                                if final_bp:
                                    # 1. Unrelease any currently released versions
                                    versions_resp = vra_client.request("GET", f"/blueprint/api/blueprints/{final_bp['id']}/versions")
                                    if versions_resp.status_code < 400:
                                        for ver_item in versions_resp.json().get("content", []):
                                            if ver_item.get("status") == "RELEASED":
                                                ver_item["status"] = "VERSIONED"
                                                vra_client.request(
                                                    "POST", 
                                                    f"/blueprint/api/blueprints/{final_bp['id']}/versions/{ver_item['id']}/actions/unrelease", 
                                                    json=ver_item
                                                )
                                                logger.info(f"  - Unreleased existing version '{ver_item.get('version')}' for blueprint '{bp_name}'")
                                    
                                    # 2. Publish new version with unique timestamp
                                    version_to_publish = f"{version}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
                                    vra_client.publish_blueprint_version(final_bp["id"], version_to_publish)
                                    logger.info(f"  - Published new version '{version_to_publish}' for blueprint '{bp_name}'")
                            except Exception as pe:
                                logger.warning(f"Could not publish version for blueprint '{bp_name}': {pe}")
                        except Exception as e:
                            logger.error(f"Failed to provision blueprint '{bp_name}': {e}")

            # 2.2 Provision ABX Actions
            abx_root = os.path.join(vra_temp_dir, "abx")
            provisioned_abxs = {}
            if os.path.exists(abx_root):
                for abx_name in os.listdir(abx_root):
                    abx_dir = os.path.join(abx_root, abx_name)
                    if not os.path.isdir(abx_dir):
                        continue
                    
                    init_path = os.path.join(abx_dir, "init.json")
                    script_path = None
                    for file in os.listdir(abx_dir):
                        if file.startswith("source."):
                            script_path = os.path.join(abx_dir, file)
                            break
                            
                    if os.path.exists(init_path) and script_path:
                        try:
                            with open(init_path, "r", encoding="utf-8") as f:
                                abx_meta = json.load(f)
                            with open(script_path, "r", encoding="utf-8") as f:
                                script_code = f.read()
                                
                            proj_name = abx_meta.get("projectName", "global")
                            proj_id = resolve_project_id(proj_name)
                            
                            payload = dict(abx_meta)
                            payload["source"] = script_code
                            payload["projectId"] = proj_id
                            payload.pop("projectName", None)
                            
                            # Check existence
                            server_acts = vra_client.list_abx_actions()
                            existing_act = next((a for a in server_acts if a["name"] == abx_name and a.get("projectId") == proj_id), None)
                            
                            if existing_act:
                                logger.info(f"Updating ABX Action '{abx_name}'...")
                                updated = vra_client.update_abx_action(existing_act["id"], payload)
                                provisioned_abxs[abx_name] = updated if updated else existing_act
                            else:
                                logger.info(f"Creating ABX Action '{abx_name}'...")
                                created = vra_client.create_abx_action(payload)
                                provisioned_abxs[abx_name] = created
                        except Exception as e:
                            logger.error(f"Failed to provision ABX Action '{abx_name}': {e}")

            # Flat resources provision helper for policies/catalog sources
            def provision_flat_resources(sub_folder, list_func, create_func, update_func, label):
                folder_path = os.path.join(vra_temp_dir, sub_folder)
                if not os.path.exists(folder_path):
                    return
                    
                for file in os.listdir(folder_path):
                    if not file.endswith(".json"):
                        continue
                        
                    file_path = os.path.join(folder_path, file)
                    name = os.path.splitext(file)[0]
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                            
                        if label == "Catalog Source":
                            type_id = payload.get("typeId")
                            if type_id == "com.vmw.vro.workflow":
                                logger.info(f"Skipping vRO Workflow Catalog Source '{name}' in flat resources step. It will be handled in step 2.8.")
                                continue
                            elif type_id == "com.vmw.blueprint":
                                payload["config"] = payload.get("config", {})
                                payload["config"]["sourceProjectId"] = target_project_id
                                payload["projectId"] = target_project_id
                                # Sanitize system / read-only / target-specific fields that cause 400 Bad Request
                                for k in ["createdAt", "createdBy", "lastUpdatedAt", "lastUpdatedBy", "itemsImported", "itemsFound", "lastImportStartedAt", "lastImportCompletedAt", "lastImportErrors", "originOrgId", "iconId"]:
                                    payload.pop(k, None)
                                # Force name to match target project name to prevent duplicates
                                payload["name"] = target_project_name
                                name = target_project_name

                        # If catalog policy, map target projects and map catalog sources
                        if label == "Catalog Policy":
                            payload.pop("orgId", None)
                            proj_list = payload.get("properties", {}).get("projects", [])
                            mapped_projs = []
                            for p in proj_list:
                                if p in projects_by_name:
                                    mapped_projs.append(projects_by_name[p])
                                else:
                                    mapped_projs.append(p)
                            if mapped_projs:
                                payload["properties"]["projects"] = mapped_projs
                            else:
                                payload["properties"] = payload.get("properties", {})
                                payload["properties"]["projects"] = [target_project_id]

                            # Map old catalog source IDs to new IDs
                            entitled_users = payload.get("definition", {}).get("entitledUsers", [])
                            for user_ent in entitled_users:
                                items = user_ent.get("items", [])
                                for item in items:
                                    if item.get("type") == "CATALOG_SOURCE_IDENTIFIER":
                                        old_id = item.get("id")
                                        name_mapped = old_id_to_name.get(old_id)
                                        if name_mapped and name_mapped in catalog_source_name_to_id:
                                            new_cs_id = catalog_source_name_to_id[name_mapped]
                                            logger.info(f"Mapping catalog source '{name_mapped}' in policy: {old_id} -> {new_cs_id}")
                                            item["id"] = new_cs_id
                                        else:
                                            logger.warning(f"Could not map catalog source ID {old_id} in policy (name matching failed).")

                        if label == "Naming Policy":
                            payload.pop("orgId", None)
                            proj_list = payload.get("projects", [])
                            mapped_projs = []
                            for p in proj_list:
                                p_id = p.get("projectId")
                                p_name = p.get("projectName")
                                if p_id == "*":
                                    mapped_projs.append(p)
                                elif p_name in projects_by_name:
                                    mapped_projs.append({
                                        "projectId": projects_by_name[p_name],
                                        "projectName": p_name
                                    })
                                else:
                                    if target_projects_config and target_projects_config[0] in projects_by_name:
                                        t_proj_id = projects_by_name[target_projects_config[0]]
                                        t_proj_name = target_projects_config[0]
                                    else:
                                        t_proj_id = target_project_id
                                        t_proj_name = target_project_name
                                    mapped_projs.append({
                                        "projectId": t_proj_id,
                                        "projectName": t_proj_name
                                    })
                            payload["projects"] = mapped_projs
                        
                        server_items = list_func()
                        existing_item = None
                        for item in server_items:
                            item_name = item.get("name") or item.get("displayName")
                            if item_name == name:
                                existing_item = item
                                break
                                
                        new_id = None
                        if existing_item:
                            logger.info(f"Updating {label} '{name}'...")
                            payload["id"] = existing_item["id"]
                            resp_data = update_func(existing_item["id"], payload)
                            new_id = (resp_data or {}).get("id") or existing_item["id"]
                        else:
                            logger.info(f"Creating {label} '{name}'...")
                            payload.pop("id", None)
                            resp_data = create_func(payload)
                            new_id = (resp_data or {}).get("id")
                            
                        if label == "Catalog Source" and new_id:
                            catalog_source_name_to_id[name] = new_id
                            if name == target_project_name:
                                catalog_source_name_to_id["admin"] = new_id
                            logger.info(f"Cached Catalog Source '{name}' ID: {new_id}")
                    except Exception as e:
                        err_msg = f"Failed to provision {label} '{name}': {e}"
                        if hasattr(e, "response") and e.response is not None:
                            err_msg += f" | Response: {e.response.text}"
                        logger.error(err_msg)

            # 2.3 Provision Custom Resources
            cr_root = os.path.join(vra_temp_dir, "custom_resources")
            if os.path.exists(cr_root):
                for file in os.listdir(cr_root):
                    if not file.endswith(".json"):
                        continue
                    file_path = os.path.join(cr_root, file)
                    name = os.path.splitext(file)[0]
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                            
                        proj_name = payload.get("projectName", "global")
                        proj_id = resolve_project_id(proj_name)
                        
                        # Process additionalActions
                        additional_actions = []
                        for action in payload.get("additionalActions", []):
                            action["orgId"] = None
                            if action.get("runnableItem", {}).get("type") == "vro.workflow":
                                wf_id = action["runnableItem"]["id"]
                                try:
                                    wf_resp = vra_client.request("GET", f"/vro/workflows/{wf_id}")
                                    if wf_resp.status_code < 400:
                                        action["runnableItem"]["endpointLink"] = wf_resp.json().get("integration", {}).get("endpointConfigurationLink")
                                except Exception as we:
                                    logger.warning(f"Failed to fetch endpointLink for workflow '{wf_id}': {we}")
                            else:
                                abx_name = action.get("runnableItem", {}).get("name")
                                if abx_name in provisioned_abxs:
                                    action["runnableItem"]["id"] = provisioned_abxs[abx_name]["id"]
                                action["runnableItem"]["projectId"] = proj_id
                                
                            form_def = action.get("formDefinition") or {}
                            form_def["id"] = None
                            form_def["tenant"] = None
                            form_def["externalSourceFormSchemas"] = None
                            action["formDefinition"] = form_def
                            
                            ra_resp = vra_client.request(
                                "POST", 
                                "/form-service/api/custom/resource-actions", 
                                params={"generateUnvalidatableExternalValuesSchema": "true"}, 
                                json=action
                            )
                            if ra_resp.status_code < 400:
                                additional_actions.append(ra_resp.json())
                            else:
                                logger.error(f"Failed to provision additional resource action for custom resource '{name}': {ra_resp.text}")
                                additional_actions.append(action)
                        payload["additionalActions"] = additional_actions
                        
                        # Process mainActions
                        main_acts = payload.get("mainActions", {})
                        for act_key in ["create", "read", "delete", "update"]:
                            m_act = main_acts.get(act_key)
                            if m_act:
                                abx_name = m_act.get("name")
                                if abx_name in provisioned_abxs:
                                    m_act["id"] = provisioned_abxs[abx_name]["id"]
                                m_act["projectId"] = proj_id
                                main_acts[act_key] = m_act
                        payload["mainActions"] = main_acts
                        
                        server_crs = vra_client.list_custom_resources()
                        existing_cr = next((cr for cr in server_crs if cr.get("resourceType") == payload.get("resourceType")), None)
                        
                        if existing_cr:
                            logger.info(f"Updating Custom Resource '{name}'...")
                            payload["id"] = existing_cr["id"]
                            vra_client.update_custom_resource(existing_cr["id"], payload)
                        else:
                            logger.info(f"Creating Custom Resource '{name}'...")
                            payload.pop("id", None)
                            vra_client.create_custom_resource(payload)
                    except Exception as e:
                        logger.error(f"Failed to provision Custom Resource '{name}': {e}")

            # 2.4 Provision Resource Actions
            ra_root = os.path.join(vra_temp_dir, "resource_actions")
            if os.path.exists(ra_root):
                for file in os.listdir(ra_root):
                    if not file.endswith(".json"):
                        continue
                    file_path = os.path.join(ra_root, file)
                    name = os.path.splitext(file)[0]
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                            
                        proj_name = payload.get("projectName", "global")
                        proj_id = resolve_project_id(proj_name)
                        
                        payload["description"] = f"GVP updated on {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}"
                        payload["orgId"] = None
                        
                        run_item = payload.get("runnableItem", {})
                        if run_item.get("type") == "vro.workflow":
                            wf_id = run_item.get("id")
                            try:
                                wf_resp = vra_client.request("GET", f"/vro/workflows/{wf_id}")
                                if wf_resp.status_code < 400:
                                    run_item["endpointLink"] = wf_resp.json().get("integration", {}).get("endpointConfigurationLink")
                            except Exception as we:
                                logger.warning(f"Failed to fetch endpointLink for workflow '{wf_id}': {we}")
                        else:
                            abx_name = run_item.get("name")
                            if abx_name in provisioned_abxs:
                                run_item["id"] = provisioned_abxs[abx_name]["id"]
                            run_item["projectId"] = proj_id
                        payload["runnableItem"] = run_item
                        
                        form_def = payload.get("formDefinition") or {}
                        form_def["id"] = None
                        form_def["tenant"] = None
                        form_def["externalSourceFormSchemas"] = None
                        payload["formDefinition"] = form_def
                        
                        logger.info(f"Saving Resource Action '{name}'...")
                        ra_resp = vra_client.request(
                            "POST",
                            "/form-service/api/custom/resource-actions",
                            params={"generateUnvalidatableExternalValuesSchema": "true"},
                            json=payload
                        )
                        if ra_resp.status_code >= 400:
                            logger.error(f"Failed to save Resource Action '{name}': {ra_resp.text}")
                    except Exception as e:
                        logger.error(f"Failed to provision Resource Action '{name}': {e}")

            # 2.4.5 Register Blueprint Catalog Source
            try:
                sources = vra_client.list_catalog_sources()
                bp_source = next((s for s in sources if s.get("typeId") == "com.vmw.blueprint" and s.get("config", {}).get("sourceProjectId") == target_project_id), None)
                
                bp_source_id = None
                if bp_source:
                    logger.info(f"Syncing existing Blueprint Catalog Source for project '{target_project_name}'...")
                    resp = vra_client.request("POST", "/catalog/api/admin/sources", json=bp_source)
                    bp_source_id = (resp.json() if resp.status_code < 400 and resp.text else {}).get("id") or bp_source.get("id")
                else:
                    logger.info(f"Creating Blueprint Catalog Source for project '{target_project_name}'...")
                    new_source = {
                        "name": target_project_name,
                        "typeId": "com.vmw.blueprint",
                        "config": {"sourceProjectId": target_project_id}
                    }
                    resp = vra_client.request("POST", "/catalog/api/admin/sources", json=new_source)
                    bp_source_id = (resp.json() if resp.status_code < 400 and resp.text else {}).get("id")
                
                if bp_source_id:
                    catalog_source_name_to_id[target_project_name] = bp_source_id
                    catalog_source_name_to_id["admin"] = bp_source_id
                    logger.info(f"Cached Blueprint Catalog Source ID: {bp_source_id}")
                    # Trigger manual sync immediately to force import of catalog items
                    try:
                        vra_client.request("POST", f"/catalog/api/admin/sources/{bp_source_id}/sync")
                        logger.info("Triggered manual sync for Blueprint Catalog Source.")
                    except Exception as se:
                        logger.warning(f"Failed to trigger sync for Blueprint Catalog Source: {se}")
            except Exception as e:
                logger.error(f"Failed to register blueprint catalog source: {e}")

            # 2.5 Provision Catalog Sources
            # Blueprint Catalog Source는 2.4.5 단계에서, Workflow Catalog Source는 2.8 단계에서 각각 전용 로직으로 처리하므로 2.5 단계에서는 중복 구성을 방지하기 위해 생략합니다.
            pass

            # 2.8 Provision Workflow Catalog Sources
            wf_src_root = os.path.join(vra_temp_dir, "workflow_sources")
            if os.path.exists(wf_src_root):
                for file in os.listdir(wf_src_root):
                    if not file.endswith(".json"):
                        continue
                    file_path = os.path.join(wf_src_root, file)
                    name = os.path.splitext(file)[0]
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            source_payload = json.load(f)
                            
                        config_wfs = source_payload.get("config", {}).get("workflows", [])
                        target_wfs = []
                        for back_wf in config_wfs:
                            wf_name = back_wf.get("name")
                            try:
                                wf_resp = vra_client.request("GET", "/vro/workflows", params={"$filter": f"name eq '{wf_name}'"})
                                if wf_resp.status_code < 400:
                                    content = wf_resp.json().get("content", [])
                                    if content:
                                        target_wf = content[0]
                                        target_wfs.append({
                                            "id": target_wf.get("id"),
                                            "name": target_wf.get("name"),
                                            "version": target_wf.get("version"),
                                            "integration": target_wf.get("integration")
                                        })
                                    else:
                                        logger.warning(f"Workflow '{wf_name}' not found on target vRO. Skipping source mapping.")
                            except Exception as we:
                                logger.error(f"Failed to query workflow '{wf_name}': {we}")
                                
                        server_sources = vra_client.list_catalog_sources()
                        existing_source = next((s for s in server_sources if s.get("typeId") == "com.vmw.vro.workflow" and s.get("name") == name), None)
                        
                        new_cs_id = None
                        if existing_source:
                            logger.info(f"Updating Workflow Catalog Source '{name}'...")
                            existing_source["config"] = existing_source.get("config", {})
                            existing_source["config"]["workflows"] = target_wfs
                            resp = vra_client.request("POST", "/catalog/api/admin/sources", json=existing_source)
                            new_cs_id = (resp.json() if resp.status_code < 400 and resp.text else {}).get("id") or existing_source.get("id")
                        else:
                            logger.info(f"Creating Workflow Catalog Source '{name}'...")
                            new_source = {
                                "config": {
                                    "workflows": target_wfs
                                },
                                "description": source_payload.get("description", "GVP VRO Content Source"),
                                "global": source_payload.get("global", True),
                                "name": name,
                                "typeId": "com.vmw.vro.workflow"
                            }
                            resp = vra_client.request("POST", "/catalog/api/admin/sources", json=new_source)
                            new_cs_id = (resp.json() if resp.status_code < 400 and resp.text else {}).get("id")
                            
                        if new_cs_id:
                            catalog_source_name_to_id[name] = new_cs_id
                            logger.info(f"Cached Workflow Catalog Source '{name}' ID: {new_cs_id}")
                            # Trigger manual sync immediately
                            try:
                                vra_client.request("POST", f"/catalog/api/admin/sources/{new_cs_id}/sync")
                                logger.info(f"Triggered manual sync for Workflow Catalog Source '{name}'.")
                            except Exception as se:
                                logger.warning(f"Failed to trigger sync for Workflow Catalog Source '{name}': {se}")
                    except Exception as e:
                        logger.error(f"Failed to provision Workflow Catalog Source '{name}': {e}")

            # Wait for Catalog Sources to synchronize in the background
            logger.info("Waiting for Catalog Sources to synchronize in the background (15s default + polling expected items)...")
            import time
            time.sleep(15)

            # Polling expected Blueprint Catalog Items to ensure Custom Forms don't fail to map
            expected_bp_items = manifest.get("components", {}).get("blueprints", [])
            if expected_bp_items:
                logger.info(f"Polling target server for expected Blueprint Catalog Items: {expected_bp_items}")
                start_time = time.time()
                timeout = 180  # Max 3 minutes
                sync_success = False
                while time.time() - start_time < timeout:
                    try:
                        catalog_items = vra_client.list_catalog_items()
                        items_on_server = {i["name"] for i in catalog_items}
                        missing_items = [name for name in expected_bp_items if name not in items_on_server]
                        if not missing_items:
                            logger.info("All expected Blueprint Catalog Items are now synchronized!")
                            sync_success = True
                            break
                        else:
                            logger.info(f"Still waiting for Blueprint items: {missing_items}. Retrying in 5 seconds...")
                    except Exception as se:
                        logger.debug(f"Error querying catalog items during sync wait: {se}")
                    time.sleep(5)
                if not sync_success:
                    logger.warning("Timeout reached waiting for Blueprint Catalog Items. Some custom forms might fail to map.")

            # 2.6 Provision Policies
            provision_flat_resources("policies", vra_client.list_policies, vra_client.create_policy, vra_client.update_policy, "Catalog Policy")

            # 2.6.5 Provision Naming Policies
            provision_flat_resources("naming_policies", vra_client.list_naming_policies, vra_client.create_naming_policy, vra_client.update_naming_policy, "Naming Policy")

            # 2.7 Provision Subscriptions
            sub_root = os.path.join(vra_temp_dir, "subscriptions")
            if os.path.exists(sub_root):
                for file in os.listdir(sub_root):
                    if not file.endswith(".json"):
                        continue
                    file_path = os.path.join(sub_root, file)
                    name = os.path.splitext(file)[0]
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                            
                        payload["orgId"] = None
                        payload["subscriberId"] = None
                        payload["description"] = f"GVP updated on {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}"
                        
                        server_subs = vra_client.list_subscriptions()
                        existing_sub = next((s for s in server_subs if s.get("name") == name), None)
                        
                        if existing_sub:
                            logger.info(f"Updating Event Broker Subscription '{name}'...")
                            for key in ["type", "disabled", "eventTopicId", "blocking", "contextual", "criteria", "runnableType", "runnableId", "timeout", "priority", "recoverRunnableType", "recoverRunnableId", "constraints"]:
                                if key in payload:
                                    existing_sub[key] = payload[key]
                            existing_sub["disabled"] = False
                            vra_client.update_subscription(existing_sub["id"], existing_sub)
                        else:
                            logger.info(f"Creating Event Broker Subscription '{name}'...")
                            payload["id"] = str(uuid.uuid4())
                            vra_client.create_subscription(payload)
                    except Exception as e:
                        logger.error(f"Failed to provision Event Broker Subscription '{name}': {e}")

            # 2.9 Provision Custom Forms
            form_folder = os.path.join(vra_temp_dir, "custom_forms")
            if os.path.exists(form_folder):
                try:
                    catalog_items = vra_client.list_catalog_items()
                    items_by_name = {i["name"]: i for i in catalog_items}
                except Exception as e:
                    logger.error(f"Failed to fetch catalog items for form mapping: {e}")
                    items_by_name = {}

                for file in os.listdir(form_folder):
                    if not file.endswith(".json"):
                        continue
                    file_path = os.path.join(form_folder, file)
                    name = os.path.splitext(file)[0]
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                            
                        # Custom forms reference catalog items. Map the sourceId/type to the target item on Prod
                        if name in items_by_name:
                            target_item = items_by_name[name]
                            payload["sourceId"] = target_item["id"]
                            payload["sourceType"] = target_item.get("type", {}).get("id")
                            
                            if "form" in payload and not isinstance(payload["form"], str):
                                payload["form"] = json.dumps(payload["form"])
                            
                            logger.info(f"Saving Custom Form for '{name}'...")
                            vra_client.request(
                                "POST",
                                "/form-service/api/forms",
                                params={"generateUnvalidatableExternalValuesSchema": "true"},
                                json=payload
                            )
                        else:
                            logger.warning(f"Catalog item '{name}' not found on target server. Custom form cannot be mapped.")
                    except Exception as e:
                        logger.error(f"Failed to provision Custom Form for '{name}': {e}")

            # 2.10 Provision Workflow Custom Forms
            wf_form_root = os.path.join(vra_temp_dir, "workflow_forms")
            if os.path.exists(wf_form_root):
                try:
                    catalog_items = vra_client.list_catalog_items()
                    items_by_name = {i["name"]: i for i in catalog_items}
                except Exception as e:
                    logger.error(f"Failed to fetch catalog items for workflow form mapping: {e}")
                    items_by_name = {}
                    
                for file in os.listdir(wf_form_root):
                    if not file.endswith(".json"):
                        continue
                    file_path = os.path.join(wf_form_root, file)
                    name = os.path.splitext(file)[0]
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            payload = json.load(f)
                            
                        if name in items_by_name:
                            target_item = items_by_name[name]
                            logger.info(f"Saving Workflow Custom Form for '{name}'...")
                            form_payload = {
                                "name": name,
                                "type": "requestForm",
                                "sourceId": target_item["id"],
                                "sourceType": payload.get("sourceType", "com.vmw.vro.workflow"),
                                "status": "ON",
                                "form": json.dumps(payload.get("form")) if isinstance(payload.get("form"), (dict, list)) else payload.get("form")
                            }
                            vra_client.request(
                                "POST", 
                                "/form-service/api/forms", 
                                params={"generateUnvalidatableExternalValuesSchema": "true"}, 
                                json=form_payload
                            )
                        else:
                            logger.warning(f"Catalog item '{name}' not found on target server. Workflow custom form cannot be mapped.")
                    except Exception as e:
                        logger.error(f"Failed to provision Workflow Custom Form for '{name}': {e}")

        finally:
            shutil.rmtree(vra_temp_dir)

    logger.info(f"=== Day-1 Restore completed for version: {version} ===")

def main():
    parser = argparse.ArgumentParser(description="VCF Automation & Orchestrator Day-1 Provisioning Tool")
    parser.add_argument("action", choices=["backup", "restore"], help="Lifecycle action to perform")
    parser.add_argument("--version", required=True, help="Release version to backup/restore")
    parser.add_argument("--artifacts-dir", default=None, help="Directory to read/write release artifacts")
    
    args = parser.parse_args()
    
    config = load_config()
    
    # Setup default artifacts directory: gitops/artifacts or packages directory
    if not args.artifacts_dir:
        # Default to /Users/ujmoon/Documents/Github/poscodx/gitops/artifacts
        args.artifacts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "artifacts")
        
    os.makedirs(args.artifacts_dir, exist_ok=True)
    
    # Initialize Clients
    vro_client = VroClient(
        vcf_url=config["vcf_url"],
        refresh_token=config["refresh_token"],
        org=config.get("org", "default"),
        verify_ssl=config.get("verify_ssl", False)
    )
    vra_client = VraClient(
        vcf_url=config["vcf_url"],
        refresh_token=config["refresh_token"],
        org=config.get("org", "default"),
        verify_ssl=config.get("verify_ssl", False)
    )

    if args.action == "backup":
        backup(vra_client, vro_client, config, args.version, args.artifacts_dir)
    elif args.action == "restore":
        restore(vra_client, vro_client, config, args.version, args.artifacts_dir)

if __name__ == "__main__":
    main()
