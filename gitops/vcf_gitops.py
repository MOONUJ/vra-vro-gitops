# -*- coding: utf-8 -*-
import os
import sys
import json
import argparse
import logging
from vro_client import VroClient

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("vcf_gitops")

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

def get_workflow_dirs(root_dir):
    """
    Scans the local directory for workflows.
    A workflow directory contains both workflow.json and content.json.
    """
    workflow_dirs = []
    # Search in both vro/workflows and vro/Workflows case-insensitively
    vro_root = os.path.join(root_dir, "vro")
    if not os.path.exists(vro_root):
        return workflow_dirs
        
    for parent, dirs, files in os.walk(vro_root):
        if "workflow.json" in files and "content.json" in files:
            workflow_dirs.append(parent)
            
    return workflow_dirs

def get_action_dirs(root_dir):
    """
    Scans the local directory for actions.
    An action directory contains both action.json and script.js.
    """
    action_dirs = []
    vro_root = os.path.join(root_dir, "vro")
    if not os.path.exists(vro_root):
        return action_dirs
        
    for parent, dirs, files in os.walk(vro_root):
        if "action.json" in files and "script.js" in files:
            action_dirs.append(parent)
            
    return action_dirs

def extract_workflow_items(workflow_dir, content_json):
    """
    Parses content.json and extracts script tasks/bindings into workflow-items/
    """
    items = content_json.get("workflow-item", [])
    extracted_count = 0
    
    for item in items:
        name = item.get("name")
        if not name:
            continue
            
        script = item.get("script", {})
        script_val = script.get("value") if isinstance(script, dict) else None
        
        in_binding = item.get("in-binding", {})
        in_bind_list = in_binding.get("bind", []) if isinstance(in_binding, dict) else []
        
        out_binding = item.get("out-binding", {})
        out_bind_list = out_binding.get("bind", []) if isinstance(out_binding, dict) else []
        
        # Only extract if it has a script, or non-empty bindings
        if script_val or in_bind_list or out_bind_list:
            item_dir = os.path.join(workflow_dir, "workflow-items", name)
            os.makedirs(item_dir, exist_ok=True)
            
            # 1. Save script code
            if script_val:
                script_path = os.path.join(item_dir, "value.js")
                # Normalize line endings to LF
                normalized_script = script_val.replace('\r\n', '\n')
                with open(script_path, "w", encoding="utf-8") as sf:
                    sf.write(normalized_script)
                    
            # 2. Save in-binding if not empty
            if in_bind_list:
                in_path = os.path.join(item_dir, "in-binding.json")
                with open(in_path, "w", encoding="utf-8") as ibf:
                    json.dump(in_binding, ibf, indent=4, ensure_ascii=False)
                    
            # 3. Save out-binding if not empty
            if out_bind_list:
                out_path = os.path.join(item_dir, "out-binding.json")
                with open(out_path, "w", encoding="utf-8") as obf:
                    json.dump(out_binding, obf, indent=4, ensure_ascii=False)
                    
            extracted_count += 1
            
    if extracted_count > 0:
        logger.info(f"Extracted {extracted_count} items into workflow-items/ for {os.path.basename(workflow_dir)}")

def assemble_workflow_content(workflow_dir):
    """
    Loads content.json and merges it with individual script files/bindings from workflow-items/ in-memory.
    Returns the assembled JSON content dict.
    """
    content_path = os.path.join(workflow_dir, "content.json")
    with open(content_path, "r", encoding="utf-8") as f:
        content_json = json.load(f)
        
    items_dir = os.path.join(workflow_dir, "workflow-items")
    if not os.path.exists(items_dir):
        return content_json
        
    items = content_json.get("workflow-item", [])
    
    # Iterate over items and check if a corresponding folder exists in workflow-items/
    for item in items:
        name = item.get("name")
        if not name:
            continue
            
        item_folder = os.path.join(items_dir, name)
        if not os.path.exists(item_folder):
            continue
            
        # 1. Load script code if value.js exists
        script_path = os.path.join(item_folder, "value.js")
        if os.path.exists(script_path):
            with open(script_path, "r", encoding="utf-8") as sf:
                code = sf.read()
                # vRO content needs script as a dictionary object
                if "script" not in item or not isinstance(item["script"], dict):
                    item["script"] = {}
                item["script"]["value"] = code
                item["script"]["encoded"] = False
                
        # 2. Load in-binding if exists
        in_path = os.path.join(item_folder, "in-binding.json")
        if os.path.exists(in_path):
            with open(in_path, "r", encoding="utf-8") as ibf:
                item["in-binding"] = json.load(ibf)
                
        # 3. Load out-binding if exists
        out_path = os.path.join(item_folder, "out-binding.json")
        if os.path.exists(out_path):
            with open(out_path, "r", encoding="utf-8") as obf:
                item["out-binding"] = json.load(obf)
                
    return content_json

def get_target_workflow_path(root_dir, category_path, workflow_name):
    """
    Determines the local directory path for a workflow, respecting existing casing (Workflows vs workflows).
    """
    # Check if capital W path exists
    cap_path = os.path.join(root_dir, "vro", "Workflows", category_path, workflow_name)
    if os.path.exists(cap_path):
        return cap_path
        
    # Check if lowercase w path exists
    lower_path = os.path.join(root_dir, "vro", "workflows", category_path, workflow_name)
    if os.path.exists(lower_path):
        return lower_path
        
    # Fallback to lowercase w path
    return lower_path

