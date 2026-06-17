# -*- coding: utf-8 -*-
import os
import logging
import requests
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("vro_client")

class VroClient:
    def __init__(self, vcf_url, refresh_token, org="default", verify_ssl=False):
        """
        vRealize Orchestrator REST API Client using Token-based Auth.
        vcf_url: base URL of VCF Automation/vRA, e.g. https://vra.domain.com
        """
        self.vcf_url = vcf_url.rstrip('/')
        self.vco_url = f"{self.vcf_url}/vco"
        self.refresh_token = refresh_token
        self.org = org
        self.verify_ssl = verify_ssl
        self.access_token = None
        self.headers = {}
        
        # Suppress insecure request warnings if verify_ssl is False
        if not self.verify_ssl:
            requests.packages.urllib3.disable_warnings(
                requests.packages.urllib3.exceptions.InsecureRequestWarning
            )

    def authenticate(self):
        """
        Exchanges the Refresh Token for an Access Token using the VCF Automation OAuth token endpoint.
        """
        logger.info("Authenticating with VCF Automation using Refresh Token...")
        url = f"{self.vcf_url}/oauth/tenant/{self.org}/token"
        headers = {
            "Accept": "application/*",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        
        try:
            response = requests.post(url, headers=headers, data=data, verify=self.verify_ssl, timeout=30)
            if response.status_code >= 400:
                logger.error(f"Auth failed (status {response.status_code}): {response.text}")
                response.raise_for_status()
                
            res_data = response.json()
            self.access_token = res_data.get("access_token")
            if not self.access_token:
                raise ValueError("Access token not found in the response.")
            
            self.headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json"
            }
            logger.info("Authentication successful.")
            return True
        except Exception as e:
            logger.error(f"Authentication exception: {e}")
            raise

    def request(self, method, path, **kwargs):
        """
        Performs an authenticated HTTP request.
        """
        if not self.access_token:
            self.authenticate()
            
        url = f"{self.vco_url}{path}" if path.startswith("/api/") else f"{self.vco_url}/api{path}"
        
        # Merge headers
        headers = dict(self.headers)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
            
        try:
            response = requests.request(method, url, headers=headers, verify=self.verify_ssl, timeout=30, **kwargs)
            if response.status_code == 401:
                # Token might be expired, retry auth once
                logger.warning("Token expired or unauthorized. Retrying authentication...")
                self.authenticate()
                headers.update(self.headers)
                response = requests.request(method, url, headers=headers, verify=self.verify_ssl, timeout=30, **kwargs)
                
            return response
        except Exception as e:
            logger.error(f"HTTP request exception on {method} {path}: {e}")
            raise

    # ==========================================
    # Package Management API
    # ==========================================
    def import_package(self, file_path, overwrite=True):
        """
        Imports a .package file onto the vRO server using POST /packages.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Package file not found at {file_path}")
            
        logger.info(f"Importing package {file_path} (overwrite={overwrite})...")
        path = "/packages"
        params = {
            "overwrite": "true" if overwrite else "false",
            "importConfigurationAttributeValues": "true",
            "tagImportMode": "ImportAndOverwriteExistingValue",
            "importConfigSecureStringAttributeValues": "false"
        }
        
        with open(file_path, 'rb') as f:
            files = {
                "file": (os.path.basename(file_path), f, "application/octet-stream")
            }
            # Note: We must NOT pass Content-Type: application/json in headers when uploading file
            custom_headers = {"Accept": "application/json"}
            
            response = self.request("POST", path, params=params, files=files, headers=custom_headers)
            if response.status_code >= 400:
                logger.error(f"Package import failed (status {response.status_code}): {response.text}")
                response.raise_for_status()
                
            logger.info("Package imported successfully.")
            return response.json()
    def export_package(self, package_name, dest_file_path):
        """
        Exports a package from the vRO server as a binary file using GET /packages/{packageName}.
        """
        logger.info(f"Exporting package {package_name} to {dest_file_path}...")
        path = f"/packages/{quote(package_name)}"
        params = {
            "exportConfigurationAttributeValues": "true",
            "exportGlobalTags": "true",
            "exportVersionHistory": "true",
            "exportConfigSecureStringAttributeValues": "false"
        }
        
        # Set Accept header to get zip/binary attachment
        custom_headers = {"Accept": "application/zip, application/octet-stream"}
        
        response = self.request("GET", path, params=params, headers=custom_headers, stream=True)
        if response.status_code >= 400:
            logger.error(f"Package export failed (status {response.status_code}): {response.text}")
            response.raise_for_status()
            
        os.makedirs(os.path.dirname(dest_file_path), exist_ok=True)
        with open(dest_file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        logger.info(f"Package {package_name} exported successfully to {dest_file_path}")
        return True

    def get_package(self, package_name):
        """
        Gets package details using GET /packages/{packageName}.
        """
        path = f"/packages/{quote(package_name)}"
        response = self.request("GET", path, headers={"Accept": "application/json"})
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_or_update_package(self, package_name, workflow_ids, action_ids, config_ids=[], resource_ids=[]):
        """
        Creates a package if it doesn't exist, or updates it if it does, associating the specified elements.
        """
        pkg = self.get_package(package_name)
        payload = {
            "description": "GitOps tracked package",
            "items": {
                "workflows": workflow_ids,
                "actions": action_ids,
                "configurations": config_ids,
                "resources": resource_ids
            },
            "rebuild": True
        }
        
        if not pkg:
            # Create using PUT
            logger.info(f"Package '{package_name}' not found. Creating via PUT...")
            path = f"/packages/{quote(package_name)}"
            response = self.request("PUT", path, json=payload)
            if response.status_code >= 400:
                logger.error(f"Failed to create package (status {response.status_code}): {response.text}")
                response.raise_for_status()
            logger.info(f"Package '{package_name}' created successfully.")
        else:
            # Update using PATCH
            logger.info(f"Package '{package_name}' already exists. Updating via PATCH...")
            path = f"/packages/{quote(package_name)}"
            response = self.request("PATCH", path, json=payload)
            if response.status_code >= 400:
                logger.error(f"Failed to update package (status {response.status_code}): {response.text}")
                response.raise_for_status()
            logger.info(f"Package '{package_name}' updated successfully.")
        return True
    # ==========================================
    # Tag-based Resource Discovery API
    # ==========================================
    def find_resources_by_tag(self, resource_type, tag):
        """
        Finds vRO objects matching a tag.
        For Workflows: uses GET /catalog/System/Workflow?tags={tag}.
        For Actions: queries GET /actions and filters by FQN containing the tag.
        """
        if resource_type == "Action":
            logger.info(f"Finding Actions with tag '{tag}' (via FQN filtering)...")
            response = self.request("GET", "/actions")
            if response.status_code >= 400:
                logger.error(f"Failed to list actions (status {response.status_code}): {response.text}")
                response.raise_for_status()
            
            res_data = response.json()
            results = []
            if isinstance(res_data, dict):
                items = res_data.get("value", res_data.get("link", []))
                for item in items:
                    attrs = {}
                    for attr in item.get("attributes", []):
                        if isinstance(attr, dict):
                            name_key = attr.get("name")
                            val = attr.get("value")
                            if name_key:
                                attrs[name_key] = val
                                
                    fqn = attrs.get("fqn", "")
                    if tag.lower() in fqn.lower():
                        obj_id = item.get("id") or attrs.get("id") or attrs.get("@id")
                        obj_name = item.get("name") or attrs.get("name") or attrs.get("@name")
                        href = item.get("href", "")
                        if not obj_id and href:
                            obj_id = href.rstrip('/').split('/')[-1]
                            
                        if obj_id and obj_name:
                            results.append({
                                "id": obj_id,
                                "name": obj_name,
                                "type": "Action",
                                "href": href,
                                "fqn": fqn,
                                "version": attrs.get("version", "0.0.0")
                            })
            return results
        else:
            logger.info(f"Finding {resource_type}s with tag '{tag}'...")
            path = f"/catalog/System/{resource_type}"
            params = {
                "tags": tag,
                "maxResult": 1000
            }
            
            response = self.request("GET", path, params=params)
            if response.status_code >= 400:
                logger.error(f"Failed to find resources by tag (status {response.status_code}): {response.text}")
                response.raise_for_status()
                
            res_data = response.json()
            results = []
            if isinstance(res_data, dict):
                items = res_data.get("value", res_data.get("link", []))
                for item in items:
                    attrs = {}
                    for attr in item.get("attributes", []):
                        if isinstance(attr, dict):
                            name_key = attr.get("name")
                            val = attr.get("value")
                            if name_key:
                                attrs[name_key] = val
                                
                    obj_id = item.get("id") or attrs.get("id") or attrs.get("@id")
                    obj_name = item.get("name") or attrs.get("name") or attrs.get("@name")
                    
                    href = item.get("href", "")
                    if not obj_id and href:
                        obj_id = href.rstrip('/').split('/')[-1]
                        
                    if obj_id and obj_name:
                        results.append({
                            "id": obj_id,
                            "name": obj_name,
                            "type": resource_type,
                            "href": href,
                            "version": attrs.get("version", "0.0.0")
                        })
            return results

    # ==========================================
    # Category (Folder) API
    # ==========================================
    def list_categories(self, category_type="WorkflowCategory"):
        """
        Lists all categories of a given type.
        """
        path = "/categories"
        params = {
            "categoryType": category_type,
            "isRoot": "false"
        }
        response = self.request("GET", path, params=params)
        if response.status_code >= 400:
            response.raise_for_status()
            
        res_data = response.json()
        # Parse CategoriesList. Typically it has 'value' array of category metadata
        if isinstance(res_data, dict):
            return res_data.get("value", [])
        elif isinstance(res_data, list):
            return res_data
        return []

    def create_category(self, name, parent_id=None, category_type="WorkflowCategory"):
        """
        Creates a category on the server.
        """
        path = "/categories"
        payload = {
            "categoryType": category_type,
            "name": name
        }
        if parent_id:
            payload["parent-category-id"] = parent_id
            
        logger.info(f"Creating category '{name}' (parent: {parent_id}, type: {category_type})...")
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            logger.error(f"Failed to create category (status {response.status_code}): {response.text}")
            response.raise_for_status()
            
        return response.json()

    def ensure_category_path(self, category_path, category_type="WorkflowCategory"):
        """
        Walks a category path (e.g. 'GVP/Task') and creates any missing folders.
        Returns the leaf category ID.
        """
        # Normalize category path: strip slashes
        clean_path = category_path.strip('/')
        if not clean_path:
            raise ValueError("Category path cannot be empty.")
            
        logger.info(f"Ensuring category path '{clean_path}' ({category_type})...")
        
        # 1. Fetch all existing categories
        existing = self.list_categories(category_type=category_type)
        
        # 2. Check if the exact path already exists
        # In vRO WsCategory, category['path'] contains the full path, e.g. "GVP/Task"
        for cat in existing:
            # Check path case-insensitively or exactly. vRO paths are usually exact.
            if cat.get("path") == clean_path:
                logger.info(f"Category path '{clean_path}' already exists with ID: {cat['id']}")
                return cat["id"]
                
        # 3. If exact path does not exist, build it hierarchically
        parts = clean_path.split('/')
        current_path_parts = []
        parent_id = None
        
        for part in parts:
            current_path_parts.append(part)
            sub_path = '/'.join(current_path_parts)
            
            # Find if this prefix path exists
            found_id = None
            for cat in existing:
                if cat.get("path") == sub_path:
                    found_id = cat["id"]
                    break
                    
            if found_id:
                parent_id = found_id
            else:
                # Create the category under the parent
                new_cat = self.create_category(part, parent_id=parent_id, category_type=category_type)
                parent_id = new_cat["id"]
                # Refresh local cache list of categories to reflect additions
                existing = self.list_categories(category_type=category_type)
                
        return parent_id

    # ==========================================
    # Workflow API
    # ==========================================
    def get_workflow(self, workflow_id):
        """
        Fetches metadata of a workflow using GET /workflows/{id}.
        """
        path = f"/workflows/{workflow_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def get_workflow_content(self, workflow_id):
        """
        Fetches the content (schema/script items) of a workflow using GET /workflows/{id}/content.
        """
        path = f"/workflows/{workflow_id}/content"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_workflow_skeleton(self, name, category_id, workflow_id=None):
        """
        Creates a workflow skeleton using POST /workflows.
        """
        path = "/workflows"
        payload = {
            "name": name,
            "category-id": category_id
        }
        if workflow_id:
            payload["id"] = workflow_id
            
        logger.info(f"Creating workflow skeleton '{name}' (ID: {workflow_id}, Category ID: {category_id})...")
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            logger.error(f"Failed to create workflow skeleton (status {response.status_code}): {response.text}")
            response.raise_for_status()
            
        return response.json()

    def update_workflow_content(self, workflow_id, content_json):
        """
        Pushes/updates the content of a workflow using PUT /workflows/{id}/content.
        """
        logger.info(f"Updating content for workflow ID: {workflow_id}...")
        path = f"/workflows/{workflow_id}/content"
        
        # The content should be sent as JSON schema
        response = self.request("PUT", path, json=content_json)
        if response.status_code >= 400:
            logger.error(f"Failed to update workflow content (status {response.status_code}): {response.text}")
            response.raise_for_status()
            
        logger.info("Workflow content updated successfully.")
        return True

    def update_workflow(self, workflow_id, workflow_meta):
        """
        Updates workflow metadata (like version) using PUT /workflows/{id}.
        """
        logger.info(f"Updating workflow metadata for ID: {workflow_id}...")
        path = f"/workflows/{workflow_id}"
        response = self.request("PUT", path, json=workflow_meta)
        if response.status_code >= 400:
            logger.error(f"Failed to update workflow metadata (status {response.status_code}): {response.text}")
            response.raise_for_status()
        return response.json()

    # ==========================================
    # Stub APIs for Future Expansion (Actions, Configs, Resources)
    # ==========================================
    def get_action(self, action_id):
        """
        Fetches metadata and script of an action using GET /actions/{id}.
        """
        path = f"/actions/{action_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_action(self, action_id, action_json):
        """
        Updates an action on the server using PUT /actions/{id}.
        """
        logger.info(f"Updating action ID: {action_id}...")
        path = f"/actions/{action_id}"
        response = self.request("PUT", path, json=action_json)
        if response.status_code >= 400:
            logger.error(f"Failed to update action (status {response.status_code}): {response.text}")
            response.raise_for_status()
        return response.json()

    def create_action(self, action_json):
        """
        Creates an action on the server using POST /actions.
        """
        logger.info(f"Creating new action FQN: {action_json.get('fqn')}...")
        path = "/actions"
        response = self.request("POST", path, json=action_json)
        if response.status_code >= 400:
            logger.error(f"Failed to create action (status {response.status_code}): {response.text}")
            response.raise_for_status()
        return response.json()

    def get_configuration(self, config_id):
        """
        Fetches metadata of a configuration using GET /configurations/{id}.
        """
        path = f"/configurations/{config_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_configuration(self, config_id, config_json):
        """
        Updates a configuration on the server using PUT /configurations/{id}.
        """
        logger.info(f"Updating configuration ID: {config_id}...")
        path = f"/configurations/{config_id}"
        response = self.request("PUT", path, json=config_json)
        if response.status_code >= 400:
            logger.error(f"Failed to update configuration (status {response.status_code}): {response.text}")
            response.raise_for_status()
        return response.json() if response.text else {}

    def create_configuration(self, category_id, config_json):
        """
        Creates a configuration element on the server using POST /configurations.
        """
        logger.info(f"Creating new configuration name: {config_json.get('name')} under category: {category_id}...")
        path = "/configurations"
        params = {"categoryId": category_id}
        response = self.request("POST", path, params=params, json=config_json)
        if response.status_code >= 400:
            logger.error(f"Failed to create configuration (status {response.status_code}): {response.text}")
            response.raise_for_status()
        return response.json()

    def get_resource(self, resource_id):
        """
        Fetches metadata of a resource using GET /resources/{id}.
        """
        path = f"/resources/{resource_id}"
        response = self.request("GET", path, headers={"Accept": "application/vnd.o11n.resource.metadata+json"})
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def get_resource_content(self, resource_id, mime_type):
        """
        Fetches the binary content of a resource using GET /resources/{id} with the corresponding MIME type.
        """
        path = f"/resources/{resource_id}"
        response = self.request("GET", path, headers={"Accept": mime_type})
        if response.status_code >= 400:
            response.raise_for_status()
        return response.content

    def update_resource_content(self, resource_id, file_path_or_bytes, filename=None):
        """
        Updates the content of a resource using POST /resources/{id}.
        """
        logger.info(f"Updating resource content for ID: {resource_id}...")
        path = f"/resources/{resource_id}"
        
        # Determine if file_path_or_bytes is file path or raw bytes
        if isinstance(file_path_or_bytes, bytes):
            files = {
                "file": (filename or "file", file_path_or_bytes, "application/octet-stream")
            }
            f = None
        else:
            if not os.path.exists(file_path_or_bytes):
                raise FileNotFoundError(f"Resource file not found at {file_path_or_bytes}")
            f = open(file_path_or_bytes, "rb")
            files = {
                "file": (filename or os.path.basename(file_path_or_bytes), f, "application/octet-stream")
            }
        
        try:
            custom_headers = {"Accept": "application/json"}
            response = self.request("POST", path, files=files, headers=custom_headers)
            if response.status_code >= 400:
                logger.error(f"Failed to update resource content (status {response.status_code}): {response.text}")
                response.raise_for_status()
            logger.info("Resource content updated successfully.")
            return True
        finally:
            if f:
                f.close()

    def update_resource_metadata(self, resource_id, resource_json):
        """
        Updates resource metadata using PUT /resources/{id}.
        """
        logger.info(f"Updating resource metadata for ID: {resource_id}...")
        path = f"/resources/{resource_id}"
        response = self.request("PUT", path, json=resource_json)
        if response.status_code >= 400:
            logger.error(f"Failed to update resource metadata (status {response.status_code}): {response.text}")
            response.raise_for_status()
        return response.json() if response.text else {}

    def create_resource(self, category_id, file_path, filename=None):
        """
        Creates a new resource using POST /resources.
        """
        logger.info(f"Creating new resource from file {file_path} under category {category_id}...")
        path = "/resources"
        params = {"categoryId": category_id}
        
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Resource file not found at {file_path}")
            
        with open(file_path, "rb") as f:
            files = {
                "file": (filename or os.path.basename(file_path), f, "application/octet-stream")
            }
            custom_headers = {"Accept": "application/json"}
            response = self.request("POST", path, params=params, files=files, headers=custom_headers)
            if response.status_code >= 400:
                logger.error(f"Failed to create resource (status {response.status_code}): {response.text}")
                response.raise_for_status()
                
            logger.info("Resource created successfully.")
            try:
                return response.json()
            except Exception:
                return {"status": "success", "status_code": response.status_code}

