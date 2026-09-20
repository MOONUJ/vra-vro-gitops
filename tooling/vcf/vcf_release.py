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
import subprocess
from datetime import datetime
from urllib.parse import quote
import yaml
from config_loader import ConfigError, REPOSITORY_ROOT, load_source_config, normalize_runtime_config
from release_artifact import (
    ReleaseArtifactError,
    build_local_release,
    finalize_release,
    prepare_staging,
    verify_release,
)
from policy import PolicyError, evaluate_plan, load_policy, policy_hash
from restore_plan import RestorePlanError, RestorePlanService
from repository import (
    RepositoryContextError,
    RepositoryMode,
    detect_repository_context,
    is_worktree_clean,
    require_operation_allowed,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("vcf_provision")


def _tool_version():
    path = REPOSITORY_ROOT / ".template-version"
    return path.read_text(encoding="utf-8").strip() if path.is_file() else "development"


def _git_commit():
    result = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode != 0:
        raise ReleaseArtifactError(result.stderr.strip() or "Git commit을 확인하지 못했습니다.")
    return result.stdout.strip()


class _ExportProblemHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(self.format(record))

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

def export_legacy(vra_client, vro_client, config, version, output_dir):
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
            # 기존 package를 읽기 전용으로 export한다. Version과 membership은 변경하지 않는다.
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


def export_release(vra_client, vro_client, config, version, output_dir, target, tool_version, git_commit):
    """원격 mutation 없이 export한 결과를 불변 release와 provenance로 마감한다."""
    staging_root, staged_release, destination = prepare_staging(output_dir, version)
    problem_handler = _ExportProblemHandler()
    logger.addHandler(problem_handler)
    try:
        # export_legacy는 output_dir/version을 생성하므로 미리 만든 빈 디렉터리를 제거한다.
        staged_release.rmdir()
        export_legacy(vra_client, vro_client, config, version, str(staging_root))
        if problem_handler.messages:
            raise ReleaseArtifactError("원격 export가 완전하지 않습니다:\n" + "\n".join(problem_handler.messages))
        return finalize_release(
            staging_root,
            staged_release,
            destination,
            version,
            "remote-export",
            target,
            tool_version,
            git_commit,
            {"gitopsTag": config.get("gitops_tag"), "projects": sorted(config.get("projects", []))},
        )
    except Exception:
        if staging_root.exists():
            shutil.rmtree(staging_root)
        raise
    finally:
        logger.removeHandler(problem_handler)

def restore_legacy(vra_client, vro_client, config, version, input_dir):
    """
    Day-1 Restore: Loads the deployment artifacts (zip & .package) for a specific version
    and applies them to the target server, creating skeletons or initializing configurations.
    """
    logger.info(f"=== Starting Day-1 Restore for version: {version} ===")
    configured_project_name, configured_project_id = validate_restore_projects(vra_client, config)

    artifact_path = os.path.abspath(os.path.join(input_dir, version))
    manifest_file = os.path.join(artifact_path, "manifest.json")
    if not os.path.exists(manifest_file):
        logger.error(f"Manifest file not found at {manifest_file}. Cannot proceed.")
        sys.exit(1)

    with open(manifest_file, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    components = manifest.get("components") or manifest.get("spec", {}).get("exportComponents", {})
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

            # Plan 단계에서 검증한 단일 project에만 복구한다.
            projects_by_name = {configured_project_name: configured_project_id}
            target_projects_config = [configured_project_name]
            target_project_id = configured_project_id

            def resolve_project_id(proj_name):
                if proj_name in projects_by_name:
                    return projects_by_name[proj_name]
                return target_project_id

            # 검증된 설정 값을 사용하며 임의 project나 placeholder로 fallback하지 않는다.
            target_project_name = configured_project_name

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


def validate_restore_projects(vra_client, config):
    configured = config.get("projects", [])
    if len(configured) != 1:
        raise RestorePlanError("restore 대상 project를 정확히 하나 설정해야 합니다.")
    projects = vra_client.get_projects()
    if not isinstance(projects, list):
        raise RestorePlanError("Automation Project discovery 응답이 목록이 아닙니다.")
    projects_by_name = {project.get("name"): project.get("id") for project in projects}
    if configured[0] not in projects_by_name or not projects_by_name[configured[0]]:
        raise RestorePlanError(f"restore 대상 project를 찾을 수 없습니다: {configured[0]}")
    return configured[0], projects_by_name[configured[0]]


def verify_restored_release(vra_client, vro_client, config, release):
    components = release.get("spec", {}).get("exportComponents")
    if not isinstance(components, dict):
        raise RestorePlanError("현재 restore는 remote-export release만 지원합니다.")

    def names(items):
        return {item.get("name") or item.get("displayName") for item in items if isinstance(item, dict)}

    checks = {
        "blueprints": names(vra_client.list_blueprints()),
        "abx_actions": names(vra_client.list_abx_actions()),
        "custom_resources": names(vra_client.list_custom_resources()),
        "resource_actions": names(vra_client.list_resource_actions()),
        "catalog_sources": names(vra_client.list_catalog_sources()),
        "policies": names(vra_client.list_policies()),
        "subscriptions": names(vra_client.list_subscriptions()),
        "naming_policies": names(vra_client.list_naming_policies()),
    }
    for component, remote_names in checks.items():
        expected = set(components.get(component, []))
        missing = sorted(expected - remote_names)
        if missing:
            raise RestorePlanError(f"restore 후 {component}가 없습니다: {', '.join(missing)}")

    package_file = components.get("vro_package")
    if package_file:
        package_name = config.get("package", {}).get("name")
        if not package_name:
            raise RestorePlanError("검증할 vRO package name이 설정되지 않았습니다.")
        temporary = tempfile.mkdtemp()
        try:
            exported = os.path.join(temporary, package_file)
            vro_client.export_package(package_name, exported)
            if not os.path.isfile(exported) or os.path.getsize(exported) == 0:
                raise RestorePlanError("restore 후 vRO package를 검증하지 못했습니다.")
        finally:
            shutil.rmtree(temporary)
    return True

def main(argv=None):
    parser = argparse.ArgumentParser(description="VCF Automation & Orchestrator Day-1 Provisioning Tool")
    parser.add_argument(
        "action",
        choices=["export", "backup", "release-build", "verify", "restore", "restore-plan", "restore-apply"],
        help="Lifecycle action to perform",
    )
    parser.add_argument("--version", required=True, help="SemVer release version")
    parser.add_argument("--artifacts-dir", default=None, help="Directory to read/write release artifacts")
    parser.add_argument("--instance", default=str(REPOSITORY_ROOT / "instance.yaml"), help="Automation 인스턴스 정의 파일")
    parser.add_argument("--secrets", default=str(REPOSITORY_ROOT / "secrets.json"), help="로컬 비밀값 파일")
    parser.add_argument("--plans-root", default=str(REPOSITORY_ROOT / ".gitops" / "restore-plans"))
    parser.add_argument("--results-root", default=str(REPOSITORY_ROOT / ".gitops" / "restore-results"))
    parser.add_argument("--locks-root", default=str(REPOSITORY_ROOT / ".gitops" / "locks"))
    parser.add_argument("--plan", help="적용할 restore plan artifact")
    parser.add_argument("--approve-plan", help="명시적으로 승인할 restore plan hash")
    parser.add_argument("--approve-artifact", action="append", default=[], help="artifact:path:sha256 승인")
    parser.add_argument("--expires-in", type=int, default=1800)
    parser.add_argument("--policy", default=str(REPOSITORY_ROOT / "governance" / "policy.yaml"))

    args = parser.parse_args(argv)

    try:
        repository_context = detect_repository_context(REPOSITORY_ROOT)
        require_operation_allowed(repository_context, args.action)
        active_policy = load_policy(args.policy)
        active_policy_hash = policy_hash(active_policy)
    except (PolicyError, RepositoryContextError, OSError) as exc:
        logger.error(f"설정 오류: {exc}")
        return 1

    if not args.artifacts_dir:
        args.artifacts_dir = str(
            REPOSITORY_ROOT / ("releases" if repository_context.mode == RepositoryMode.INSTANCE else ".gitops/release-exports")
        )

    if args.action == "verify":
        try:
            manifest = verify_release(Path(args.artifacts_dir) / args.version)
        except ReleaseArtifactError as exc:
            logger.error(f"release 검증 오류: {exc}")
            return 1
        print(f"VERIFIED {manifest['metadata']['version']}")
        return 0

    if args.action == "release-build":
        if not is_worktree_clean(repository_context):
            logger.error("release-build는 추적 파일 변경이 없는 commit에서만 실행할 수 있습니다.")
            return 1
        instance_path = Path(args.instance)
        if not instance_path.is_file() and repository_context.mode == RepositoryMode.TEMPLATE:
            instance_path = REPOSITORY_ROOT / "instance.example.yaml"
        try:
            instance = yaml.safe_load(instance_path.read_text(encoding="utf-8"))
            target = {
                "name": instance["metadata"]["name"],
                "endpoint": instance["spec"]["endpoint"],
                "organization": instance["spec"].get("organization", "default"),
            }
            release_path, _ = build_local_release(
                REPOSITORY_ROOT,
                args.artifacts_dir,
                args.version,
                target,
                _tool_version(),
                active_policy_hash,
                _git_commit(),
            )
        except (KeyError, TypeError, yaml.YAMLError, OSError, ReleaseArtifactError) as exc:
            logger.error(f"release build 오류: {exc}")
            return 1
        print(f"release {release_path.resolve()}")
        return 0

    try:
        source_config = load_source_config(args.instance, args.secrets)
        config = normalize_runtime_config(source_config)
    except (ConfigError, OSError) as exc:
        logger.error(f"설정 오류: {exc}")
        return 1

    os.makedirs(args.artifacts_dir, exist_ok=True)

    from vro_client import VroClient
    from vra_client import VraClient

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

    target = {
        "name": source_config["environment"]["name"],
        "endpoint": config["vcf_url"],
        "organization": config.get("org", "default"),
    }
    if args.action in {"restore-plan", "restore-apply"}:
        from content_observation import complete_observation
        from vcf_sync import get_vra_status, get_vro_status

        try:
            validate_restore_projects(vra_client, config)
            observation = complete_observation(
                target,
                get_vro_status(vro_client, config, str(REPOSITORY_ROOT)),
                get_vra_status(vra_client, config, str(REPOSITORY_ROOT)),
            )
            service = RestorePlanService(
                args.plans_root,
                args.results_root,
                args.locks_root,
                target,
                _tool_version(),
            )
            if args.action == "restore-plan":
                release_path = Path(args.artifacts_dir) / args.version
                release = verify_release(release_path)
                if not isinstance(release.get("spec", {}).get("exportComponents"), dict):
                    raise RestorePlanError("현재 restore는 remote-export release만 지원합니다.")
                plan_path, plan = service.create_plan(release_path, observation, args.expires_in)
                evaluate_plan(plan, active_policy, "plan")
                print(f"Restore plan {plan['metadata']['planHash']}")
                print(f"expiresAt {plan['metadata']['expiresAt']}")
                for approval in plan["spec"]["requiredApprovals"]:
                    print(f"approve {approval}")
                print(f"artifact {plan_path.resolve()}")
                return 0
            if not args.plan or not args.approve_plan:
                raise RestorePlanError("restore-apply에는 --plan과 --approve-plan이 필요합니다.")
            plan = service.load_plan(args.plan)
            evaluate_plan(plan, active_policy, "apply")

            def execute_restore(release_path):
                problem_handler = _ExportProblemHandler()
                logger.addHandler(problem_handler)
                try:
                    restore_legacy(
                        vra_client,
                        vro_client,
                        config,
                        release_path.name,
                        str(release_path.parent),
                    )
                    if problem_handler.messages:
                        raise RestorePlanError("restore가 완전하지 않습니다:\n" + "\n".join(problem_handler.messages))
                finally:
                    logger.removeHandler(problem_handler)

            result_path, result = service.apply(
                plan,
                args.approve_plan,
                args.approve_artifact,
                observation,
                execute_restore,
                lambda release: verify_restored_release(vra_client, vro_client, config, release),
            )
            print(f"{result['spec']['status']} RESTORE_RELEASE")
            print(f"result {result_path.resolve()}")
            return 0 if result["spec"]["status"] == "VERIFIED" else 1
        except (RestorePlanError, ReleaseArtifactError, PolicyError, ConfigError, OSError) as exc:
            logger.error(f"restore 오류: {exc}")
            return 1

    if args.action in {"export", "backup"}:
        if args.action == "backup":
            logger.warning("backup은 read-only export alias입니다. export를 사용하세요.")
        try:
            release_path, _ = export_release(
                vra_client,
                vro_client,
                config,
                args.version,
                args.artifacts_dir,
                target,
                _tool_version(),
                _git_commit(),
            )
        except (ReleaseArtifactError, OSError) as exc:
            logger.error(f"release export 오류: {exc}")
            return 1
        print(f"release {release_path.resolve()}")
    elif args.action == "restore":
        logger.error("direct restore는 비활성화되었습니다. restore-plan과 restore-apply를 사용하세요.")
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