def pull_all(client, config, root_dir):
    """
    Sync from vRO server to local repository.
    """
    tag = config.get("gitops_tag")
    if not tag:
        logger.error("No 'gitops_tag' configured in config.json. Cannot execute pull-all.")
        sys.exit(1)
        
    logger.info(f"--- Starting Pull-All Sync for tag '{tag}' ---")
    
    # 1. Discover workflows matching the tag
    try:
        discovered_workflows = client.find_resources_by_tag("Workflow", tag)
    except Exception as e:
        logger.error(f"Failed to discover workflows by tag: {e}")
        discovered_workflows = []
        
    logger.info(f"Discovered {len(discovered_workflows)} workflows with tag '{tag}' on the server.")
    
    # 2. Discover actions matching the tag
    try:
        discovered_actions = client.find_resources_by_tag("Action", tag)
    except Exception as e:
        logger.error(f"Failed to discover actions by tag: {e}")
        discovered_actions = []

    logger.info(f"Discovered {len(discovered_actions)} actions matching tag '{tag}' on the server.")

    # 3. Discover configurations matching the tag
    try:
        discovered_configs = client.find_resources_by_tag("ConfigurationElement", tag)
    except Exception as e:
        logger.error(f"Failed to discover configurations by tag: {e}")
        discovered_configs = []

    logger.info(f"Discovered {len(discovered_configs)} configurations matching tag '{tag}' on the server.")

    # 4. Discover resources matching the tag
    try:
        discovered_resources = client.find_resources_by_tag("ResourceElement", tag)
    except Exception as e:
        logger.error(f"Failed to discover resources by tag: {e}")
        discovered_resources = []

    logger.info(f"Discovered {len(discovered_resources)} resources matching tag '{tag}' on the server.")

    # 5. Create or update the package on the server with all discovered elements, and export it
    pkg_config = config.get("package", {})
    pkg_name = pkg_config.get("name")
    pkg_local_path = pkg_config.get("local_path")
    if pkg_name and pkg_local_path:
        pkg_full_path = os.path.join(root_dir, pkg_local_path)
        try:
            workflow_ids = [wf["id"] for wf in discovered_workflows]
            action_ids = [act["id"] for act in discovered_actions]
            config_ids = [cfg["id"] for cfg in discovered_configs]
            resource_ids = [res["id"] for res in discovered_resources]
            
            logger.info(f"Ensuring package '{pkg_name}' contains all elements on the server...")
            client.create_or_update_package(
                package_name=pkg_name,
                workflow_ids=workflow_ids,
                action_ids=action_ids,
                config_ids=config_ids,
                resource_ids=resource_ids
            )
            
            # Export the package binary
            client.export_package(pkg_name, pkg_full_path)
        except Exception as e:
            logger.error(f"Failed to ensure/export package {pkg_name}: {e}")
            # Continue syncing individual components even if package export fails

    # 6. Pull individual workflows
    for wf in discovered_workflows:
        wf_id = wf["id"]
        wf_name = wf["name"]
        logger.info(f"Syncing workflow: {wf_name} (ID: {wf_id})...")
        
        try:
            # Fetch full metadata and content
            wf_meta = client.get_workflow(wf_id)
            wf_content = client.get_workflow_content(wf_id)
            
            # Find category path
            category_id = wf_meta.get("category-id")
            category_path = ""
            if category_id:
                # Query category to find path
                cat_resp = client.request("GET", f"/categories/{category_id}")
                if cat_resp.status_code == 200:
                    category_path = cat_resp.json().get("path", "")
                    
            if not category_path:
                logger.warning(f"Could not resolve category path for workflow {wf_name}. Defaulting to root.")
                category_path = "Default"
                
            # Determine target local directory
            local_dir = get_target_workflow_path(root_dir, category_path, wf_name)
            os.makedirs(local_dir, exist_ok=True)
            
            # Save files
            with open(os.path.join(local_dir, "workflow.json"), "w", encoding="utf-8") as mf:
                json.dump(wf_meta, mf, indent=4, ensure_ascii=False)
                
            with open(os.path.join(local_dir, "content.json"), "w", encoding="utf-8") as cf:
                json.dump(wf_content, cf, indent=4, ensure_ascii=False)
                
            # Extract workflow-items
            extract_workflow_items(local_dir, wf_content)
            
            logger.info(f"Successfully pulled workflow {wf_name} to {local_dir}")
        except Exception as e:
            logger.error(f"Failed to pull workflow {wf_name} (ID: {wf_id}): {e}")

    # 7. Pull individual actions
    for act in discovered_actions:
        act_id = act["id"]
        act_name = act["name"]
        logger.info(f"Syncing action: {act_name} (ID: {act_id})...")

        try:
            act_meta = client.get_action(act_id)
            module = act_meta.get("module")
            if not module:
                logger.warning(f"No module found for action {act_name}. Defaulting to 'Default'")
                module = "Default"

            # Target folder path: vro/actions/{module}/{name}/
            local_dir = os.path.join(root_dir, "vro", "actions", module, act_name)
            os.makedirs(local_dir, exist_ok=True)

            # Extract script code
            script_code = act_meta.get("script", "")
            normalized_script = script_code.replace('\r\n', '\n')
            with open(os.path.join(local_dir, "script.js"), "w", encoding="utf-8") as sf:
                sf.write(normalized_script)

            # Save metadata (clear script value inside action.json for cleanliness)
            act_meta_clean = dict(act_meta)
            act_meta_clean["script"] = ""
            with open(os.path.join(local_dir, "action.json"), "w", encoding="utf-8") as mf:
                json.dump(act_meta_clean, mf, indent=4, ensure_ascii=False)

            logger.info(f"Successfully pulled action {act_name} to {local_dir}")
        except Exception as e:
            logger.error(f"Failed to pull action {act_name} (ID: {act_id}): {e}")

    # 8. Pull individual configurations
    for cfg in discovered_configs:
        cfg_id = cfg["id"]
        cfg_name = cfg["name"]
        logger.info(f"Syncing configuration: {cfg_name} (ID: {cfg_id})...")

        try:
            cfg_meta = client.get_configuration(cfg_id)
            if not cfg_meta:
                continue

            # Resolve category path
            category_id = cfg_meta.get("category-id")
            category_path = ""
            if category_id:
                cat_resp = client.request("GET", f"/categories/{category_id}")
                if cat_resp.status_code == 200:
                    category_path = cat_resp.json().get("path", "")
            if not category_path:
                category_path = "Default"

            # Save format: vro/configurations/{category_path}/{config_name}.json
            local_dir = os.path.join(root_dir, "vro", "configurations", category_path)
            os.makedirs(local_dir, exist_ok=True)

            # Clean up transient fields
            cfg_clean = {
                "id": cfg_meta.get("id"),
                "name": cfg_meta.get("name"),
                "version": cfg_meta.get("version", "0.0.0"),
                "attributes": cfg_meta.get("attributes", [])
            }

            with open(os.path.join(local_dir, f"{cfg_name}.json"), "w", encoding="utf-8") as f:
                json.dump(cfg_clean, f, indent=4, ensure_ascii=False)

            logger.info(f"Successfully pulled configuration {cfg_name} to {local_dir}")
        except Exception as e:
            logger.error(f"Failed to pull configuration {cfg_name} (ID: {cfg_id}): {e}")

    # 9. Pull individual resources
    for res in discovered_resources:
        res_id = res["id"]
        res_name = res["name"]
        logger.info(f"Syncing resource: {res_name} (ID: {res_id})...")

        try:
            res_meta = client.get_resource(res_id)
            if not res_meta:
                continue

            # Resolve category path
            category_id = res_meta.get("category-id")
            category_path = ""
            if category_id:
                cat_resp = client.request("GET", f"/categories/{category_id}")
                if cat_resp.status_code == 200:
                    category_path = cat_resp.json().get("path", "")
            if not category_path:
                category_path = "Default"

            # Target dir: vro/resources/{category_path}/{resource_name}/
            local_dir = os.path.join(root_dir, "vro", "resources", category_path, res_name)
            os.makedirs(local_dir, exist_ok=True)

            # Save metadata
            mime_type = res_meta.get("mime-type", "application/octet-stream")
            res_clean = {
                "id": res_meta.get("id"),
                "name": res_meta.get("name"),
                "version": res_meta.get("version", "0.0.0"),
                "mime-type": mime_type,
                "description": res_meta.get("description", "")
            }

            with open(os.path.join(local_dir, "resource.json"), "w", encoding="utf-8") as f:
                json.dump(res_clean, f, indent=4, ensure_ascii=False)

            # Save content
            content = client.get_resource_content(res_id, mime_type)
            with open(os.path.join(local_dir, res_name), "wb") as f:
                f.write(content)

            logger.info(f"Successfully pulled resource {res_name} to {local_dir}")
        except Exception as e:
            logger.error(f"Failed to pull resource {res_name} (ID: {res_id}): {e}")

