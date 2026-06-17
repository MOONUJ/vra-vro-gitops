# -*- coding: utf-8 -*-
import os
import logging
import requests
from urllib.parse import quote

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("vra_client")

class VraClient:
    def __init__(self, vcf_url, refresh_token, org="default", verify_ssl=False):
        """
        vRealize Automation / Aria Automation REST API Client using Token-based Auth.
        vcf_url: base URL of VCF Automation/vRA, e.g. https://vra.domain.com
        """
        self.vcf_url = vcf_url.rstrip('/')
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
        Exchanges the Refresh Token for an Access Token using the VCF Automation CSP token endpoint.
        """
        logger.info("Authenticating with Aria Automation using Refresh Token...")
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
                "Accept": "application/json",
                "Content-Type": "application/json"
            }
            logger.info("Authentication successful.")
            return True
        except Exception as e:
            logger.error(f"Authentication exception: {e}")
            raise

    def request(self, method, path, **kwargs):
        """
        Performs an authenticated HTTP request to vRA REST API endpoints.
        """
        if not self.access_token:
            self.authenticate()
            
        # Ensure path starts with a slash
        if not path.startswith('/'):
            path = '/' + path
        url = f"{self.vcf_url}{path}"
        
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
    # Project API
    # ==========================================
    def get_projects(self):
        """Lists all projects."""
        path = "/iaas/api/projects"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", [])

    def get_project_by_name(self, name):
        """Retrieves a project by its name."""
        path = "/iaas/api/projects"
        params = {"$filter": f"name eq '{name}'"}
        response = self.request("GET", path, params=params)
        if response.status_code >= 400:
            response.raise_for_status()
        content = response.json().get("content", [])
        return content[0] if content else None

    # ==========================================
    # Blueprint (Cloud Template) API
    # ==========================================
    def list_blueprints(self):
        """Lists blueprints."""
        path = "/blueprint/api/blueprints?size=1000"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", [])

    def get_blueprint(self, bp_id):
        """Gets blueprint details."""
        path = f"/blueprint/api/blueprints/{bp_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def get_blueprint_content(self, bp_id):
        """Gets blueprint YAML content."""
        path = f"/blueprint/api/blueprints/{bp_id}/content"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.text

    def create_blueprint(self, payload):
        """Creates a blueprint."""
        path = "/blueprint/api/blueprints"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_blueprint(self, bp_id, payload):
        """Updates a blueprint."""
        path = f"/blueprint/api/blueprints/{bp_id}"
        response = self.request("PUT", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def publish_blueprint_version(self, bp_id, version, release=True):
        """Publishes a blueprint version."""
        path = f"/blueprint/api/blueprints/{bp_id}/versions"
        payload = {
            "version": version,
            "release": release,
            "description": "GitOps automated release version"
        }
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    # ==========================================
    # Custom Resource API
    # ==========================================
    def list_custom_resources(self):
        """Lists custom resources."""
        path = "/form-service/api/custom/resource-types?size=1000"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", []) if isinstance(response.json(), dict) else response.json()

    def get_custom_resource(self, cr_id):
        """Gets custom resource details."""
        path = f"/form-service/api/custom/resource-types/{cr_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_custom_resource(self, payload):
        """Creates custom resource."""
        path = "/form-service/api/custom/resource-types"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_custom_resource(self, cr_id, payload):
        """Updates custom resource using POST to collection endpoint."""
        path = "/form-service/api/custom/resource-types"
        payload_copy = dict(payload)
        payload_copy["id"] = cr_id
        response = self.request("POST", path, json=payload_copy)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json() if response.text else {}

    # ==========================================
    # Resource Action API
    # ==========================================
    def list_resource_actions(self):
        """Lists resource actions."""
        path = "/form-service/api/custom/resource-actions?size=1000"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", []) if isinstance(response.json(), dict) else response.json()

    def get_resource_action(self, ra_id):
        """Gets resource action details."""
        path = f"/form-service/api/custom/resource-actions/{ra_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_resource_action(self, payload):
        """Creates resource action."""
        path = "/form-service/api/custom/resource-actions"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_resource_action(self, ra_id, payload):
        """Updates resource action using POST to collection endpoint."""
        path = "/form-service/api/custom/resource-actions"
        payload_copy = dict(payload)
        payload_copy["id"] = ra_id
        response = self.request("POST", path, json=payload_copy)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json() if response.text else {}

    # ==========================================
    # Catalog Source API
    # ==========================================
    def list_catalog_sources(self):
        """Lists catalog sources."""
        path = "/catalog/api/admin/sources?size=1000"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", []) if isinstance(response.json(), dict) else response.json()

    def get_catalog_source(self, cs_id):
        """Gets catalog source details."""
        path = f"/catalog/api/admin/sources/{cs_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_catalog_source(self, payload):
        """Creates catalog source."""
        path = "/catalog/api/admin/sources"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_catalog_source(self, cs_id, payload):
        """Updates catalog source using POST to collection endpoint."""
        path = "/catalog/api/admin/sources"
        payload_copy = dict(payload)
        payload_copy["id"] = cs_id
        response = self.request("POST", path, json=payload_copy)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json() if response.text else {}

    # ==========================================
    # Policy API
    # ==========================================
    def list_policies(self):
        """Lists policies."""
        path = "/policy/api/policies?size=1000"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", []) if isinstance(response.json(), dict) else response.json()

    def get_policy(self, policy_id):
        """Gets policy details."""
        path = f"/policy/api/policies/{policy_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_policy(self, payload):
        """Creates policy."""
        path = "/policy/api/policies"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_policy(self, policy_id, payload):
        """Updates policy using POST to collection endpoint."""
        path = "/policy/api/policies"
        payload_copy = dict(payload)
        payload_copy["id"] = policy_id
        response = self.request("POST", path, json=payload_copy)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json() if response.text else {}

    # ==========================================
    # ABX Action API
    # ==========================================
    def list_abx_actions(self):
        """Lists ABX actions."""
        path = "/abx/api/resources/actions?size=1000"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", []) if isinstance(response.json(), dict) else response.json()

    def get_abx_action(self, action_id):
        """Gets ABX action details."""
        path = f"/abx/api/resources/actions/{action_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_abx_action(self, payload):
        """Creates ABX action."""
        path = "/abx/api/resources/actions"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_abx_action(self, action_id, payload):
        """Updates ABX action."""
        path = f"/abx/api/resources/actions/{action_id}"
        response = self.request("PUT", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    # ==========================================
    # Subscription (Event Broker) API
    # ==========================================
    def list_subscriptions(self):
        """Lists subscriptions."""
        path = "/event-broker/api/subscriptions?size=1000"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", []) if isinstance(response.json(), dict) else response.json()

    def get_subscription(self, sub_id):
        """Gets subscription details."""
        path = f"/event-broker/api/subscriptions/{sub_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_subscription(self, payload):
        """Creates subscription."""
        path = "/event-broker/api/subscriptions"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json() if response.text else {}

    def update_subscription(self, sub_id, payload):
        """Updates subscription using POST to collection endpoint."""
        path = "/event-broker/api/subscriptions"
        payload_copy = dict(payload)
        payload_copy["id"] = sub_id
        response = self.request("POST", path, json=payload_copy)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json() if response.text else {}

    # ==========================================
    # Service Broker Catalog & Forms API
    # ==========================================
    def list_catalog_items(self):
        """Lists all catalog items in Service Broker (Admin)."""
        path = "/catalog/api/admin/items?size=1000"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json().get("content", []) if isinstance(response.json(), dict) else response.json()

    def get_custom_form(self, source_type, source_id):
        """Fetches the request form schema by source type and source id."""
        path = f"/form-service/api/forms/fetchBySourceAndType?sourceType={source_type}&sourceId={source_id}&formType=requestForm"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_or_update_custom_form(self, payload):
        """Creates or updates a custom form layout schema."""
        path = "/form-service/api/forms"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json() if response.text else {}

    # ==========================================
    # Naming Policy API
    # ==========================================
    def list_naming_policies(self):
        """Lists naming policies."""
        path = "/provisioning/naming"
        response = self.request("GET", path)
        if response.status_code >= 400:
            response.raise_for_status()
        res_json = response.json()
        if isinstance(res_json, dict) and "content" in res_json:
            return res_json["content"]
        elif isinstance(res_json, list):
            return res_json
        return []

    def get_naming_policy(self, naming_id):
        """Gets naming policy details."""
        path = f"/provisioning/naming/{naming_id}"
        response = self.request("GET", path)
        if response.status_code == 404:
            return None
        elif response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def create_naming_policy(self, payload):
        """Creates a naming policy."""
        path = "/provisioning/naming"
        response = self.request("POST", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def update_naming_policy(self, naming_id, payload):
        """Updates a naming policy."""
        path = f"/provisioning/naming/{naming_id}"
        response = self.request("PUT", path, json=payload)
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json() if response.text else {}