def get_local_configurations(root_dir):
    config_files = []
    configs_root = os.path.join(root_dir, "vro", "configurations")
    if not os.path.exists(configs_root):
        return config_files
        
    for parent, dirs, files in os.walk(configs_root):
        for file in files:
            if file.endswith(".json"):
                config_files.append(os.path.join(parent, file))
    return config_files

def get_local_resources(root_dir):
    resource_dirs = []
    resources_root = os.path.join(root_dir, "vro", "resources")
    if not os.path.exists(resources_root):
        return resource_dirs
        
    for parent, dirs, files in os.walk(resources_root):
        if "resource.json" in files:
            resource_dirs.append(parent)
    return resource_dirs

def push_all(client, config, root_dir, dry_run=False, force_bootstrap=False):
    """
    Sync from local repository to vRO server.
    """
    logger.info(f"--- Starting Push-All Sync (Dry-Run: {dry_run}, Force-Bootstrap: {force_bootstrap}) ---")
    
    # 1. Scan local directories for workflows
    local_dirs = get_workflow_dirs(root_dir)
    logger.info(f"Discovered {len(local_dirs)} local workflows in repository.")
    
    workflows_to_push = []
    need_bootstrap = force_bootstrap
    
    for wf_dir in local_dirs:
        # Load local files
        try:
            with open(os.path.join(wf_dir, "workflow.json"), "r", encoding="utf-8") as f:
                wf_meta = json.load(f)
            wf_id = wf_meta.get("id")
            wf_name = wf_meta.get("workflowName", wf_meta.get("name"))
            
            if not wf_id:
                logger.error(f"No ID found in workflow.json for path {wf_dir}. Skipping.")
                continue
                
            assembled_content = assemble_workflow_content(wf_dir)
            workflows_to_push.append({
                "id": wf_id,
                "name": wf_name,
                "meta": wf_meta,
                "content": assembled_content,
                "dir": wf_dir
            })
        except Exception as e:
            logger.error(f"Failed to load/assemble workflow at {wf_dir}: {e}")
            continue

    # 2. Scan local directories for actions
    local_action_dirs = get_action_dirs(root_dir)
    logger.info(f"Discovered {len(local_action_dirs)} local actions in repository.")

    actions_to_push = []
    for act_dir in local_action_dirs:
        try:
            with open(os.path.join(act_dir, "action.json"), "r", encoding="utf-8") as f:
                act_json = json.load(f)
            with open(os.path.join(act_dir, "script.js"), "r", encoding="utf-8") as f:
                script_code = f.read()

            act_id = act_json.get("id")
            act_name = act_json.get("name")
            if not act_id:
                logger.error(f"No ID found in action.json for path {act_dir}. Skipping.")
                continue

            act_json["script"] = script_code
            actions_to_push.append({
                "id": act_id,
                "name": act_name,
                "json": act_json,
                "dir": act_dir
            })
        except Exception as e:
            logger.error(f"Failed to load action at {act_dir}: {e}")
            continue

    # 3. Scan local directories for configurations
    local_cfg_files = get_local_configurations(root_dir)
    logger.info(f"Discovered {len(local_cfg_files)} local configurations in repository.")

    configs_to_push = []
    for cfg_file in local_cfg_files:
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg_json = json.load(f)
            cfg_id = cfg_json.get("id")
            cfg_name = cfg_json.get("name")
            if not cfg_id or not cfg_name:
                logger.error(f"Invalid configuration file {cfg_file}. Skipping.")
                continue

            rel_path = os.path.relpath(os.path.dirname(cfg_file), os.path.join(root_dir, "vro", "configurations"))
            configs_to_push.append({
                "id": cfg_id,
                "name": cfg_name,
                "json": cfg_json,
                "category_path": rel_path,
                "file": cfg_file
            })
        except Exception as e:
            logger.error(f"Failed to load configuration at {cfg_file}: {e}")
            continue

    # 4. Scan local directories for resources
    local_res_dirs = get_local_resources(root_dir)
    logger.info(f"Discovered {len(local_res_dirs)} local resources in repository.")

    resources_to_push = []
    for res_dir in local_res_dirs:
        try:
            with open(os.path.join(res_dir, "resource.json"), "r", encoding="utf-8") as f:
                res_meta = json.load(f)
            res_id = res_meta.get("id")
            res_name = res_meta.get("name")
            if not res_id or not res_name:
                logger.error(f"Invalid resource metadata in {res_dir}. Skipping.")
                continue

            content_file = os.path.join(res_dir, res_name)
            if not os.path.exists(content_file):
                logger.error(f"Resource content file not found at {content_file}. Skipping.")
                continue

            rel_path = os.path.relpath(os.path.dirname(res_dir), os.path.join(root_dir, "vro", "resources"))
            resources_to_push.append({
                "id": res_id,
                "name": res_name,
                "meta": res_meta,
                "content_file": content_file,
                "category_path": rel_path,
                "dir": res_dir
            })
        except Exception as e:
            logger.error(f"Failed to load resource at {res_dir}: {e}")
            continue

    if dry_run:
        logger.info("[DRY RUN] Verification completed. The following workflows would be synced:")
        for wf in workflows_to_push:
            logger.info(f"  - Workflow: {wf['name']} (ID: {wf['id']}) at {wf['dir']}")
        logger.info("[DRY RUN] The following actions would be synced:")
        for act in actions_to_push:
            logger.info(f"  - Action: {act['name']} (ID: {act['id']}) at {act['dir']}")
        logger.info("[DRY RUN] The following configurations would be synced:")
        for cfg in configs_to_push:
            logger.info(f"  - Configuration: {cfg['name']} (ID: {cfg['id']}) at {cfg['file']}")
        logger.info("[DRY RUN] The following resources would be synced:")
        for res in resources_to_push:
            logger.info(f"  - Resource: {res['name']} (ID: {res['id']}) at {res['dir']}")
        return

    # Check if any workflows/actions/configurations/resources do not exist on the server. If so, trigger bootstrap!
    if not need_bootstrap:
        for wf in workflows_to_push:
            try:
                server_wf = client.get_workflow(wf["id"])
                if not server_wf:
                    logger.info(f"Workflow {wf['name']} (ID: {wf['id']}) is missing on the server. Bootstrapping required.")
                    need_bootstrap = True
                    break
            except Exception as e:
                logger.warning(f"Error checking workflow {wf['name']} on server: {e}. Assuming it might be missing.")
                need_bootstrap = True
                break

        if not need_bootstrap:
            for act in actions_to_push:
                try:
                    server_act = client.get_action(act["id"])
                    if not server_act:
                        logger.info(f"Action {act['name']} (ID: {act['id']}) is missing on the server. Bootstrapping required.")
                        need_bootstrap = True
                        break
                except Exception as e:
                    logger.warning(f"Error checking action {act['name']} on server: {e}. Assuming it might be missing.")
                    need_bootstrap = True
                    break

        if not need_bootstrap:
            for cfg in configs_to_push:
                try:
                    server_cfg = client.get_configuration(cfg["id"])
                    if not server_cfg:
                        logger.info(f"Configuration {cfg['name']} (ID: {cfg['id']}) is missing on the server. Bootstrapping required.")
                        need_bootstrap = True
                        break
                except Exception as e:
                    logger.warning(f"Error checking configuration {cfg['name']} on server: {e}. Assuming missing.")
                    need_bootstrap = True
                    break

        if not need_bootstrap:
            for res in resources_to_push:
                try:
                    server_res = client.get_resource(res["id"])
                    if not server_res:
                        logger.info(f"Resource {res['name']} (ID: {res['id']}) is missing on the server. Bootstrapping required.")
                        need_bootstrap = True
                        break
                except Exception as e:
                    logger.warning(f"Error checking resource {res['name']} on server: {e}. Assuming missing.")
                    need_bootstrap = True
                    break

    # 1. Bootstrap Phase: Import package if needed
    if need_bootstrap:
        pkg_config = config.get("package", {})
        pkg_local_path = pkg_config.get("local_path")
        if pkg_local_path:
            pkg_full_path = os.path.join(root_dir, pkg_local_path)
            if os.path.exists(pkg_full_path):
                logger.info(f"Triggering bootstrap by importing package file: {pkg_local_path}")
                try:
                    client.import_package(pkg_full_path, overwrite=True)
                except Exception as e:
                    logger.error(f"Package import bootstrap failed: {e}. Proceeding with individual fallback creations.")
            else:
                logger.warning(f"Bootstrap requested/needed, but package file not found at: {pkg_full_path}")
        else:
            logger.info("No package file configured for bootstrapping. Individual fallback creation will be used.")

    # 2. Sync Phase: Update each workflow content
    for wf in workflows_to_push:
        wf_id = wf["id"]
        wf_name = wf["name"]
        wf_content = wf["content"]
        wf_meta = wf["meta"]
        
        try:
            logger.info(f"Pushing workflow: {wf_name} (ID: {wf_id})...")
            
            # Double check existence, if still missing (e.g. no package or package didn't contain it), create skeleton
            server_wf = client.get_workflow(wf_id)
            if not server_wf:
                logger.info(f"Workflow {wf_name} still missing on server. Creating skeleton folder hierarchy...")
                category_path = wf_meta.get("folder", "")
                if not category_path:
                    category_path = "GVP" # Default fallback
                    
                category_id = client.ensure_category_path(category_path, "WorkflowCategory")
                client.create_workflow_skeleton(wf_name, category_id, wf_id)
                
            # Update content
            client.update_workflow_content(wf_id, wf_content)
            logger.info(f"Successfully pushed {wf_name} to server.")
        except Exception as e:
            logger.error(f"Failed to push workflow {wf_name} (ID: {wf_id}): {e}")

    # 3. Sync Phase: Update each action content
    for act in actions_to_push:
        act_id = act["id"]
        act_name = act["name"]
        act_json = act["json"]

        try:
            logger.info(f"Pushing action: {act_name} (ID: {act_id})...")
            
            # Double check existence, if missing, create it
            server_act = client.get_action(act_id)
            if server_act:
                client.update_action(act_id, act_json)
            else:
                client.create_action(act_json)
            logger.info(f"Successfully pushed action {act_name} to server.")
        except Exception as e:
            logger.error(f"Failed to push action {act_name} (ID: {act_id}): {e}")

    # 4. Sync Phase: Update each configuration
    for cfg in configs_to_push:
        cfg_id = cfg["id"]
        cfg_name = cfg["name"]
        cfg_json = cfg["json"]
        cat_path = cfg["category_path"]

        try:
            logger.info(f"Pushing configuration: {cfg_name} (ID: {cfg_id})...")
            server_cfg = client.get_configuration(cfg_id)
            if not server_cfg:
                logger.info(f"Configuration {cfg_name} still missing on server. Creating configuration element...")
                category_id = client.ensure_category_path(cat_path, "ConfigurationElementCategory")
                create_payload = {
                    "id": cfg_id,
                    "name": cfg_name,
                    "version": cfg_json.get("version", "0.0.0"),
                    "attributes": cfg_json.get("attributes", [])
                }
                client.create_configuration(category_id, create_payload)
            else:
                # Update attributes in place
                update_payload = dict(server_cfg)
                update_payload["attributes"] = cfg_json.get("attributes", [])
                update_payload["version"] = cfg_json.get("version", "0.0.0")
                client.update_configuration(cfg_id, update_payload)
            logger.info(f"Successfully pushed configuration {cfg_name} to server.")
        except Exception as e:
            logger.error(f"Failed to push configuration {cfg_name} (ID: {cfg_id}): {e}")

    # 5. Sync Phase: Update each resource
    for res in resources_to_push:
        res_id = res["id"]
        res_name = res["name"]
        res_meta = res["meta"]
        content_file = res["content_file"]
        cat_path = res["category_path"]

        try:
            logger.info(f"Pushing resource: {res_name} (ID: {res_id})...")
            server_res = client.get_resource(res_id)
            if not server_res:
                logger.info(f"Resource {res_name} still missing on server. Creating resource element...")
                category_id = client.ensure_category_path(cat_path, "ResourceElementCategory")
                client.create_resource(category_id, content_file, filename=res_name)

            # Retrieve again to make sure we have server side ID/meta and can push update
            server_res = client.get_resource(res_id)
            if server_res:
                client.update_resource_content(res_id, content_file, filename=res_name)
                
                update_payload = dict(server_res)
                update_payload["description"] = res_meta.get("description", "")
                update_payload["version"] = res_meta.get("version", "0.0.0")
                client.update_resource_metadata(res_id, update_payload)
                logger.info(f"Successfully pushed resource {res_name} to server.")
            else:
                logger.error(f"Resource {res_name} (ID: {res_id}) does not exist on server and could not be bootstrapped with the correct ID.")
        except Exception as e:
            logger.error(f"Failed to push resource {res_name} (ID: {res_id}): {e}")

def status(client, config, root_dir):
    """
    Compares the state of workflows, actions, configurations, and resources
    between the local Git repository and the remote vRO orchestrator.
    """
    tag = config.get("gitops_tag")
    if not tag:
        logger.error("No 'gitops_tag' configured in config.json. Cannot execute status.")
        sys.exit(1)

    logger.info(f"--- Running GitOps Status Check for tag '{tag}' ---")

    # 1. Discover server resources by tag
    try:
        server_workflows = client.find_resources_by_tag("Workflow", tag)
    except Exception as e:
        logger.error(f"Failed to fetch workflows from server: {e}")
        server_workflows = []

    try:
        server_actions = client.find_resources_by_tag("Action", tag)
    except Exception as e:
        logger.error(f"Failed to fetch actions from server: {e}")
        server_actions = []

    try:
        server_configs = client.find_resources_by_tag("ConfigurationElement", tag)
    except Exception as e:
        logger.error(f"Failed to fetch configurations from server: {e}")
        server_configs = []

    try:
        server_resources = client.find_resources_by_tag("ResourceElement", tag)
    except Exception as e:
        logger.error(f"Failed to fetch resources from server: {e}")
        server_resources = []

    # Map server assets by ID
    server_wf_map = {wf["id"]: wf for wf in server_workflows}
    server_act_map = {act["id"]: act for act in server_actions}
    server_cfg_map = {cfg["id"]: cfg for cfg in server_configs}
    server_res_map = {res["id"]: res for res in server_resources}

    # 2. Discover local resources
    # Workflows
    local_wf_dirs = get_workflow_dirs(root_dir)
    local_wf_map = {}
    for wf_dir in local_wf_dirs:
        try:
            with open(os.path.join(wf_dir, "workflow.json"), "r", encoding="utf-8") as f:
                wf_meta = json.load(f)
            wf_id = wf_meta.get("id")
            if wf_id:
                local_wf_map[wf_id] = {
                    "name": wf_meta.get("workflowName", wf_meta.get("name")),
                    "version": wf_meta.get("version", "0.0.0"),
                    "meta": wf_meta,
                    "dir": wf_dir
                }
        except Exception:
            pass

    # Actions
    local_act_dirs = get_action_dirs(root_dir)
    local_act_map = {}
    for act_dir in local_act_dirs:
        try:
            with open(os.path.join(act_dir, "action.json"), "r", encoding="utf-8") as f:
                act_meta = json.load(f)
            act_id = act_meta.get("id")
            if act_id:
                local_act_map[act_id] = {
                    "name": act_meta.get("name"),
                    "version": act_meta.get("version", "0.0.0"),
                    "meta": act_meta,
                    "dir": act_dir
                }
        except Exception:
            pass

    # Configurations
    local_cfg_files = get_local_configurations(root_dir)
    local_cfg_map = {}
    for cfg_file in local_cfg_files:
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg_json = json.load(f)
            cfg_id = cfg_json.get("id")
            if cfg_id:
                local_cfg_map[cfg_id] = {
                    "name": cfg_json.get("name"),
                    "version": cfg_json.get("version", "0.0.0"),
                    "json": cfg_json,
                    "file": cfg_file
                }
        except Exception:
            pass

    # Resources
    local_res_dirs = get_local_resources(root_dir)
    local_res_map = {}
    for res_dir in local_res_dirs:
        try:
            with open(os.path.join(res_dir, "resource.json"), "r", encoding="utf-8") as f:
                res_meta = json.load(f)
            res_id = res_meta.get("id")
            if res_id:
                local_res_map[res_id] = {
                    "name": res_meta.get("name"),
                    "version": res_meta.get("version", "0.0.0"),
                    "meta": res_meta,
                    "dir": res_dir
                }
        except Exception:
            pass

    # 3. Compare and categorize
    results = {
        "Workflow": {"IN_SYNC": [], "MODIFIED": [], "LOCAL_ONLY": [], "SERVER_ONLY": []},
        "Action": {"IN_SYNC": [], "MODIFIED": [], "LOCAL_ONLY": [], "SERVER_ONLY": []},
        "ConfigurationElement": {"IN_SYNC": [], "MODIFIED": [], "LOCAL_ONLY": [], "SERVER_ONLY": []},
        "ResourceElement": {"IN_SYNC": [], "MODIFIED": [], "LOCAL_ONLY": [], "SERVER_ONLY": []}
    }

    # Workflow comparison
    all_wf_ids = set(server_wf_map.keys()) | set(local_wf_map.keys())
    for wf_id in all_wf_ids:
        if wf_id not in local_wf_map:
            results["Workflow"]["SERVER_ONLY"].append((wf_id, server_wf_map[wf_id]["name"]))
        elif wf_id not in server_wf_map:
            results["Workflow"]["LOCAL_ONLY"].append((wf_id, local_wf_map[wf_id]["name"]))
        else:
            srv_ver = server_wf_map[wf_id].get("version", "0.0.0")
            loc_ver = local_wf_map[wf_id]["version"]
            modified = (srv_ver != loc_ver)
            
            if not modified:
                try:
                    server_content = client.get_workflow_content(wf_id)
                    local_content = assemble_workflow_content(local_wf_map[wf_id]["dir"])
                    
                    srv_items = {item.get("name"): item.get("script", {}).get("value", "") for item in server_content.get("workflow-item", []) if item.get("name")}
                    loc_items = {item.get("name"): item.get("script", {}).get("value", "") for item in local_content.get("workflow-item", []) if item.get("name")}
                    
                    for name, srv_val in srv_items.items():
                        loc_val = loc_items.get(name, "")
                        srv_clean = (srv_val or "").replace("\r\n", "\n").strip()
                        loc_clean = (loc_val or "").replace("\r\n", "\n").strip()
                        if srv_clean != loc_clean:
                            modified = True
                            break
                except Exception:
                    modified = True
            
            if modified:
                results["Workflow"]["MODIFIED"].append((wf_id, local_wf_map[wf_id]["name"]))
            else:
                results["Workflow"]["IN_SYNC"].append((wf_id, local_wf_map[wf_id]["name"]))

    # Action comparison
    all_act_ids = set(server_act_map.keys()) | set(local_act_map.keys())
    for act_id in all_act_ids:
        if act_id not in local_act_map:
            results["Action"]["SERVER_ONLY"].append((act_id, server_act_map[act_id]["name"]))
        elif act_id not in server_act_map:
            results["Action"]["LOCAL_ONLY"].append((act_id, local_act_map[act_id]["name"]))
        else:
            srv_ver = server_act_map[act_id].get("version", "0.0.0")
            loc_ver = local_act_map[act_id]["version"]
            modified = (srv_ver != loc_ver)
            
            if not modified:
                try:
                    srv_act = client.get_action(act_id)
                    srv_code = (srv_act.get("script", "") or "").replace("\r\n", "\n").strip()
                    with open(os.path.join(local_act_map[act_id]["dir"], "script.js"), "r", encoding="utf-8") as sf:
                        loc_code = sf.read().replace("\r\n", "\n").strip()
                    if srv_code != loc_code:
                        modified = True
                except Exception:
                    modified = True
            
            if modified:
                results["Action"]["MODIFIED"].append((act_id, local_act_map[act_id]["name"]))
            else:
                results["Action"]["IN_SYNC"].append((act_id, local_act_map[act_id]["name"]))

    # Configuration comparison
    all_cfg_ids = set(server_cfg_map.keys()) | set(local_cfg_map.keys())
    for cfg_id in all_cfg_ids:
        if cfg_id not in local_cfg_map:
            results["ConfigurationElement"]["SERVER_ONLY"].append((cfg_id, server_cfg_map[cfg_id]["name"]))
        elif cfg_id not in server_cfg_map:
            results["ConfigurationElement"]["LOCAL_ONLY"].append((cfg_id, local_cfg_map[cfg_id]["name"]))
        else:
            srv_ver = server_cfg_map[cfg_id].get("version", "0.0.0")
            loc_ver = local_cfg_map[cfg_id]["version"]
            modified = (srv_ver != loc_ver)
            
            if not modified:
                try:
                    srv_cfg = client.get_configuration(cfg_id)
                    srv_attrs = {}
                    for attr in srv_cfg.get("attributes", []):
                        name = attr.get("name")
                        if name:
                            val = attr.get("value")
                            is_plain = False
                            if isinstance(val, dict) and "secure-string" in val:
                                is_plain = val["secure-string"].get("isPlainText", False)
                            
                            if attr.get("type") == "SecureString" and not is_plain:
                                srv_attrs[name] = "__SECURE_STRING_IGNORED__"
                            else:
                                srv_attrs[name] = val

                    loc_attrs = {}
                    for attr in local_cfg_map[cfg_id]["json"].get("attributes", []):
                        name = attr.get("name")
                        if name:
                            val = attr.get("value")
                            is_plain = False
                            if isinstance(val, dict) and "secure-string" in val:
                                is_plain = val["secure-string"].get("isPlainText", False)
                            
                            if attr.get("type") == "SecureString" and not is_plain:
                                loc_attrs[name] = "__SECURE_STRING_IGNORED__"
                            else:
                                loc_attrs[name] = val

                    if srv_attrs != loc_attrs:
                        modified = True
                except Exception:
                    modified = True
            
            if modified:
                results["ConfigurationElement"]["MODIFIED"].append((cfg_id, local_cfg_map[cfg_id]["name"]))
            else:
                results["ConfigurationElement"]["IN_SYNC"].append((cfg_id, local_cfg_map[cfg_id]["name"]))

    # Resource comparison
    all_res_ids = set(server_res_map.keys()) | set(local_res_map.keys())
    for res_id in all_res_ids:
        if res_id not in local_res_map:
            results["ResourceElement"]["SERVER_ONLY"].append((res_id, server_res_map[res_id]["name"]))
        elif res_id not in server_res_map:
            results["ResourceElement"]["LOCAL_ONLY"].append((res_id, local_res_map[res_id]["name"]))
        else:
            srv_ver = server_res_map[res_id].get("version", "0.0.0")
            loc_ver = local_res_map[res_id]["version"]
            modified = (srv_ver != loc_ver)
            
            if not modified:
                try:
                    srv_res = client.get_resource(res_id)
                    mime_type = srv_res.get("mime-type", "application/octet-stream")
                    srv_content = client.get_resource_content(res_id, mime_type)
                    
                    local_file = os.path.join(local_res_map[res_id]["dir"], local_res_map[res_id]["name"])
                    with open(local_file, "rb") as lf:
                        loc_content = lf.read()
                        
                    if srv_content != loc_content:
                        modified = True
                except Exception:
                    modified = True
            
            if modified:
                results["ResourceElement"]["MODIFIED"].append((res_id, local_res_map[res_id]["name"]))
            else:
                results["ResourceElement"]["IN_SYNC"].append((res_id, local_res_map[res_id]["name"]))

    # 4. Display results
    print("\n==================================================")
    print("             vRO GitOps Status Report             ")
    print("==================================================")

    for type_name, categories in results.items():
        total_type = sum(len(items) for items in categories.values())
        if total_type == 0:
            continue
            
        print(f"\n[+] Type: {type_name}")
        
        # In Sync
        if categories["IN_SYNC"]:
            print(f"  - In Sync ({len(categories['IN_SYNC'])} items):")
            for item in sorted(categories["IN_SYNC"], key=lambda x: x[1]):
                print(f"    * {item[1]} (ID: {item[0]})")
                
        # Modified
        if categories["MODIFIED"]:
            print(f"  - Modified ({len(categories['MODIFIED'])} items):")
            for item in sorted(categories["MODIFIED"], key=lambda x: x[1]):
                print(f"    * \033[93m{item[1]} (ID: {item[0]})\033[0m") # Yellow output
                
        # Local Only
        if categories["LOCAL_ONLY"]:
            print(f"  - Local Only ({len(categories['LOCAL_ONLY'])} items):")
            for item in sorted(categories["LOCAL_ONLY"], key=lambda x: x[1]):
                print(f"    * \033[92m{item[1]} (ID: {item[0]})\033[0m") # Green output
                
        # Server Only
        if categories["SERVER_ONLY"]:
            print(f"  - Server Only ({len(categories['SERVER_ONLY'])} items):")
            for item in sorted(categories["SERVER_ONLY"], key=lambda x: x[1]):
                print(f"    * \033[96m{item[1]} (ID: {item[0]})\033[0m") # Cyan output

    print("\n==================================================")
    summary_parts = []
    for state in ["IN_SYNC", "MODIFIED", "LOCAL_ONLY", "SERVER_ONLY"]:
        count = sum(len(results[t][state]) for t in results)
        summary_parts.append(f"{state}: {count}")
    print("Summary: " + " | ".join(summary_parts))
    print("==================================================\n")

def main():
    parser = argparse.ArgumentParser(description="VCF Automation & Orchestrator GitOps Sync Tool")
    parser.add_argument("action", choices=["pull-all", "push-all", "status"], help="Sync action to perform")
    parser.add_argument("--dry-run", action="store_true", help="Validates files and configurations without calling server APIs")
    parser.add_argument("--bootstrap", action="store_true", help="Force imports the package file before applying code changes")
    
    args = parser.parse_args()
    
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    config = load_config()
    
    if args.dry_run:
        logger.info("Dry-Run mode active.")
        if args.action == "push-all":
            push_all(None, config, root_dir, dry_run=True)
        else:
            logger.info("[DRY RUN] Operation verified.")
        return
        
    # Set up client
    client = VroClient(
        vcf_url=config["vcf_url"],
        refresh_token=config["refresh_token"],
        org=config.get("org", "default"),
        verify_ssl=config.get("verify_ssl", False)
    )
    
    # Execute action
    if args.action == "pull-all":
        pull_all(client, config, root_dir)
    elif args.action == "push-all":
        push_all(client, config, root_dir, dry_run=False, force_bootstrap=args.bootstrap)
    elif args.action == "status":
        status(client, config, root_dir)
        
if __name__ == "__main__":
    main()
